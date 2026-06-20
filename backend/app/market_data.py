"""
Market data abstraction layer.

Three interchangeable providers (set MARKET_DATA_PROVIDER in .env):

  mock     -- deterministic synthetic OHLCV, seeded per symbol.
  fyers    -- Fyers Data API v3. Uses token_id column from stock_mstr.
  yfinance -- Yahoo Finance. Maps NSE -> "<symbol>.NS", BSE -> "<symbol>.BO"
              Strips common suffixes like -EQ, -BE, -BL, -GC, -IL from
              symbol_code before building the Yahoo ticker.

`get_quote()` also accepts the `latest_update` JSON blob already stored
on stock_mstr by your existing feed process.
"""

from __future__ import annotations

import hashlib
import math
import random
import re
from abc import ABC, abstractmethod
from datetime import datetime, timedelta
from typing import Any, Dict, Optional

import pandas as pd
import requests

from .config import get_settings

settings = get_settings()


# ---------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------
def _clean_symbol(symbol_code: str) -> str:
    """
    Strip NSE/BSE series suffixes that yfinance doesn't understand.
    Examples:  RADICO-EQ  ->  RADICO
               EIFFL-BE   ->  EIFFL
               HDFCSILVER-EQ -> HDFCSILVER
    """
    return re.sub(r"[-_](EQ|BE|BL|GC|IL|SM|ST|N1|N2|N3|N4|W1|W2|W3|W4)$", "", symbol_code.strip().upper())


def quote_from_latest_update(latest_update: Optional[dict]) -> Optional[Dict[str, Any]]:
    if not latest_update or not isinstance(latest_update, dict):
        return None

    def pick(*keys):
        for k in keys:
            if k in latest_update and latest_update[k] is not None:
                try:
                    return float(latest_update[k])
                except (TypeError, ValueError):
                    pass
        return None

    ltp = pick("ltp", "last_price", "lp", "close", "c", "price")
    if ltp is None:
        return None

    prev_close = pick("prev_close", "previous_close", "pc", "prevClose")
    open_ = pick("open", "o")
    high = pick("high", "h")
    low = pick("low", "l")
    volume = pick("volume", "vol", "v", "tt_qty")
    change_pct = pick("change_pct", "pChange", "ch_pct", "per_change", "changePercent")

    if change_pct is None and prev_close:
        change_pct = ((ltp - prev_close) / prev_close) * 100 if prev_close else None

    ts = latest_update.get("timestamp") or latest_update.get("ts") or latest_update.get("updated_at")

    return {
        "ltp": ltp,
        "prev_close": prev_close,
        "open": open_,
        "high": high,
        "low": low,
        "volume": volume,
        "change_pct": change_pct,
        "ts": ts,
        "source": "stock_mstr.latest_update",
    }


# ---------------------------------------------------------------------
# Provider interface
# ---------------------------------------------------------------------
class MarketDataProvider(ABC):
    @abstractmethod
    def get_quote(self, symbol_code: str, exchange: str, token_id: Optional[int]) -> Dict[str, Any]:
        ...

    @abstractmethod
    def get_history(self, symbol_code: str, exchange: str, token_id: Optional[int], days: int = 400) -> pd.DataFrame:
        ...


# ---------------------------------------------------------------------
# Mock provider
# ---------------------------------------------------------------------
class MockProvider(MarketDataProvider):
    def _seed(self, symbol_code: str) -> int:
        return int(hashlib.md5(symbol_code.encode()).hexdigest(), 16) % (2**32)

    def get_history(self, symbol_code, exchange, token_id, days=400) -> pd.DataFrame:
        rng = random.Random(self._seed(symbol_code))
        base_price = rng.uniform(50, 3000)
        drift = rng.uniform(-0.0006, 0.0012)
        vol = rng.uniform(0.012, 0.03)
        regime = rng.choice(["base_near_high", "mid_correction", "extended", "downtrend"])

        rows = []
        price = base_price
        today = datetime.utcnow().date()
        for i in range(days):
            d = today - timedelta(days=days - i)
            if d.weekday() >= 5:
                continue
            shock = rng.gauss(0, vol)
            cycle = math.sin(i / 35.0) * 0.01
            step = drift + cycle + shock
            if regime == "extended" and i > days * 0.7:
                step += 0.004
            if regime == "downtrend":
                step -= 0.0008
            if regime == "mid_correction" and i > days * 0.6:
                step -= 0.0015
            price = max(1.0, price * (1 + step))
            o = price * (1 + rng.gauss(0, 0.004))
            h = max(o, price) * (1 + abs(rng.gauss(0, 0.006)))
            l = min(o, price) * (1 - abs(rng.gauss(0, 0.006)))
            v = max(1000, rng.gauss(200000, 80000))
            rows.append({"date": d, "open": round(o, 2), "high": round(h, 2),
                          "low": round(l, 2), "close": round(price, 2), "volume": int(v)})
        return pd.DataFrame(rows)

    def get_quote(self, symbol_code, exchange, token_id) -> Dict[str, Any]:
        hist = self.get_history(symbol_code, exchange, token_id, days=10)
        last = hist.iloc[-1]
        prev = hist.iloc[-2]
        change_pct = ((last["close"] - prev["close"]) / prev["close"]) * 100
        return {
            "ltp": float(last["close"]),
            "prev_close": float(prev["close"]),
            "open": float(last["open"]),
            "high": float(last["high"]),
            "low": float(last["low"]),
            "volume": float(last["volume"]),
            "change_pct": round(float(change_pct), 2),
            "ts": datetime.utcnow().isoformat(),
            "source": "mock",
        }


