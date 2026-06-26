"""
sources/yfinance_source.py — Free, structured scoring from yfinance data

No API costs, no LLM calls. Pulls real financial ratios from Yahoo
Finance and scores them using sector-aware thresholds (a bank's
healthy D/E is very different from a manufacturer's).

Limitations (be upfront about these in red_flags / notes when hit):
  - No promoter holding / pledge data (India-specific, not in yfinance)
  - No litigation / governance narrative
  - Smallcap coverage can be sparse (some fields return None)
  - revenueGrowth / earningsGrowth sometimes missing for Indian stocks
"""

from __future__ import annotations
import warnings
from typing import Any, Dict, Optional

import pandas as pd

from .base import FundamentalSource, SectorSource, MomentumSource
from .cache import cached_fetch

warnings.filterwarnings("ignore")


def _fetch_history_with_retry(symbol: str, period: str = "9mo", attempts: int = 3) -> pd.DataFrame:
    """
    Fetch yfinance history with exponential backoff on 429 (Too Many
    Requests) errors. Server IPs get throttled much more aggressively
    than residential IPs, so this matters a lot more in production
    than it did in local testing.
    """
    import time
    import yfinance as yf

    last_exc = None
    for attempt in range(attempts):
        try:
            hist = yf.Ticker(symbol).history(period=period, auto_adjust=True)
            if not hist.empty:
                return hist
        except Exception as e:
            last_exc = e
            msg = str(e)
            if "429" in msg or "Too Many Requests" in msg:
                # Back off harder for rate limiting specifically
                time.sleep(3.0 * (attempt + 1))
            else:
                time.sleep(1.0)
            continue
    return pd.DataFrame()


# ─────────────────────────────────────────────────────────────────────
# Sector buckets for threshold selection — see design discussion
# ─────────────────────────────────────────────────────────────────────

FINANCIAL_SECTORS      = {"Bank", "Financials"}
CAPITAL_INTENSIVE      = {"Auto", "Industrials", "Power & Utilities", "Realty",
                           "Metals & Mining", "Building Materials", "Energy",
                           "Transportation"}
ASSET_LIGHT             = {"I.T", "FMCG", "Healthcare", "Consumer Discretionary",
                            "Media", "Services", "Telecom", "Telecom-Service"}


def _de_thresholds(sector: Optional[str]) -> tuple:
    """Returns (healthy_max, moderate_max) for Debt/Equity by sector bucket."""
    if sector in FINANCIAL_SECTORS:
        return (8.0, 12.0)      # leverage is the business model
    if sector in CAPITAL_INTENSIVE:
        return (1.2, 2.0)
    return (0.6, 1.2)           # asset-light default


def _clean_symbol(symbol_code: str) -> str:
    import re
    return re.sub(r"[-_](EQ|BE|BL|GC|IL|SM|ST|N1|N2|N3|N4|W1|W2|W3|W4)$", "",
                   symbol_code.strip().upper())


def _yf_symbol(symbol_code: str, exchange: str) -> str:
    clean  = _clean_symbol(symbol_code)
    suffix = ".BO" if (exchange or "NSE").upper() == "BSE" else ".NS"
    return f"{clean}{suffix}"


# ─────────────────────────────────────────────────────────────────────
# Fundamental scoring
# ─────────────────────────────────────────────────────────────────────

