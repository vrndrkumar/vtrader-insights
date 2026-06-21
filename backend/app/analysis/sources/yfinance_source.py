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

warnings.filterwarnings("ignore")


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
        import yfinance as yf

        yf_sym = _yf_symbol(symbol_code, exchange)
        try:
            ticker = yf.Ticker(yf_sym)
            info   = ticker.info or {}
        except Exception:
            info = {}

        if not info or info.get("trailingPE") is None and info.get("marketCap") is None:
            # BSE fallback
            try:
                ticker = yf.Ticker(yf_sym.replace(".NS", ".BO"))
                info   = ticker.info or {}
            except Exception:
                info = {}

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
    def get_sector_analysis(self, sector: Optional[str], sector_index_symbol: Optional[str]) -> Dict[str, Any]:
        import yfinance as yf

        if not sector_index_symbol:
            sector_index_symbol = "^CRSLDX"   # Nifty 500 fallback

        try:
            nifty_hist  = yf.Ticker("^NSEI").history(period="9mo", auto_adjust=True)
            sector_hist = yf.Ticker(sector_index_symbol).history(period="9mo", auto_adjust=True)
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

        def pct_return(df, days):
            if len(df) < days:
                return None
            return float((df["Close"].iloc[-1] / df["Close"].iloc[-days] - 1) * 100)

        nifty_1m, nifty_3m, nifty_6m = pct_return(nifty_hist, 21), pct_return(nifty_hist, 63), pct_return(nifty_hist, 126)
        sect_1m,  sect_3m,  sect_6m  = pct_return(sector_hist, 21), pct_return(sector_hist, 63), pct_return(sector_hist, 126)

        rs_1m = (sect_1m - nifty_1m) if (sect_1m is not None and nifty_1m is not None) else 0
        rs_3m = (sect_3m - nifty_3m) if (sect_3m is not None and nifty_3m is not None) else 0
        rs_6m = (sect_6m - nifty_6m) if (sect_6m is not None and nifty_6m is not None) else 0

        # Weighted relative strength — recent performance weighted more
        weighted_rs = (rs_1m * 0.5) + (rs_3m * 0.3) + (rs_6m * 0.2)

        score = 50.0 + (weighted_rs * 2.5)   # scale RS% into score points
        score = max(0.0, min(100.0, score))

        if weighted_rs >= 3:
            trend = "Bullish"
        elif weighted_rs <= -3:
            trend = "Bearish"
        else:
            trend = "Neutral"

        is_fallback = sector_index_symbol == "^CRSLDX"
        benchmark_note = " (compared against broad market — no dedicated sector index available)" if is_fallback else ""

        outlook = (
            f"{sector or 'This sector'} is {'outperforming' if weighted_rs > 0 else 'underperforming'} "
            f"Nifty 50 by {abs(weighted_rs):.1f}% on a momentum-weighted basis{benchmark_note}. "
            f"1M relative strength: {rs_1m:+.1f}%, 3M: {rs_3m:+.1f}%, 6M: {rs_6m:+.1f}%."
        )

        growth_drivers = []
        risks = []
        if weighted_rs > 3:
            growth_drivers.append("Sector showing sustained outperformance vs broad market — institutional rotation likely underway.")
        elif weighted_rs < -3:
            risks.append("Sector showing sustained underperformance vs broad market — capital may be rotating out.")

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
            nifty_hist = yf.Ticker("^NSEI").history(period="9mo", auto_adjust=True)
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