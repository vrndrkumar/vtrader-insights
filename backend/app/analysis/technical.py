"""
Technical analysis engine — VTrader Stock Analyser

Scoring (total 100):
  Tier 1 — Price Structure      max 35 pts  (leading)
  Tier 2 — Candlestick Context  max 20 pts  (timing)
  Tier 3 — SMC patterns         max 15 pts  (institutional)
  Tier 4 — Lagging indicators   max 30 pts  (confirmation only)

Lagging indicators (SMA, RSI, volume averages) can also PENALISE
the score (e.g. -10 for full downtrend, -8 for overbought RSI)
so they still act as a meaningful filter without dominating.
"""

from __future__ import annotations
from typing import Any, Dict, List, Optional
import pandas as pd

from .patterns import (
    run_all_patterns,
    pattern_summary_to_dict,
    compute_lagging_score,
)


def _sma(series: pd.Series, w: int) -> Optional[float]:
    return float(series.tail(w).mean()) if len(series) >= w else None


def _rsi(series: pd.Series, period: int = 14) -> Optional[float]:
    if len(series) < period + 1:
        return None
    d    = series.diff().dropna()
    gain = d.clip(lower=0).rolling(period).mean().iloc[-1]
    loss = (-d.clip(upper=0)).rolling(period).mean().iloc[-1]
    if loss == 0:
        return 100.0
    return float(100 - 100 / (1 + gain / loss))


def _atr_pct(df: pd.DataFrame, period: int = 14) -> Optional[float]:
    if len(df) < period + 1:
        return None
    h, l, c  = df["high"], df["low"], df["close"]
    pc        = c.shift(1)
    tr        = pd.concat([(h-l), (h-pc).abs(), (l-pc).abs()], axis=1).max(axis=1)
    atr       = tr.rolling(period).mean().iloc[-1]
    lc        = c.iloc[-1]
    return float((atr / lc) * 100) if lc else None


def _swing_levels(df: pd.DataFrame, window: int = 5, lookback: int = 120) -> Dict[str, List[float]]:
    recent = df.tail(lookback).reset_index(drop=True)
    highs, lows = [], []
    for i in range(window, len(recent) - window):
        sh = recent["high"].iloc[i - window: i + window + 1]
        sl = recent["low"].iloc[i - window: i + window + 1]
        if recent["high"].iloc[i] == sh.max():
            highs.append(float(recent["high"].iloc[i]))
        if recent["low"].iloc[i] == sl.min():
            lows.append(float(recent["low"].iloc[i]))

    def cluster(lvls, tol=1.5):
        if not lvls:
            return []
        lvls = sorted(lvls)
        grps = [[lvls[0]]]
        for v in lvls[1:]:
            if abs(v - grps[-1][-1]) / grps[-1][-1] * 100 <= tol:
                grps[-1].append(v)
            else:
                grps.append([v])
        return [round(sum(g)/len(g), 2) for g in grps]

    return {"resistance": cluster(highs)[-3:], "support": cluster(lows)[-3:]}


def _classify_trend(price: float, sma50: Optional[float], sma200: Optional[float]) -> str:
    if sma50 and sma200:
        if price > sma50 > sma200:
            return "Uptrend"
        if price < sma50 < sma200:
            return "Downtrend"
        if price > sma200 and sma50 < sma200:
            return "Early Recovery (above 200DMA)"
    return "Sideways / Mixed"