class YFinanceFundamentalSource(FundamentalSource):
    def get_fundamentals(self, symbol_code: str, exchange: str, sector: Optional[str] = None) -> Dict[str, Any]:
        import time
        import yfinance as yf

        yf_sym = _yf_symbol(symbol_code, exchange)
        info = {}

        for attempt in range(3):
            try:
                ticker = yf.Ticker(yf_sym)
                info   = ticker.info or {}
                if info and (info.get("trailingPE") is not None or info.get("marketCap") is not None):
                    break
            except Exception as e:
                if "429" in str(e) or "Too Many Requests" in str(e):
                    time.sleep(3.0 * (attempt + 1))
                else:
                    time.sleep(1.0)
                continue

        if not info or (info.get("trailingPE") is None and info.get("marketCap") is None):
            # BSE fallback
            for attempt in range(2):
                try:
                    ticker = yf.Ticker(yf_sym.replace(".NS", ".BO"))
                    info   = ticker.info or {}
                    if info:
                        break
                except Exception as e:
                    if "429" in str(e) or "Too Many Requests" in str(e):
                        time.sleep(3.0 * (attempt + 1))
                    continue

        if not info:
            return self._empty_result("No fundamental data available from data provider.")

        pe          = info.get("trailingPE")
        pb          = info.get("priceToBook")
        de          = info.get("debtToEquity")
        roe         = info.get("returnOnEquity")
        roa         = info.get("returnOnAssets")
        op_margin   = info.get("operatingMargins")
        net_margin  = info.get("profitMargins")
        rev_growth  = info.get("revenueGrowth")
        earn_growth = info.get("earningsGrowth")
        current_r   = info.get("currentRatio")
        fcf         = info.get("freeCashflow")
        market_cap  = info.get("marketCap")

        score        = 50.0
        notes_fin    = []
        notes_biz    = []
        notes_val    = []
        red_flags    = []

        # ── Debt / Leverage (sector-aware) ───────────────────────────
        healthy_de, moderate_de = _de_thresholds(sector)
        if de is not None:
            de_ratio = de / 100 if de > 10 else de   # yfinance sometimes returns as %, sometimes raw
            if de_ratio <= healthy_de:
                score += 10
                notes_fin.append(f"Debt-to-Equity at {de_ratio:.2f} is within healthy range for its sector.")
            elif de_ratio <= moderate_de:
                score += 3
                notes_fin.append(f"Debt-to-Equity at {de_ratio:.2f} is moderate — manageable but worth monitoring.")
            else:
                score -= 10
                notes_fin.append(f"Debt-to-Equity at {de_ratio:.2f} is elevated for its sector.")
                red_flags.append(f"High leverage — Debt/Equity of {de_ratio:.2f} exceeds typical comfort levels for this sector.")
        else:
            notes_fin.append("Debt-to-Equity data not available from provider.")

        # ── Profitability ─────────────────────────────────────────────
        if net_margin is not None:
            if net_margin >= 0.15:
                score += 8
                notes_fin.append(f"Strong net margin of {net_margin*100:.1f}%.")
            elif net_margin >= 0.05:
                score += 3
                notes_fin.append(f"Moderate net margin of {net_margin*100:.1f}%.")
            elif net_margin < 0:
                score -= 15
                notes_fin.append(f"Negative net margin of {net_margin*100:.1f}% — company is currently loss-making.")
                red_flags.append("Company is reporting negative net profit margin.")
            else:
                score -= 3
                notes_fin.append(f"Thin net margin of {net_margin*100:.1f}%.")

        if op_margin is not None and op_margin < 0:
            red_flags.append("Negative operating margin — core business operations are unprofitable.")
            score -= 8

        # ── Growth ─────────────────────────────────────────────────────
        if rev_growth is not None:
            if rev_growth >= 0.15:
                score += 8
                notes_biz.append(f"Strong revenue growth of {rev_growth*100:.1f}% YoY.")
            elif rev_growth >= 0.05:
                score += 3
                notes_biz.append(f"Moderate revenue growth of {rev_growth*100:.1f}% YoY.")
            elif rev_growth < 0:
                score -= 8
                notes_biz.append(f"Revenue declined {abs(rev_growth)*100:.1f}% YoY.")
                red_flags.append(f"Revenue is declining year-over-year ({rev_growth*100:.1f}%).")
            else:
                notes_biz.append(f"Weak revenue growth of {rev_growth*100:.1f}% YoY.")
        else:
            notes_biz.append("Revenue growth data not available from provider.")

        # ── Returns ────────────────────────────────────────────────────
        if roe is not None:
            if roe >= 0.18:
                score += 7
                notes_fin.append(f"Strong Return on Equity of {roe*100:.1f}%.")
            elif roe >= 0.10:
                score += 2
                notes_fin.append(f"Decent Return on Equity of {roe*100:.1f}%.")
            elif roe < 0:
                score -= 8
                notes_fin.append(f"Negative Return on Equity ({roe*100:.1f}%).")

        # ── Liquidity ──────────────────────────────────────────────────
        if current_r is not None:
            if current_r < 1.0:
                score -= 5
                notes_fin.append(f"Current ratio of {current_r:.2f} is below 1 — potential short-term liquidity strain.")
                red_flags.append(f"Current ratio of {current_r:.2f} below 1.0 — current liabilities exceed current assets.")
            elif current_r >= 1.5:
                notes_fin.append(f"Healthy current ratio of {current_r:.2f}.")

        # ── Cash flow ──────────────────────────────────────────────────
        if fcf is not None:
            if fcf < 0:
                score -= 6
                notes_fin.append("Negative free cash flow — company is burning cash.")
                red_flags.append("Negative free cash flow.")
            else:
                notes_fin.append("Positive free cash flow.")

        # ── Valuation (sector-relative would need peer data; using absolute bands for now) ──
        if pe is not None and pe > 0:
            if sector in ASSET_LIGHT:
                cheap, expensive = 20, 45
            elif sector in FINANCIAL_SECTORS:
                cheap, expensive = 10, 25
            else:
                cheap, expensive = 12, 30

            if pe <= cheap:
                notes_val.append(f"P/E of {pe:.1f}x appears inexpensive for its sector.")
            elif pe <= expensive:
                notes_val.append(f"P/E of {pe:.1f}x is in a reasonable range for its sector.")
            else:
                notes_val.append(f"P/E of {pe:.1f}x is elevated — priced for high growth expectations.")
        else:
            notes_val.append("P/E not available — possibly loss-making or data gap.")

        if pb is not None:
            notes_val.append(f"Price-to-Book ratio: {pb:.2f}x.")

        # ── Ownership — yfinance has no India-specific promoter data ────
        notes_own = ["Promoter holding and pledge data is not available from this data source. "
                     "Consider checking exchange filings directly for ownership and governance signals."]

        score = max(0.0, min(100.0, score))
        rating = "Strong" if score >= 70 else "Good" if score >= 55 else "Average" if score >= 40 else "Weak"

        return {
            "score": round(score, 1),
            "rating": rating,
            "business_quality_notes": " ".join(notes_biz) or "Limited business quality data available.",
            "financial_health_notes": " ".join(notes_fin) or "Limited financial health data available.",
            "ownership_notes": " ".join(notes_own),
            "valuation_notes": " ".join(notes_val) or "Limited valuation data available.",
            "red_flags": red_flags,
            "raw_metrics": {
                "pe_ratio": pe, "pb_ratio": pb, "debt_to_equity": de,
                "roe": roe, "roa": roa, "operating_margin": op_margin,
                "net_margin": net_margin, "revenue_growth": rev_growth,
                "earnings_growth": earn_growth, "current_ratio": current_r,
                "free_cash_flow": fcf, "market_cap": market_cap,
            },
        }

    def _empty_result(self, reason: str) -> Dict[str, Any]:
        return {
            "score": 50.0, "rating": "Average",
            "business_quality_notes": reason,
            "financial_health_notes": reason,
            "ownership_notes": reason,
            "valuation_notes": reason,
            "red_flags": [],
            "raw_metrics": {},
        }