# ---------------------------------------------------------------------
# Fyers provider
# ---------------------------------------------------------------------
class FyersProvider(MarketDataProvider):
    def _fyers_symbol(self, symbol_code: str, exchange: str) -> str:
        exch = (exchange or "NSE").upper()
        code = symbol_code.upper()
        if "-" in code:
            return f"{exch}:{code}"
        return f"{exch}:{code}-EQ"

    def _headers(self) -> Dict[str, str]:
        return {"Authorization": f"{settings.fyers_app_id}:{settings.fyers_access_token}"}

    def get_quote(self, symbol_code, exchange, token_id) -> Dict[str, Any]:
        sym = self._fyers_symbol(symbol_code, exchange)
        resp = requests.get(
            f"{settings.fyers_base_url}/quotes",
            params={"symbols": sym},
            headers=self._headers(),
            timeout=10,
        )
        resp.raise_for_status()
        payload = resp.json()
        d = payload["d"][0]["v"]
        return {
            "ltp": d.get("lp"),
            "prev_close": d.get("prev_close_price"),
            "open": d.get("open_price"),
            "high": d.get("high_price"),
            "low": d.get("low_price"),
            "volume": d.get("volume"),
            "change_pct": d.get("chp"),
            "ts": datetime.utcnow().isoformat(),
            "source": "fyers",
        }

    def get_history(self, symbol_code, exchange, token_id, days=400) -> pd.DataFrame:
        sym = self._fyers_symbol(symbol_code, exchange)
        range_to = datetime.utcnow().date()
        range_from = range_to - timedelta(days=int(days * 1.6))
        resp = requests.get(
            f"{settings.fyers_base_url}/history",
            params={
                "symbol": sym,
                "resolution": "D",
                "date_format": "1",
                "range_from": range_from.isoformat(),
                "range_to": range_to.isoformat(),
                "cont_flag": "1",
            },
            headers=self._headers(),
            timeout=15,
        )
        resp.raise_for_status()
        payload = resp.json()
        candles = payload.get("candles", [])
        df = pd.DataFrame(candles, columns=["epoch", "open", "high", "low", "close", "volume"])
        df["date"] = pd.to_datetime(df["epoch"], unit="s").dt.date
        return df[["date", "open", "high", "low", "close", "volume"]]


# ---------------------------------------------------------------------
# Yahoo Finance provider  — fixes the -EQ suffix problem
# ---------------------------------------------------------------------
class YFinanceProvider(MarketDataProvider):
    def _yf_symbol(self, symbol_code: str, exchange: str) -> str:
        clean = _clean_symbol(symbol_code)
        suffix = ".BO" if (exchange or "NSE").upper() == "BSE" else ".NS"
        return f"{clean}{suffix}"

    def get_history(self, symbol_code, exchange, token_id, days=400) -> pd.DataFrame:
        import yfinance as yf
        import warnings
        warnings.filterwarnings("ignore")

        yf_sym = self._yf_symbol(symbol_code, exchange)
        period = f"{min(days, 730)}d"

        for attempt in range(3):
            try:
                ticker = yf.Ticker(yf_sym)
                hist   = ticker.history(period=period, auto_adjust=True)

                if hist.empty and ".NS" in yf_sym:
                    # BSE fallback
                    ticker2 = yf.Ticker(yf_sym.replace(".NS", ".BO"))
                    hist    = ticker2.history(period=period, auto_adjust=True)

                if not hist.empty:
                    break

            except Exception:
                if attempt < 2:
                    import time
                    time.sleep(1.5 * (attempt + 1))
                    continue
                break

        if hist.empty:
            return pd.DataFrame(columns=["date", "open", "high", "low", "close", "volume"])

        hist = hist.reset_index()
        hist.columns = [c.lower() for c in hist.columns]
        date_col = "datetime" if "datetime" in hist.columns else "date"
        hist["date"] = pd.to_datetime(hist[date_col]).dt.date
        return hist[["date", "open", "high", "low", "close", "volume"]].dropna()

    def get_quote(self, symbol_code, exchange, token_id) -> Dict[str, Any]:
        hist = self.get_history(symbol_code, exchange, token_id, days=10)
        if hist.empty or len(hist) < 2:
            return {
                "ltp": None, "prev_close": None, "open": None,
                "high": None, "low": None, "volume": None,
                "change_pct": None, "ts": datetime.utcnow().isoformat(),
                "source": "yfinance_no_data",
            }
        last = hist.iloc[-1]
        prev = hist.iloc[-2]
        change_pct = ((last["close"] - prev["close"]) / prev["close"]) * 100
        return {
            "ltp": float(last["close"]),
            "prev_close": float(prev["close"]),
            "open": float(last["open"]),
            "high": float(last["high"]),
            "low": float(last["low"]),
            "volume": float(last["volume"]),
            "change_pct": round(float(change_pct), 2),
            "ts": datetime.utcnow().isoformat(),
            "source": "yfinance",
        }


_PROVIDERS = {
    "mock": MockProvider,
    "fyers": FyersProvider,
    "yfinance": YFinanceProvider,
}


def get_provider() -> MarketDataProvider:
    cls = _PROVIDERS.get(settings.market_data_provider.lower(), MockProvider)
    return cls()