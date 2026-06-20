"""
Pattern Detection Engine — VTrader Stock Analyser
==================================================

Detects price-action and candlestick patterns from daily OHLCV data.

Tier 1 — Price Structure      (max 35 pts) — LEADING signals
Tier 2 — Candlestick Context  (max 20 pts) — Timing signals
Tier 3 — Smart Money Concepts (max 15 pts) — Institutional footprint
Tier 4 — Lagging Confirmations(max 30 pts) — Confirmation only

Design principle:
  Price action and structure lead. Indicators confirm.
  A stock with great structure but lagging indicators = higher score
  than a stock with perfect RSI but broken structure.

Key: HH/HL after major correction scores HIGHEST (20 pts) because it
     catches a full new uptrend near the base — best risk:reward.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd


# ─────────────────────────────────────────────────────────────────────
# Data structures
# ─────────────────────────────────────────────────────────────────────

@dataclass
class PatternResult:
    name: str
    detected: bool
    confidence: str = "Low"           # Low / Medium / High / Very High
    score_contribution: float = 0.0
    description: str = ""
    details: Dict[str, Any] = field(default_factory=dict)


@dataclass
class PatternSummary:
    patterns: List[PatternResult] = field(default_factory=list)
    tier1_score: float = 0.0
    tier2_score: float = 0.0
    tier3_score: float = 0.0
    tier4_score: float = 0.0          # can be negative (penalties)
    total_pattern_score: float = 0.0
    strongest_pattern: Optional[str] = None
    pattern_narrative: str = ""


# ─────────────────────────────────────────────────────────────────────
# Shared utilities
# ─────────────────────────────────────────────────────────────────────

def _find_swing_pivots(
    df: pd.DataFrame,
    window: int = 5,
    lookback: int = 252,
) -> Tuple[List[dict], List[dict]]:
    recent = df.tail(lookback).reset_index(drop=True)
    highs, lows = [], []
    for i in range(window, len(recent) - window):
        seg_h = recent["high"].iloc[i - window: i + window + 1]
        seg_l = recent["low"].iloc[i - window: i + window + 1]
        if recent["high"].iloc[i] == seg_h.max():
            highs.append({
                "idx": i,
                "date": recent["date"].iloc[i],
                "price": float(recent["high"].iloc[i]),
                "volume": float(recent["volume"].iloc[i]),
            })
        if recent["low"].iloc[i] == seg_l.min():
            lows.append({
                "idx": i,
                "date": recent["date"].iloc[i],
                "price": float(recent["low"].iloc[i]),
                "volume": float(recent["volume"].iloc[i]),
            })
    return highs, lows


def _avg_volume(df: pd.DataFrame, period: int = 20) -> float:
    if len(df) < period:
        return float(df["volume"].mean()) if not df.empty else 1.0
    return float(df["volume"].tail(period).mean())


def _near_support(price: float, swing_lows: List[dict], tol_pct: float = 2.5) -> bool:
    return any(
        abs(price - l["price"]) / l["price"] * 100 <= tol_pct
        for l in swing_lows
    )


# ─────────────────────────────────────────────────────────────────────
# TIER 1 — Price Structure Patterns (max 35 pts)
# ─────────────────────────────────────────────────────────────────────

def detect_hh_hl_structure(df: pd.DataFrame) -> PatternResult:
    """
    Two-layer detection:
      Layer 1 — Context: 30%+ correction in last 18 months?
      Layer 2 — Structure: HH/HL pairs forming since the bottom?

    Scoring:
      Post-correction, early (2 pairs)  → 20 pts  ← highest in system
      Post-correction, established (3+) → 16 pts
      Post-correction, 1 pair only      → 10 pts
      Normal uptrend, 3+ pairs          → 10 pts
      Normal uptrend, 2 pairs           →  6 pts
      1 pair only                        →  2 pts
    """
    if df is None or len(df) < 60:
        return PatternResult("HH/HL Structure", False,
                             description="Insufficient history")

    swing_highs, swing_lows = _find_swing_pivots(df, window=5, lookback=252)
    if len(swing_highs) < 2 or len(swing_lows) < 2:
        return PatternResult("HH/HL Structure", False,
                             description="Not enough swing pivots")

    # Layer 1 — prior correction
    all_high = df.tail(378)["high"].max()
    peak_idx = df.tail(378)["high"].idxmax()
    trough_after = df.loc[peak_idx:, "low"].min() if peak_idx < len(df) - 1 else df["low"].min()
    drawdown_pct = ((all_high - trough_after) / all_high) * 100
    had_major_correction = drawdown_pct >= 30.0

    # Layer 2 — count HH/HL pairs after the bottom
    if had_major_correction:
        trough_idx = df.loc[peak_idx:, "low"].idxmin()
        bottom_date = df.loc[trough_idx, "date"] if trough_idx < len(df) else None
        if bottom_date:
            swing_highs = [h for h in swing_highs if h["date"] >= bottom_date]
            swing_lows  = [l for l in swing_lows  if l["date"] >= bottom_date]

    hh_count = sum(
        1 for i in range(1, len(swing_highs))
        if swing_highs[i]["price"] > swing_highs[i-1]["price"] * 1.005
    )
    hl_count = sum(
        1 for i in range(1, len(swing_lows))
        if swing_lows[i]["price"] > swing_lows[i-1]["price"] * 1.005
    )
    pairs = min(hh_count, hl_count)

    if pairs == 0:
        return PatternResult("HH/HL Structure", False,
                             description=f"No HH/HL pairs. Max drawdown was {drawdown_pct:.1f}%")

    # Scoring table
    if had_major_correction and pairs >= 3:
        score, conf = 16.0, "Very High"
        label = f"Established post-correction recovery (+{drawdown_pct:.0f}% drop, {pairs} HH/HL pairs)"
    elif had_major_correction and pairs == 2:
        score, conf = 20.0, "Very High"
        label = f"Early recovery after {drawdown_pct:.0f}% correction ({pairs} HH/HL forming) — best entry zone"
    elif had_major_correction and pairs == 1:
        score, conf = 10.0, "Medium"
        label = f"Possible recovery start after {drawdown_pct:.0f}% correction (1 HH/HL — wait for confirmation)"
    elif pairs >= 3:
        score, conf = 10.0, "High"
        label = f"Established uptrend ({pairs} HH/HL pairs — watch for late-stage entry risk)"
    elif pairs == 2:
        score, conf = 6.0, "Medium"
        label = f"Developing uptrend (2 HH/HL pairs)"
    else:
        score, conf = 2.0, "Low"
        label = "Single HH/HL — too early to confirm"

    last_hh = swing_highs[-1]["price"] if swing_highs else None
    last_hl = swing_lows[-1]["price"]  if swing_lows  else None

    return PatternResult(
        name="HH/HL Structure",
        detected=True,
        confidence=conf,
        score_contribution=score,
        description=label,
        details={
            "had_major_correction": had_major_correction,
            "max_drawdown_pct": round(drawdown_pct, 1),
            "confirmed_pairs": pairs,
            "last_swing_high": round(last_hh, 2) if last_hh else None,
            "last_swing_low":  round(last_hl, 2) if last_hl  else None,
        }
    )


def detect_double_bottom(df: pd.DataFrame) -> PatternResult:
    """
    Two lows within 3%, neckline rally 6%+, price near/above neckline.
    Confirmed (above neckline): 15 pts
    Forming (within 5% of neckline): 10 pts
    """
    if df is None or len(df) < 60:
        return PatternResult("Double Bottom", False, description="Insufficient history")

    _, swing_lows = _find_swing_pivots(df, window=5, lookback=200)
    if len(swing_lows) < 2:
        return PatternResult("Double Bottom", False, description="Not enough swing lows")

    current_price = float(df["close"].iloc[-1])
    best = None

    for i in range(len(swing_lows) - 1):
        for j in range(i + 1, len(swing_lows)):
            b1, b2 = swing_lows[i], swing_lows[j]
            if (b2["idx"] - b1["idx"]) < 10:
                continue
            diff_pct = abs(b2["price"] - b1["price"]) / b1["price"] * 100
            if diff_pct > 3.0:
                continue
            between  = df.iloc[b1["idx"]: b2["idx"] + 1]
            if between.empty:
                continue
            neckline = float(between["high"].max())
            rally    = (neckline - b1["price"]) / b1["price"] * 100
            if rally < 6.0:
                continue
            dist = (current_price - neckline) / neckline * 100
            if dist < -5.0:
                continue

            vol_exhaustion = b2["volume"] < b1["volume"] * 1.1
            confirmed      = dist >= 0

            score = 15.0 if confirmed else 10.0
            if vol_exhaustion: score += 1.0
            conf  = "High" if (confirmed and vol_exhaustion) else \
                    "High" if confirmed else "Medium"

            status = "above neckline - confirmed" if confirmed else f"{abs(dist):.1f}% below neckline - forming"
            candidate = {
                "score": score, "confidence": conf,
                "bottom1": b1["price"], "bottom2": b2["price"],
                "neckline": neckline, "rally_pct": rally,
                "dist_from_neckline": dist, "vol_exhaustion": vol_exhaustion,
                "status": status,
            }
            if best is None or score > best["score"]:
                best = candidate

    if best is None:
        return PatternResult("Double Bottom", False, description="No double bottom found")

    desc = (
        f"Double bottom at {best['bottom1']:.1f} & {best['bottom2']:.1f}, "
        f"neckline {best['neckline']:.1f} ({best['status']})"
    )
    return PatternResult(
        name="Double Bottom",
        detected=True,
        confidence=best["confidence"],
        score_contribution=best["score"],
        description=desc,
        details=best,
    )


def detect_choch(df: pd.DataFrame) -> PatternResult:
    """
    Change of Character: first HH after a series of Lower Highs.
    With volume + support test: 14 pts
    Without volume: 10 pts
    """
    if df is None or len(df) < 40:
        return PatternResult("ChoCh", False, description="Insufficient history")

    swing_highs, swing_lows = _find_swing_pivots(df, window=4, lookback=150)
    if len(swing_highs) < 3:
        return PatternResult("ChoCh", False, description="Not enough swing highs")

    avg_vol = _avg_volume(df, 20)
    current_price = float(df["close"].iloc[-1])
    recent_highs  = swing_highs[-4:]

    lh_count = sum(
        1 for i in range(1, len(recent_highs) - 1)
        if recent_highs[i]["price"] < recent_highs[i-1]["price"]
    )
    if lh_count < 1:
        return PatternResult("ChoCh", False, description="No prior Lower High sequence")

    last_high = recent_highs[-1]
    prev_high = recent_highs[-2]
    broke_lh  = last_high["price"] > prev_high["price"] * 1.005

    if not broke_lh:
        return PatternResult("ChoCh", False,
                             description="Last swing high has not broken prior Lower High yet")

    support_tested = any(l["idx"] < last_high["idx"] for l in swing_lows)
    vol_confirm    = last_high["volume"] > avg_vol * 1.15
    still_valid    = current_price > prev_high["price"] * 0.97

    if not still_valid:
        return PatternResult("ChoCh", False,
                             description="ChoCh occurred but price has reversed back below it")

    score = 14.0 if (vol_confirm and support_tested) else 10.0
    conf  = "Very High" if (vol_confirm and support_tested) else \
            "High" if (vol_confirm or support_tested) else "Medium"

    desc = (
        f"ChoCh: broke above Lower High {prev_high['price']:.1f} → new high {last_high['price']:.1f}"
        + (" | Volume ✓" if vol_confirm else "")
        + (" | Support tested ✓" if support_tested else "")
    )
    return PatternResult(
        name="ChoCh (Change of Character)",
        detected=True,
        confidence=conf,
        score_contribution=score,
        description=desc,
        details={
            "choch_level": round(last_high["price"], 2),
            "prior_lh": round(prev_high["price"], 2),
            "vol_confirm": vol_confirm,
            "support_tested": support_tested,
        }
    )


def detect_failed_breakdown(df: pd.DataFrame) -> PatternResult:
    """
    Price closes below support then recovers above it within 1-5 candles.
    With capitulation volume: 13 pts
    Without: 9 pts
    """
    if df is None or len(df) < 30:
        return PatternResult("Failed Breakdown", False, description="Insufficient history")

    _, swing_lows = _find_swing_pivots(df, window=5, lookback=120)
    if not swing_lows:
        return PatternResult("Failed Breakdown", False, description="No support levels")

    recent        = df.tail(30).reset_index(drop=True)
    avg_vol       = _avg_volume(df, 20)
    current_close = float(df["close"].iloc[-1])

    for support in swing_lows[-4:]:
        sup = support["price"]
        for i in range(5, len(recent) - 1):
            if recent["close"].iloc[i] < sup * 0.995:
                window = recent.iloc[i+1: i+6]
                if window.empty:
                    continue
                recovered = any(c > sup * 1.005 for c in window["close"])
                if recovered and current_close > sup:
                    vol_spike = recent["volume"].iloc[i] > avg_vol * 1.3
                    score = 13.0 if vol_spike else 9.0
                    conf  = "High" if vol_spike else "Medium"
                    return PatternResult(
                        name="Failed Breakdown (Bear Trap)",
                        detected=True,
                        confidence=conf,
                        score_contribution=score,
                        description=(
                            f"Price broke below support {sup:.1f} then recovered"
                            + (" with capitulation volume ✓" if vol_spike else "")
                        ),
                        details={"support_level": round(sup, 2), "vol_spike": vol_spike}
                    )

    return PatternResult("Failed Breakdown", False, description="No failed breakdown in recent bars")


# ─────────────────────────────────────────────────────────────────────
# TIER 2 — Candlestick Context Patterns (max 20 pts)
# ─────────────────────────────────────────────────────────────────────

def detect_bullish_engulfing(df: pd.DataFrame) -> PatternResult:
    """
    At support + volume: 12 pts
    At support, no volume: 8 pts
    Not at support: 2 pts
    """
    if df is None or len(df) < 20:
        return PatternResult("Bullish Engulfing", False, description="Insufficient history")

    _, swing_lows = _find_swing_pivots(df, window=5, lookback=120)
    avg_vol = _avg_volume(df, 20)

    for lb in range(1, 6):
        ic, ip = len(df) - lb, len(df) - lb - 1
        if ip < 0:
            continue
        prev, curr = df.iloc[ip], df.iloc[ic]
        po, pc = float(prev["open"]), float(prev["close"])
        co, cc = float(curr["open"]), float(curr["close"])

        prev_bear  = pc < po
        curr_bull  = cc > co
        full_engulf = co < pc and cc > po

        if prev_bear and curr_bull and full_engulf:
            at_sup  = _near_support(float(curr["low"]), swing_lows)
            vol_ok  = float(curr["volume"]) > avg_vol * 1.1

            if not at_sup:
                score, conf = 2.0, "Low"
                desc = "Bullish engulfing not at key support — low reliability"
            elif vol_ok:
                score, conf = 12.0, "High"
                desc = f"Bullish engulfing at support with volume ✓{' (' + str(lb) + ' bars ago)' if lb > 1 else ''}"
            else:
                score, conf = 8.0, "Medium"
                desc = f"Bullish engulfing at support (no volume confirmation){' (' + str(lb) + ' bars ago)' if lb > 1 else ''}"

            return PatternResult(
                name="Bullish Engulfing at Support",
                detected=True, confidence=conf,
                score_contribution=score, description=desc,
                details={"at_support": at_sup, "vol_confirm": vol_ok, "bars_ago": lb}
            )

    return PatternResult("Bullish Engulfing at Support", False,
                         description="No bullish engulfing in last 5 candles")


def detect_hammer_pin_bar(df: pd.DataFrame) -> PatternResult:
    """
    At support + volume: 11 pts
    At support, no volume: 7 pts
    Not at support: 2 pts
    """
    if df is None or len(df) < 20:
        return PatternResult("Hammer / Pin Bar", False, description="Insufficient history")

    _, swing_lows = _find_swing_pivots(df, window=5, lookback=120)
    avg_vol = _avg_volume(df, 20)

    for lb in range(1, 6):
        idx = len(df) - lb
        if idx < 0:
            continue
        c = df.iloc[idx]
        o, h, cl, l = float(c["open"]), float(c["high"]), float(c["close"]), float(c["low"])
        body        = abs(cl - o)
        total       = h - l
        lower_wick  = min(o, cl) - l
        upper_wick  = h - max(o, cl)
        if total < 0.001:
            continue

        is_hammer = (
            lower_wick >= body * 2.0
            and upper_wick <= body * 0.6
            and body / total <= 0.40
        )
        if not is_hammer:
            continue

        at_sup = _near_support(l, swing_lows)
        vol_ok = float(c["volume"]) > avg_vol * 1.15

        if not at_sup:
            score, conf = 2.0, "Low"
            desc = "Hammer not at key support — low reliability"
        elif vol_ok:
            score, conf = 11.0, "High"
            desc = f"Hammer/Pin Bar at support with rejection volume ✓{' (' + str(lb) + ' bars ago)' if lb > 1 else ''}"
        else:
            score, conf = 7.0, "Medium"
            desc = f"Hammer/Pin Bar at support (no volume){' (' + str(lb) + ' bars ago)' if lb > 1 else ''}"

        return PatternResult(
            name="Hammer / Pin Bar",
            detected=True, confidence=conf,
            score_contribution=score, description=desc,
            details={"at_support": at_sup, "vol_confirm": vol_ok,
                     "lower_wick_ratio": round(lower_wick / total, 2), "bars_ago": lb}
        )

    return PatternResult("Hammer / Pin Bar", False,
                         description="No hammer/pin bar in last 5 candles")


def detect_volume_climax(df: pd.DataFrame) -> PatternResult:
    """
    Huge volume red candle with long lower wick + price recovered after.
    At support: 10 pts | Not at support: 6 pts
    """
    if df is None or len(df) < 30:
        return PatternResult("Volume Climax", False, description="Insufficient history")

    avg_vol       = _avg_volume(df, 20)
    _, swing_lows = _find_swing_pivots(df, window=5, lookback=120)
    current_price = float(df["close"].iloc[-1])
    window        = df.tail(20).reset_index(drop=True)

    for i in range(len(window)):
        row = window.iloc[i]
        o, h, c, l = float(row["open"]), float(row["high"]), float(row["close"]), float(row["low"])
        vol   = float(row["volume"])
        total = h - l
        if total < 0.001:
            continue

        lower_wick  = min(o, c) - l
        is_red      = c < o
        vol_spike   = vol > avg_vol * 2.0
        long_wick   = (lower_wick / total) > 0.4
        recovered   = current_price > c * 1.02

        if is_red and vol_spike and long_wick and recovered:
            at_sup      = _near_support(l, swing_lows)
            bars_ago    = len(window) - i
            score       = 10.0 if at_sup else 6.0
            conf        = "High" if at_sup else "Medium"
            return PatternResult(
                name="Volume Climax / Selling Exhaustion",
                detected=True, confidence=conf,
                score_contribution=score,
                description=(
                    f"Volume climax {bars_ago} bar(s) ago at {l:.1f}"
                    + (" at support ✓" if at_sup else "")
                    + f" ({vol/avg_vol:.1f}x avg vol)"
                ),
                details={"at_support": at_sup, "vol_multiple": round(vol/avg_vol, 1),
                         "bars_ago": bars_ago}
            )

    return PatternResult("Volume Climax", False,
                         description="No volume climax in last 20 candles")


def detect_inside_bar(df: pd.DataFrame) -> PatternResult:
    """
    Compression candle. After strong directional move: 5 pts | Otherwise: 2 pts
    """
    if df is None or len(df) < 5:
        return PatternResult("Inside Bar", False, description="Insufficient history")

    for lb in range(1, 4):
        ic, ip = len(df) - lb, len(df) - lb - 1
        if ip < 0:
            continue
        curr, prev = df.iloc[ic], df.iloc[ip]
        is_inside = (
            float(curr["high"]) < float(prev["high"])
            and float(curr["low"]) > float(prev["low"])
        )
        if not is_inside:
            continue

        prev_body  = abs(float(prev["close"]) - float(prev["open"]))
        prev_range = float(prev["high"]) - float(prev["low"])
        strong_mb  = (prev_body / prev_range) > 0.5 if prev_range > 0 else False

        score = 5.0 if strong_mb else 2.0
        conf  = "Medium" if strong_mb else "Low"
        desc  = (
            "Inside bar after strong directional candle — compression before move ✓"
            if strong_mb else "Inside bar (weak mother bar — lower reliability)"
        )
        return PatternResult(
            name="Inside Bar (Compression)",
            detected=True, confidence=conf,
            score_contribution=score, description=desc,
            details={"strong_mother_bar": strong_mb, "bars_ago": lb}
        )

    return PatternResult("Inside Bar", False,
                         description="No inside bar in last 3 candles")


# ─────────────────────────────────────────────────────────────────────
# TIER 3 — Smart Money Concepts (max 15 pts)
# ─────────────────────────────────────────────────────────────────────

def detect_vcp(df: pd.DataFrame) -> PatternResult:
    """
    Volatility Contraction Pattern — tightest coil before breakout.
    4+ contractions + volume contraction: 15 pts
    3 contractions + volume contraction: 12 pts
    Contractions only, no volume:         8 pts
    """
    if df is None or len(df) < 60:
        return PatternResult("VCP", False, description="Insufficient history")

    recent = df.tail(120).reset_index(drop=True)
    swing_highs, swing_lows = _find_swing_pivots(recent, window=4, lookback=120)

    if len(swing_highs) < 3 or len(swing_lows) < 3:
        return PatternResult("VCP", False, description="Not enough swing pivots")

    all_pivots = sorted(swing_highs + swing_lows, key=lambda x: x["idx"])
    swings = []
    for i in range(1, len(all_pivots)):
        amp  = abs(all_pivots[i]["price"] - all_pivots[i-1]["price"])
        avgp = (all_pivots[i]["price"] + all_pivots[i-1]["price"]) / 2
        avgv = (all_pivots[i]["volume"] + all_pivots[i-1]["volume"]) / 2
        swings.append({
            "amp_pct": (amp / avgp) * 100,
            "avg_vol": avgv,
        })

    if len(swings) < 3:
        return PatternResult("VCP", False, description="Not enough swings for VCP")

    check = swings[-4:]
    contracting_amp = all(
        check[i]["amp_pct"] < check[i-1]["amp_pct"] * 0.9
        for i in range(1, len(check))
    )
    contracting_vol = all(
        check[i]["avg_vol"] < check[i-1]["avg_vol"] * 1.1
        for i in range(1, len(check))
    )

    if not contracting_amp:
        return PatternResult("VCP", False,
                             description="Price swings not contracting — no VCP")

    n = len(check)
    latest_amp = check[-1]["amp_pct"]

    if n >= 4 and contracting_vol:
        score, conf = 15.0, "Very High"
    elif contracting_vol:
        score, conf = 12.0, "High"
    else:
        score, conf = 8.0, "Medium"

    desc = (
        f"VCP: {n} contracting swings, latest amplitude {latest_amp:.1f}%"
        + (" | Volume also contracting ✓" if contracting_vol else " | Volume not yet confirming")
    )
    return PatternResult(
        name="VCP (Volatility Contraction Pattern)",
        detected=True, confidence=conf,
        score_contribution=score, description=desc,
        details={"contractions": n, "latest_amp_pct": round(latest_amp, 1),
                 "vol_contracting": contracting_vol}
    )


def detect_order_block(df: pd.DataFrame) -> PatternResult:
    """
    Last bearish candle before a 3%+ impulse move.
    Price currently inside the OB zone.
    Bearish OB body: 10 pts | Bullish OB body: 6 pts
    """
    if df is None or len(df) < 30:
        return PatternResult("Order Block", False, description="Insufficient history")

    current_price = float(df["close"].iloc[-1])
    recent        = df.tail(120).reset_index(drop=True)
    candidates    = []

    for i in range(2, len(recent) - 3):
        c  = float(recent["close"].iloc[i])
        m1 = (float(recent["close"].iloc[i+1]) - c) / c * 100
        m2 = (float(recent["close"].iloc[min(i+2, len(recent)-1)]) - c) / c * 100
        m3 = (float(recent["close"].iloc[min(i+3, len(recent)-1)]) - c) / c * 100
        if max(m1, m2, m3) >= 3.0:
            row = recent.iloc[i]
            candidates.append({
                "ob_high":     float(row["high"]),
                "ob_low":      float(row["low"]),
                "move_pct":    max(m1, m2, m3),
                "bearish_body": float(row["close"]) < float(row["open"]),
                "idx": i,
            })

    if not candidates:
        return PatternResult("Order Block", False,
                             description="No impulsive moves found to anchor order blocks")

    for ob in reversed(candidates):
        if ob["ob_low"] <= current_price <= ob["ob_high"]:
            score = 10.0 if ob["bearish_body"] else 6.0
            desc  = (
                f"Price testing OB zone {ob['ob_low']:.1f}–{ob['ob_high']:.1f} "
                f"(preceded a {ob['move_pct']:.1f}% impulse)"
                + (" | Bearish OB = stronger institutional zone ✓" if ob["bearish_body"] else "")
            )
            return PatternResult(
                name="Order Block",
                detected=True, confidence="High",
                score_contribution=score, description=desc,
                details={"ob_high": round(ob["ob_high"], 2),
                         "ob_low": round(ob["ob_low"], 2),
                         "impulse_pct": round(ob["move_pct"], 1),
                         "bearish_body": ob["bearish_body"]}
            )

    nearest = min(candidates, key=lambda x: abs((x["ob_high"]+x["ob_low"])/2 - current_price))
    dist    = (current_price - nearest["ob_high"]) / nearest["ob_high"] * 100
    return PatternResult(
        name="Order Block", detected=False, confidence="Low", score_contribution=0,
        description=(
            f"Nearest OB zone {nearest['ob_low']:.1f}–{nearest['ob_high']:.1f} "
            f"({dist:+.1f}% from current price — not in zone yet)"
        ),
        details={"nearest_ob_high": round(nearest["ob_high"], 2),
                 "nearest_ob_low": round(nearest["ob_low"], 2),
                 "distance_pct": round(dist, 1)}
    )


# ─────────────────────────────────────────────────────────────────────
# TIER 4 — Lagging Confirmations (scored in technical.py)
# These are computed from indicators, not patterns.
# Returned as a separate dict for transparency in the report.
# ─────────────────────────────────────────────────────────────────────

def compute_lagging_score(
    trend: str,
    rsi14: Optional[float],
    pct_from_52w_high: float,
    pct_from_52w_low: float,
    vol_ratio: Optional[float],
    atr_pct: Optional[float],
    structure: str,
) -> Tuple[float, List[dict]]:
    """
    Returns (score, breakdown_list).
    Score can be negative (penalties).
    Max contribution: +30. No hard floor — penalties can reduce total score.
    """
    score    = 0.0
    breakdown = []

    def add(label, pts, reason):
        nonlocal score
        score += pts
        breakdown.append({"signal": label, "points": pts, "reason": reason})

    # SMA trend alignment
    if trend == "Uptrend":
        add("SMA Trend", 8, "Price > SMA50 > SMA200 — full trend alignment")
    elif "Early Recovery" in trend:
        add("SMA Trend", 5, "Price > SMA200 but SMA50 below — partial recovery")
    elif trend == "Downtrend":
        add("SMA Trend", -10, "Price < SMA50 < SMA200 — against all moving averages")
    else:
        add("SMA Trend", 0, "Sideways / mixed — no trend signal")

    # RSI
    if rsi14 is not None:
        if 45 <= rsi14 <= 65:
            add("RSI", 6, f"RSI {rsi14:.1f} in healthy range (45–65)")
        elif 30 <= rsi14 < 45:
            add("RSI", 4, f"RSI {rsi14:.1f} oversold recovery zone — valid at bottoms")
        elif rsi14 > 72:
            add("RSI", -8, f"RSI {rsi14:.1f} overbought — risky entry point")
        elif rsi14 < 25:
            add("RSI", -5, f"RSI {rsi14:.1f} very oversold — no recovery signal yet")
        else:
            add("RSI", 0, f"RSI {rsi14:.1f} neutral zone")

    # 52-week position
    if -25 <= pct_from_52w_high <= -5:
        add("52W Position", 6, f"{pct_from_52w_high:.1f}% below 52W high — sweet spot (room to run)")
    elif -5 < pct_from_52w_high <= 0:
        add("52W Position", 3, "Near 52W high — breakout zone, watch for extension")
    elif pct_from_52w_high < -40:
        add("52W Position", -3, f"{pct_from_52w_high:.1f}% below 52W high — deep value or broken trend")

    if pct_from_52w_low < 8:
        add("52W Low Proximity", -5, "Within 8% of 52W low — price near bottom, high risk")

    # Volume ratio
    if vol_ratio is not None:
        base_structures = (
            "Base Building", "Near Breakout", "Pullback Within Uptrend",
            "Post-Correction"
        )
        on_base = any(s in structure for s in base_structures)
        if vol_ratio >= 1.15 and on_base:
            add("Volume", 4, f"Rising volume ({vol_ratio:.1f}x) during base/recovery — accumulation signal")
        elif vol_ratio >= 1.15 and "Extended" in structure:
            add("Volume", -4, f"Rising volume ({vol_ratio:.1f}x) on extended stock — distribution risk")
        elif vol_ratio <= 0.75 and "Downtrend" in structure:
            add("Volume", -2, "Falling volume in downtrend — no buyers")

    # ATR / compression
    if atr_pct is not None and atr_pct < 2.5:
        add("ATR Compression", 3, f"ATR {atr_pct:.1f}% — tight range, coiling for a move")

    # Cap at 30
    score = min(score, 30.0)

    return round(score, 1), breakdown


# ─────────────────────────────────────────────────────────────────────
# Master runner
# ─────────────────────────────────────────────────────────────────────

TIER1 = [detect_hh_hl_structure, detect_double_bottom, detect_choch, detect_failed_breakdown]
TIER2 = [detect_bullish_engulfing, detect_hammer_pin_bar, detect_volume_climax, detect_inside_bar]
TIER3 = [detect_vcp, detect_order_block]

TIER1_CAP = 35.0
TIER2_CAP = 20.0
TIER3_CAP = 15.0


def run_all_patterns(df: pd.DataFrame) -> PatternSummary:
    summary = PatternSummary()

    if df is None or df.empty:
        summary.pattern_narrative = "No price history available."
        return summary

    for fn, tier, cap_attr in [
        *[(f, 1, "tier1_score") for f in TIER1],
        *[(f, 2, "tier2_score") for f in TIER2],
        *[(f, 3, "tier3_score") for f in TIER3],
    ]:
        try:
            r = fn(df)
            summary.patterns.append(r)
            if r.detected:
                setattr(summary, cap_attr,
                        getattr(summary, cap_attr) + r.score_contribution)
        except Exception as e:
            summary.patterns.append(
                PatternResult(fn.__name__, False, description=f"Error: {e}")
            )

    summary.tier1_score = min(summary.tier1_score, TIER1_CAP)
    summary.tier2_score = min(summary.tier2_score, TIER2_CAP)
    summary.tier3_score = min(summary.tier3_score, TIER3_CAP)
    summary.total_pattern_score = (
        summary.tier1_score + summary.tier2_score + summary.tier3_score
    )

    detected = [p for p in summary.patterns if p.detected]
    if detected:
        summary.strongest_pattern = max(detected, key=lambda p: p.score_contribution).name

    summary.pattern_narrative = _build_narrative(summary)
    return summary


def _build_narrative(s: PatternSummary) -> str:
    detected  = [p for p in s.patterns if p.detected]
    high_conf = [p for p in detected if p.confidence in ("High", "Very High")]

    if not detected:
        return ("No significant price-action patterns detected. "
                "Stock may be directionless or require more history.")
    if len(high_conf) >= 3:
        names = ", ".join(p.name for p in high_conf[:3])
        return (f"Strong pattern confluence: {names}. "
                f"Multiple high-confidence signals align — significantly elevated probability "
                f"of a directional move. Pattern contribution: +{s.total_pattern_score:.0f} pts.")
    if len(high_conf) >= 1:
        p = high_conf[0]
        others = [x.name for x in detected if x != p][:2]
        return (f"Primary: {p.name} ({p.confidence}) — {p.description}. "
                + (f"Supporting: {', '.join(others)}. " if others else "")
                + f"Pattern contribution: +{s.total_pattern_score:.0f} pts.")
    return (f"Weak signals only: {', '.join(p.name for p in detected[:3])}. "
            f"None with high confidence — wait for clearer confirmation.")


def pattern_summary_to_dict(summary: PatternSummary) -> dict:
    return {
        "patterns": [
            {
                "name": p.name,
                "detected": p.detected,
                "confidence": p.confidence,
                "score_contribution": p.score_contribution,
                "description": p.description,
                "details": p.details,
            }
            for p in summary.patterns
        ],
        "tier1_score": summary.tier1_score,
        "tier2_score": summary.tier2_score,
        "tier3_score": summary.tier3_score,
        "total_pattern_score": summary.total_pattern_score,
        "strongest_pattern": summary.strongest_pattern,
        "pattern_narrative": summary.pattern_narrative,
    }


# type hint for compute_lagging_score
from typing import Optional, Tuple, List