# ─────────────────────────────────────────────────────────────────────
# Sector scoring — relative strength of sector index vs Nifty 50
# ─────────────────────────────────────────────────────────────────────

class YFinanceSectorSource(SectorSource):
    """
    Sector scoring per user design: treat the sector index like a
    tradeable instrument, not just a "beat Nifty or not" percentage.

    Blends 4 inputs (News/Sentiment deferred -- see sector_technicals.py
    module docstring and project notes):
      1. Relative Strength vs Nifty 50 (1M/3M/6M weighted)   -- 30 pts
      2. RSI multi-timeframe (daily+weekly, trend-aware)      -- 25 pts
      3. MACD multi-timeframe (crossover quality/freshness)   -- 30 pts
      4. EMA50/EMA100 trend alignment (absolute trend gate)   -- 15 pts
      Total raw range before centering: roughly -70..+100

    Fetches 14 months of history (not 9) to give EMA100 and weekly
    RSI/MACD genuine warm-up data instead of being right at the edge
    of insufficient-history fallback behaviour.

    DAILY CACHING: a sector index's RSI/MACD/EMA only meaningfully
    changes once per trading day. Recomputing this on every single
    stock analysis was pure waste (hundreds of stocks sharing the same
    sector were each triggering a full fresh yfinance fetch+compute),
    and was a real contributor to the Yahoo Finance 429 rate-limiting
    problem. Results are now cached in the sector_score_cache DB table
    for 24 hours -- computed once, reused by every stock in that sector
    for the rest of the day, across all workers and surviving restarts
    (unlike the in-memory cache.py TTL cache, which is per-process and
    resets on restart).
    """

    HISTORY_PERIOD = "14mo"
    DAILY_CACHE_HOURS = 24

    def get_sector_analysis(self, sector: Optional[str], sector_index_symbol: Optional[str], db=None) -> Dict[str, Any]:
        if not sector_index_symbol:
            sector_index_symbol = "^CRSLDX"   # Nifty 500 fallback

        # ── Check DB cache first ──
        if db is not None:
            cached = self._read_cache(db, sector_index_symbol)
            if cached is not None:
                result = dict(cached)
                # sector_name reflects the CURRENT stock's sector label even
                # though the underlying index computation is shared/cached --
                # two different sector names can share the same fallback index
                result["sector_name"] = sector or "Unclassified"
                return result

        # ── Not cached or stale — compute fresh ──
        result = self._compute_fresh(sector, sector_index_symbol)

        if db is not None:
            self._write_cache(db, sector_index_symbol, result)

        return result

    def _read_cache(self, db, sector_index_symbol: str) -> Optional[Dict[str, Any]]:
        from datetime import datetime, timedelta
        from ...database import SectorScoreCache

        try:
            row = db.query(SectorScoreCache).filter(
                SectorScoreCache.sector_index_symbol == sector_index_symbol
            ).first()
        except Exception:
            return None

        if row is None:
            return None

        if row.computed_at is None:
            return None

        age = datetime.utcnow() - row.computed_at
        if age > timedelta(hours=self.DAILY_CACHE_HOURS):
            return None   # stale, recompute

        return {
            "sector_name": sector_index_symbol,  # overwritten by caller
            "sector_trend": row.sector_trend,
            "sector_strength_score": row.sector_strength_score,
            "sector_outlook": row.sector_outlook,
            "growth_drivers": row.growth_drivers or [],
            "risks": row.risks or [],
            "raw_metrics": row.raw_metrics or {},
        }

    def _write_cache(self, db, sector_index_symbol: str, result: Dict[str, Any]) -> None:
        from ...database import SectorScoreCache

        try:
            row = db.query(SectorScoreCache).filter(
                SectorScoreCache.sector_index_symbol == sector_index_symbol
            ).first()

            if row is None:
                row = SectorScoreCache(sector_index_symbol=sector_index_symbol)
                db.add(row)

            row.sector_strength_score = result["sector_strength_score"]
            row.sector_trend          = result["sector_trend"]
            row.sector_outlook        = result["sector_outlook"]
            row.growth_drivers        = result["growth_drivers"]
            row.risks                 = result["risks"]
            row.raw_metrics           = result["raw_metrics"]
            import datetime as _dt
            row.computed_at = _dt.datetime.utcnow()

            db.commit()
        except Exception:
            db.rollback()
            # Caching failure should never break the analysis itself --
            # the result is still returned to the caller either way.

    def _compute_fresh(self, sector: Optional[str], sector_index_symbol: str) -> Dict[str, Any]:
        from .sector_technicals import compute_sector_technical_score

        try:
            nifty_hist  = cached_fetch(f"nifty50_{self.HISTORY_PERIOD}",
                                        lambda: _fetch_history_with_retry("^NSEI", self.HISTORY_PERIOD))
            sector_hist = cached_fetch(f"sector_{sector_index_symbol}_{self.HISTORY_PERIOD}",
                                        lambda: _fetch_history_with_retry(sector_index_symbol, self.HISTORY_PERIOD))
        except Exception:
            nifty_hist  = pd.DataFrame()
            sector_hist = pd.DataFrame()

        if nifty_hist.empty or sector_hist.empty:
            return {
                "sector_name": sector or "Unclassified",
                "sector_trend": "Neutral",
                "sector_strength_score": 50.0,
                "sector_outlook": "Sector index data temporarily unavailable.",
                "growth_drivers": [],
                "risks": [],
                "raw_metrics": {},
            }

        # ── 1. Relative Strength vs Nifty (existing logic, kept as one input) ──
        def pct_return(df, days):
            if len(df) < days:
                return None
            return float((df["Close"].iloc[-1] / df["Close"].iloc[-days] - 1) * 100)

        nifty_1m, nifty_3m, nifty_6m = pct_return(nifty_hist, 21), pct_return(nifty_hist, 63), pct_return(nifty_hist, 126)
        sect_1m,  sect_3m,  sect_6m  = pct_return(sector_hist, 21), pct_return(sector_hist, 63), pct_return(sector_hist, 126)

        rs_1m = (sect_1m - nifty_1m) if (sect_1m is not None and nifty_1m is not None) else 0
        rs_3m = (sect_3m - nifty_3m) if (sect_3m is not None and nifty_3m is not None) else 0
        rs_6m = (sect_6m - nifty_6m) if (sect_6m is not None and nifty_6m is not None) else 0
        weighted_rs = (rs_1m * 0.5) + (rs_3m * 0.3) + (rs_6m * 0.2)

        # Scale RS% into a contribution, capped at its allotted SHARE of
        # the blend (see weight split below), not an independent +/-30.
        rs_points_raw = max(-30.0, min(30.0, weighted_rs * 1.5))

        # ── 2/3/4. RSI + MACD + EMA on the sector index itself ──
        tech_result = compute_sector_technical_score(sector_hist)
        # Raw technical_points range is roughly -70..+70 (25+30+15 caps)
        tech_points_raw = tech_result["technical_points"]

        # ── Combine with proper weighted share, NOT simple addition ──
        # BUG FIX: previously this summed rs_points(max 30) + tech_points(max 70)
        # directly onto a base of 50, giving a theoretical max of 150 that
        # silently clipped to 100 -- meaning many genuinely-strong-but-not-
        # perfect sectors all piled up at the 100 ceiling with no headroom
        # to differentiate "strong" from "every single sub-signal maxed out".
        #
        # Fix: each input is normalised to its OWN -1..+1 range first, then
        # combined using the agreed weights (RS=30%, RSI=25%, MACD=30%, EMA=15%)
        # against a total swing of +/-50 around the center of 50. This means
        # hitting exactly 100 requires every single sub-signal to be at its
        # own individual maximum simultaneously -- a genuinely rare event,
        # not a common one.
        rs_norm   = rs_points_raw / 30.0                                    # -1..+1
        rsi_norm  = tech_result["rsi"]["points"] / 25.0                     # -1..+1
        macd_norm = tech_result["macd"]["points"] / 30.0                    # -1..+1
        ema_norm  = tech_result["ema"]["points"] / 15.0                     # -1..+1

        blended_norm = (
            rs_norm   * 0.30
            + rsi_norm  * 0.25
            + macd_norm * 0.30
            + ema_norm  * 0.15
        )   # -1..+1, weights sum to 1.0

        score = 50.0 + (blended_norm * 50.0)
        score = max(0.0, min(100.0, score))

        # Keep these for raw_metrics / display purposes
        rs_points   = round(rs_points_raw, 1)
        tech_points = round(tech_points_raw, 1)

        # ── Trend label — require BOTH relative strength AND absolute technical
        # quality to agree before calling it Bullish/Bearish (fixes the flaw
        # where "beating a falling Nifty" alone got mislabeled bullish) ──
        ema_points = tech_result["ema"]["points"]
        absolute_trend_positive = ema_points > 0
        absolute_trend_negative = ema_points < 0

        if weighted_rs >= 3 and tech_points > 10 and absolute_trend_positive:
            trend = "Bullish"
        elif weighted_rs <= -3 and tech_points < -10 and absolute_trend_negative:
            trend = "Bearish"
        elif weighted_rs >= 3 and not absolute_trend_positive:
            # Beating Nifty but NOT in its own absolute uptrend --
            # the false-positive case flagged in design review
            trend = "Neutral (relative strength only — absolute trend not confirmed)"
        else:
            trend = "Neutral"

        is_fallback = sector_index_symbol == "^CRSLDX"
        benchmark_note = " (compared against broad market — no dedicated sector index available)" if is_fallback else ""

        # Cap fallback-index sectors below full confidence -- they're
        # measuring correlation with the broad market, not a real peer group
        if is_fallback:
            score = min(score, 65.0)

        outlook_parts = [
            f"{sector or 'This sector'} relative strength vs Nifty 50: 1M {rs_1m:+.1f}%, 3M {rs_3m:+.1f}%, 6M {rs_6m:+.1f}%{benchmark_note}."
        ]
        outlook_parts.extend(tech_result["rsi"]["notes"][:2])
        outlook_parts.extend(tech_result["macd"]["notes"][:2])
        outlook_parts.extend(tech_result["ema"]["notes"][:1])
        outlook = " ".join(outlook_parts)

        growth_drivers = []
        risks = []
        if trend == "Bullish":
            growth_drivers.append("Sector index showing genuine bullish alignment across relative strength, momentum (RSI/MACD), and trend structure (EMA).")
        elif trend == "Bearish":
            risks.append("Sector index showing genuine bearish alignment across relative strength, momentum (RSI/MACD), and trend structure (EMA).")
        elif "absolute trend not confirmed" in trend:
            risks.append("Sector is beating the broader market, but its own price trend is not confirmed bullish — could be a weaker sector falling less, not genuine strength.")

        return {
            "sector_name": sector or "Unclassified",
            "sector_trend": trend,
            "sector_strength_score": round(score, 1),
            "sector_outlook": outlook,
            "growth_drivers": growth_drivers,
            "risks": risks,
            "raw_metrics": {
                "sector_index_symbol": sector_index_symbol,
                "is_fallback_index": is_fallback,
                "relative_strength_1m": round(rs_1m, 2) if rs_1m else None,
                "relative_strength_3m": round(rs_3m, 2) if rs_3m else None,
                "relative_strength_6m": round(rs_6m, 2) if rs_6m else None,
                "weighted_relative_strength": round(weighted_rs, 2),
                "rs_points": round(rs_points, 1),
                "technical_points": tech_points,
                "rsi_daily": tech_result["rsi"].get("daily_rsi"),
                "rsi_weekly": tech_result["rsi"].get("weekly_rsi"),
                "macd_daily_bullish": tech_result["macd"].get("daily", {}).get("is_bullish"),
                "macd_weekly_bullish": tech_result["macd"].get("weekly", {}).get("is_bullish"),
                "ema50": tech_result["ema"].get("ema50"),
                "ema100": tech_result["ema"].get("ema100"),
            },
        }