def compute_technical(df: pd.DataFrame, quote: Dict[str, Any]) -> Dict[str, Any]:
    if df is None or df.empty:
        return {"error": "no_history", "technical_score": 35.0, "pattern_data": {}}

    df    = df.sort_values("date").reset_index(drop=True)
    close = df["close"]
    price = float(quote.get("ltp") or close.iloc[-1])

    # 52-week range
    w52     = df.tail(252)
    w52_hi  = float(w52["high"].max())
    w52_lo  = float(w52["low"].min())
    pct_hi  = ((price - w52_hi) / w52_hi) * 100
    pct_lo  = ((price - w52_lo) / w52_lo)  * 100

    # Indicators
    sma20   = _sma(close, 20)
    sma50   = _sma(close, 50)
    sma200  = _sma(close, 200)
    rsi14   = _rsi(close, 14)
    atr_p   = _atr_pct(df, 14)

    vr      = float(df["volume"].tail(10).mean())   if len(df) >= 10 else None
    vb      = float(df["volume"].tail(60).head(50).mean()) if len(df) >= 60 else None
    vol_rat = round(vr / vb, 2) if (vr and vb) else None

    levels  = _swing_levels(df)
    trend   = _classify_trend(price, sma50, sma200)

    # Preliminary structure label (may be overridden by pattern engine)
    near_hi = pct_hi >= -8
    ovb     = (rsi14 or 50) >= 72
    tight   = atr_p is not None and atr_p < 2.5
    above50 = sma50 is not None and price >= sma50

    if near_hi and ovb:
        structure = "Extended / Already Broken Out"
    elif near_hi and not ovb:
        structure = "Near Breakout"
    elif (-20 < pct_hi < -8) and above50 and tight:
        structure = "Base Building"
    elif pct_hi <= -20 and trend == "Uptrend":
        structure = "Pullback Within Uptrend"
    elif trend == "Downtrend":
        structure = "Downtrend"
    else:
        structure = "Choppy / No Clear Structure"

    # ── Tier 1/2/3 — Pattern engine ──────────────────────────────────
    pat_summary = run_all_patterns(df)
    pat_dict    = pattern_summary_to_dict(pat_summary)

    # Override structure if HH/HL post-correction detected
    hh_hl = next(
        (p for p in pat_summary.patterns if p.name == "HH/HL Structure" and p.detected), None
    )
    if hh_hl and hh_hl.details.get("had_major_correction"):
        structure = f"Post-Correction Recovery — {hh_hl.description}"

    # ── Tier 4 — Lagging confirmations ───────────────────────────────
    t4_score, t4_breakdown = compute_lagging_score(
        trend=trend,
        rsi14=rsi14,
        pct_from_52w_high=pct_hi,
        pct_from_52w_low=pct_lo,
        vol_ratio=vol_rat,
        atr_pct=atr_p,
        structure=structure,
    )

    # ── Final score ───────────────────────────────────────────────────
    # Patterns: Tier1 (≤35) + Tier2 (≤20) + Tier3 (≤15) = up to 70
    # Lagging:  Tier4 (≤30, can be negative)
    # Total cap: 100
    raw_score      = pat_summary.total_pattern_score + t4_score
    technical_score = round(max(0.0, min(100.0, raw_score)), 1)

    return {
        # Price info
        "current_price":          price,
        "week52_high":            round(w52_hi, 2),
        "week52_low":             round(w52_lo, 2),
        "pct_from_52w_high":      round(pct_hi, 2),
        "pct_from_52w_low":       round(pct_lo, 2),
        # Indicators
        "sma20":                  round(sma20,  2) if sma20  else None,
        "sma50":                  round(sma50,  2) if sma50  else None,
        "sma200":                 round(sma200, 2) if sma200 else None,
        "rsi14":                  round(rsi14,  2) if rsi14 is not None else None,
        "atr_pct":                round(atr_p,  2) if atr_p  is not None else None,
        "volume_ratio_10d_vs_50d": vol_rat,
        # Levels
        "support_levels":         levels["support"],
        "resistance_levels":      levels["resistance"],
        # Classification
        "trend":                  trend,
        "structure":              structure,
        # Score breakdown
        "tier1_score":            round(pat_summary.tier1_score, 1),
        "tier2_score":            round(pat_summary.tier2_score, 1),
        "tier3_score":            round(pat_summary.tier3_score, 1),
        "tier4_score":            t4_score,
        "tier4_breakdown":        t4_breakdown,
        "pattern_score":          round(pat_summary.total_pattern_score, 1),
        "technical_score":        technical_score,
        # Full pattern data for report
        "pattern_data":           pat_dict,
        "history_points_used":    len(df),
    }


def suggest_trade_setup(technical: Dict[str, Any]) -> Dict[str, Any]:
    price = technical.get("current_price")
    if price is None:
        return {}

    resistances = sorted(technical.get("resistance_levels", []))
    supports    = sorted(technical.get("support_levels", []))
    w52_hi      = technical.get("week52_high")
    sma50       = technical.get("sma50")
    atr_pct     = technical.get("atr_pct") or 2.5

    above = [r for r in resistances if r > price]
    breakout_trigger = (
        above[0] if above
        else (w52_hi if w52_hi and w52_hi > price else round(price * 1.05, 2))
    )

    below = [s for s in supports if s < price]
    if below:
        stop = below[-1]
    elif sma50 and sma50 < price:
        stop = round(sma50 * 0.985, 2)
    else:
        stop = round(price * (1 - (atr_pct * 1.8) / 100), 2)

    risk    = max(price - stop, 0.01)
    t1      = round(price + risk * 1.5, 2)
    t2      = round(price + risk * 3.0, 2)
    t3      = round(price + risk * 4.5, 2)
    rr      = round((t2 - price) / risk, 2) if risk else None
    exp_ret = round(((t2 - price) / price) * 100, 1)

    return {
        "current_price":       price,
        "entry_zone_low":      round(min(price, breakout_trigger) * 0.985, 2),
        "entry_zone_high":     round(price * 1.005, 2),
        "breakout_trigger":    round(breakout_trigger, 2),
        "stop_loss":           stop,
        "target1":             t1,
        "target2":             t2,
        "target3":             t3,
        "expected_return_pct": exp_ret,
        "risk_reward_ratio":   rr,
    }