# ─────────────────────────────────────────────────────────────────────
# Momentum scoring — relative strength of the STOCK vs Nifty 50
# ─────────────────────────────────────────────────────────────────────

class YFinanceMomentumSource(MomentumSource):
    def get_momentum(self, symbol_code: str, price_history: pd.DataFrame, sector_index_symbol: Optional[str] = None) -> Dict[str, Any]:
        import yfinance as yf

        if price_history is None or price_history.empty or len(price_history) < 30:
            return self._empty_result()

        try:
            # Shares the same cache key as YFinanceSectorSource's 14mo fetch
            # -- avoids a duplicate Nifty 50 fetch per stock during batch runs.
            # 14mo of data is a superset of the 9mo window used below, the
            # extra history is simply unused here.
            nifty_hist = cached_fetch("nifty50_14mo", lambda: _fetch_history_with_retry("^NSEI", "14mo"))
        except Exception:
            nifty_hist = pd.DataFrame()

        df = price_history.sort_values("date").reset_index(drop=True)
        close = df["close"]

        def pct_return(series, days):
            if len(series) < days:
                return None
            return float((series.iloc[-1] / series.iloc[-days] - 1) * 100)

        stock_1m, stock_3m = pct_return(close, 21), pct_return(close, 63)

        nifty_1m = nifty_3m = None
        if not nifty_hist.empty:
            nc = nifty_hist["Close"]
            nifty_1m = pct_return(nc, 21)
            nifty_3m = pct_return(nc, 63)

        rs_1m = (stock_1m - nifty_1m) if (stock_1m is not None and nifty_1m is not None) else None
        rs_3m = (stock_3m - nifty_3m) if (stock_3m is not None and nifty_3m is not None) else None

        # Volume trend — recent 10d vs prior 50d
        vol_ratio = None
        if len(df) >= 60:
            recent_vol = df["volume"].tail(10).mean()
            base_vol   = df["volume"].tail(60).head(50).mean()
            if base_vol:
                vol_ratio = round(recent_vol / base_vol, 2)

        score = 50.0
        if rs_1m is not None:
            score += max(-15, min(15, rs_1m * 1.2))
        if rs_3m is not None:
            score += max(-10, min(10, rs_3m * 0.8))
        if vol_ratio is not None:
            if vol_ratio >= 1.3:
                score += 8
            elif vol_ratio <= 0.6:
                score -= 5

        score = max(0.0, min(100.0, score))

        rs_text = []
        if rs_1m is not None:
            rs_text.append(f"1M relative strength vs Nifty 50: {rs_1m:+.1f}%")
        if rs_3m is not None:
            rs_text.append(f"3M relative strength vs Nifty 50: {rs_3m:+.1f}%")
        assessment = ". ".join(rs_text) if rs_text else "Insufficient data for relative strength calculation."

        if vol_ratio is not None:
            if vol_ratio >= 1.3:
                acc_dist = f"Volume running {vol_ratio}x above baseline — possible accumulation."
            elif vol_ratio <= 0.6:
                acc_dist = f"Volume running {vol_ratio}x below baseline — low participation."
            else:
                acc_dist = f"Volume near baseline ({vol_ratio}x) — no strong accumulation/distribution signal."
        else:
            acc_dist = "Insufficient volume data."

        return {
            "momentum_score": round(score, 1),
            "relative_strength_assessment": assessment,
            "accumulation_distribution": acc_dist,
            "raw_metrics": {
                "stock_return_1m": round(stock_1m, 2) if stock_1m else None,
                "stock_return_3m": round(stock_3m, 2) if stock_3m else None,
                "nifty_return_1m": round(nifty_1m, 2) if nifty_1m else None,
                "nifty_return_3m": round(nifty_3m, 2) if nifty_3m else None,
                "relative_strength_1m": round(rs_1m, 2) if rs_1m else None,
                "relative_strength_3m": round(rs_3m, 2) if rs_3m else None,
                "volume_ratio": vol_ratio,
            },
        }

    def _empty_result(self) -> Dict[str, Any]:
        return {
            "momentum_score": 50.0,
            "relative_strength_assessment": "Insufficient price history for momentum calculation.",
            "accumulation_distribution": "Insufficient data.",
            "raw_metrics": {},
        }