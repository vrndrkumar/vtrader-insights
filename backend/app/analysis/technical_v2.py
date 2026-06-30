"""
analysis/technical_v2.py — Technical Scoring Engine v3 (CORRECTED)

CRITICAL FIX FROM v2: The previous version had a backwards MACD recency
bug — it scored crosses that had HELD LONGER as more "confirmed" and
therefore higher-scoring, which structurally favored stocks that had
ALREADY moved over stocks that were freshly turning. This is the
opposite of the user's explicit requirement to find stocks "about to
blast," and was the root cause of the system recommending
already-blasted stocks instead of pre-move setups.

v3 implements the user's exact specification, verified via isolated
unit tests (see conversation history):
  - Daily: bullish cross within last 6 DAYS qualifies (recency, not duration)
  - Weekly: bullish cross within last 4 WEEKS, or below-signal-but-rising
  - Monthly: bullish cross within last 2 MONTHS, or below-signal-but-rising
  - Zone tiers (user's explicit ranking, verified correct in tests):
      #1 near-zero cross = STRONGEST (fresh momentum shift)
      #2 far-below-zero cross = SECOND (deep reversal potential)
      #3 far-above-zero cross = WEAKEST of the three (already trending)
  - Stocks with NO qualifying timeframe score 0 on this component —
    correctly excluding "already ran, no fresh signal" stocks

COMPONENTS:
  1. Weekly Base Quality       (0-30 pts) — unchanged from v2
  2. Breakout Position         (0-25 pts) — unchanged from v2
  3. MACD Multi-Timeframe      (0-25 pts) — REBUILT per spec above
  4. Relative Strength Line    (0-10 pts) — unchanged, already correct
  5. Weekly Volume Signature   (0-10 pts) — unchanged from v2
  + Disqualifiers (hard caps)

NOT YET IMPLEMENTED (confirmed still pending, flagged explicitly):
  - News/sentiment scoring — deferred, no infrastructure built
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from typing import Any, Dict, List, Optional, Tuple


# ─────────────────────────────────────────────────────────────────────────────
# Core indicator math
# ─────────────────────────────────────────────────────────────────────────────

def _ema(series: pd.Series, n: int) -> pd.Series:
    return series.ewm(span=n, adjust=False).mean()


def _rsi(series: pd.Series, n: int = 14) -> pd.Series:
    delta = series.diff()
    gain  = delta.clip(lower=0)
    loss  = (-delta.clip(upper=0))
    avg_g = gain.ewm(alpha=1/n, adjust=False).mean()
    avg_l = loss.ewm(alpha=1/n, adjust=False).mean()
    rs    = avg_g / avg_l.replace(0, np.nan)
    return (100 - 100 / (1 + rs)).fillna(100)


def _macd(series: pd.Series, fast=12, slow=26, sig=9
         ) -> Tuple[pd.Series, pd.Series, pd.Series]:
    ml = _ema(series, fast) - _ema(series, slow)
    sl = _ema(ml, sig)
    return ml, sl, ml - sl


def _is_rising(series: pd.Series, lookback: int = 3) -> bool:
    if len(series) <= lookback:
        return False
    return float(series.iloc[-1]) > float(series.iloc[-lookback - 1])


# ─────────────────────────────────────────────────────────────────────────────
# COMPONENT 1 — Weekly Base Quality (0-30 pts)  [unchanged from v2]
# ─────────────────────────────────────────────────────────────────────────────

def _detect_stage(weekly_close: pd.Series) -> Tuple[int, str]:
    if len(weekly_close) < 30:
        return 1, "Stage 1 (Insufficient history)"

    e50   = _ema(weekly_close, min(50, len(weekly_close)))
    price = float(weekly_close.iloc[-1])
    e50_now  = float(e50.iloc[-1])
    e50_4wk  = float(e50.iloc[-5]) if len(e50) >= 5 else e50_now
    slope    = (e50_now - e50_4wk) / e50_4wk * 100
    high_26w = float(weekly_close.tail(26).max()) if len(weekly_close) >= 26 else price
    pct_from_high = (price - high_26w) / high_26w * 100

    if price > e50_now and slope > 0.3:
        return 2, "Stage 2 (Uptrend)"
    if price > e50_now and (slope <= 0 or pct_from_high < -10):
        return 3, "Stage 3 (Distribution)"
    if price < e50_now and slope < -0.3:
        return 4, "Stage 4 (Decline)"
    return 1, "Stage 1 (Accumulation)"


def _score_base_quality(weekly_df: pd.DataFrame) -> Tuple[float, int, float, str]:
    if len(weekly_df) < 8:
        return 0, 0, 100, "Insufficient weekly data"

    closes = weekly_df["close"].values
    highs  = weekly_df["high"].values
    lows   = weekly_df["low"].values

    best_weeks = 0
    best_range = 100.0

    for lookback in [52, 40, 26, 16, 12, 8]:
        if len(closes) < lookback:
            continue
        wc = closes[-lookback:]
        wh = highs[-lookback:]
        wl = lows[-lookback:]
        rng = (max(wh) - min(wl)) / np.mean(wc) * 100
        if rng < 35:
            for wks in range(lookback, 3, -1):
                c = closes[-wks:]
                h = highs[-wks:]
                l = lows[-wks:]
                r = (max(h) - min(l)) / np.mean(c) * 100
                if r < 30:
                    best_weeks = wks
                    best_range = r
                    break
            if best_weeks > 0:
                break

    if best_weeks < 4:
        return 0, 0, 100, "No base detected (wide/choppy price action)"

    weeks_score = (
        10 if best_weeks >= 52 else
        9  if best_weeks >= 32 else
        8  if best_weeks >= 26 else
        7  if best_weeks >= 16 else
        5  if best_weeks >= 12 else
        3  if best_weeks >= 8  else 1
    )

    tight_score = (
        10 if best_range < 8  else
        8  if best_range < 12 else
        6  if best_range < 18 else
        4  if best_range < 25 else 1
    )

    vcp_score = 0
    best_range_desc = f"{best_weeks}wk base, range {best_range:.1f}%"
    if best_weeks >= 9:
        seg = best_weeks // 3
        segs = [
            closes[-best_weeks          : -best_weeks + seg],
            closes[-best_weeks + seg    : -best_weeks + 2*seg],
            closes[-best_weeks + 2*seg  :],
        ]
        ranges = []
        for s in segs:
            if len(s) > 0:
                avg = np.mean(s)
                r   = (max(s) - min(s)) / avg * 100 if avg else 0
                ranges.append(r)
        if len(ranges) == 3 and ranges[0] > ranges[1] > ranges[2] and ranges[2] < 10:
            vcp_score = 10
            best_range_desc = f"{best_weeks}wk VCP — ranges {ranges[0]:.1f}%→{ranges[1]:.1f}%→{ranges[2]:.1f}%"
        elif len(ranges) >= 2 and ranges[0] > ranges[-1]:
            vcp_score = 5
            best_range_desc = f"{best_weeks}wk contracting base"

    total = weeks_score + tight_score + vcp_score
    return min(float(total), 20.0), best_weeks, best_range, best_range_desc


def score_weekly_base(weekly_df: pd.DataFrame) -> Dict[str, Any]:
    if weekly_df is None or len(weekly_df) < 8:
        return {"score": 0, "stage": 1, "stage_label": "Stage 1", "base_weeks": 0,
                "base_range_pct": 100, "base_desc": "No data", "notes": []}

    close = weekly_df["close"]
    stage_n, stage_label = _detect_stage(close)
    stage_score = {1: 10, 2: 6, 3: 0, 4: 0}.get(stage_n, 0)

    base_score, base_weeks, base_range, base_desc = _score_base_quality(weekly_df)
    total = min(stage_score + base_score, 30.0)

    notes = [f"Stage: {stage_label}", f"Base: {base_desc}"]
    if stage_n in [3, 4]:
        notes.append(f"⚠ {stage_label} — disqualifier will cap final score")

    return {
        "score": round(total, 1), "stage": stage_n, "stage_label": stage_label,
        "base_weeks": base_weeks, "base_range_pct": round(base_range, 1),
        "base_desc": base_desc, "notes": notes,
    }


# ─────────────────────────────────────────────────────────────────────────────
# COMPONENT 2 — Breakout Position (0-25 pts)  [unchanged from v2]
# ─────────────────────────────────────────────────────────────────────────────

def score_breakout_position(weekly_df: pd.DataFrame,
                             monthly_df: pd.DataFrame) -> Dict[str, Any]:
    if weekly_df is None or len(weekly_df) < 26:
        return {"score": 10, "pct_from_52w_high": 0, "multi_yr_breakout": False,
                "swing_highs_above": 0, "notes": ["Insufficient weekly data"]}

    close_w  = weekly_df["close"].values
    high_w   = weekly_df["high"].values
    current  = float(close_w[-1])

    high_52w     = float(max(high_w[-52:])) if len(high_w) >= 52 else float(max(high_w))
    pct_from_52w = (current - high_52w) / high_52w * 100

    multi_yr_score = 0
    multi_yr       = False
    if monthly_df is not None and len(monthly_df) >= 24:
        highs_m  = monthly_df["high"].values
        high_2yr = float(max(highs_m[-24:]))
        high_3yr = float(max(highs_m)) if len(highs_m) >= 36 else high_2yr
        if current >= high_2yr * 0.98:
            multi_yr       = True
            multi_yr_score = 6
        if current >= high_3yr * 0.98:
            multi_yr_score = 8

    wk52_score = (
        10 if pct_from_52w >= -1  else
        9  if pct_from_52w >= -3  else
        7  if pct_from_52w >= -7  else
        5  if pct_from_52w >= -12 else
        3  if pct_from_52w >= -20 else 0
    )

    swing_highs = 0
    hw = high_w[-52:] if len(high_w) >= 52 else high_w
    for i in range(1, len(hw) - 1):
        h = hw[i]
        if current * 1.02 < h < current * 1.20:
            if h > hw[i-1] and h > hw[i+1]:
                swing_highs += 1

    res_score = (
        7 if swing_highs == 0 else
        5 if swing_highs <= 2 else
        3 if swing_highs <= 4 else 0
    )

    total = min(wk52_score + multi_yr_score + res_score, 25.0)

    notes = [f"Price vs 52W high: {pct_from_52w:+.1f}%"]
    if multi_yr:
        notes.append("Breaking multi-year high — price discovery zone")
    if swing_highs == 0:
        notes.append("No overhead resistance within 20% — clear path upward")
    elif swing_highs >= 5:
        notes.append(f"⚠ Heavy resistance — {swing_highs} swing highs above")

    return {
        "score": round(total, 1), "pct_from_52w_high": round(pct_from_52w, 1),
        "multi_yr_breakout": multi_yr, "swing_highs_above": swing_highs, "notes": notes,
    }


# ─────────────────────────────────────────────────────────────────────────────
# COMPONENT 3 — MACD Multi-Timeframe (0-25 pts)  [REBUILT — v3 corrected]
# ─────────────────────────────────────────────────────────────────────────────

def _bars_since_cross(macd_line: pd.Series, signal_line: pd.Series, max_lookback: int) -> Optional[int]:
    """
    Returns how many bars AGO the most recent bullish crossover happened,
    within max_lookback bars. None if no cross found in that window.
    This is RECENCY (how long ago), not DURATION (how long it's held) —
    the critical distinction that v2 got backwards.
    """
    diff = (macd_line - signal_line).values
    n = len(diff)
    for bars_ago in range(0, min(max_lookback, n - 1)):
        idx = n - 1 - bars_ago
        if idx < 1:
            break
        if diff[idx - 1] <= 0 and diff[idx] > 0:
            return bars_ago
    return None


def _zone_tier(ml_now: float, sl_now: float, recent_range: float) -> str:
    """
    User's explicit ranking (verified via unit test):
      near_zero > far_below_zero > far_above_zero
    """
    if recent_range == 0:
        recent_range = abs(ml_now) or 1.0
    avg_level = (ml_now + sl_now) / 2
    distance_pct = abs(avg_level) / recent_range
    if distance_pct < 0.15:
        return "near_zero"
    elif avg_level < 0:
        return "far_below_zero"
    else:
        return "far_above_zero"


def score_macd_timeframe_v3(close: pd.Series, label: str,
                             recency_lookback_bars: int,
                             rising_lookback: int = 3) -> Tuple[float, Dict[str, Any]]:
    """
    Per-timeframe MACD scoring matching user's exact spec:
      Qualifies if: (A) bullish cross within recency_lookback_bars bars ago,
                 OR (B) below signal but MACD line is rising (about to cross)
      Score = recency-scaled base + zone-tier bonus
    """
    if len(close) < 35:
        return 0.0, {"error": f"Insufficient {label} data", "qualifies": False}

    ml, sl, hist = _macd(close)
    ml_now, sl_now = float(ml.iloc[-1]), float(sl.iloc[-1])
    is_bullish_now = ml_now > sl_now

    bars_ago = _bars_since_cross(ml, sl, max_lookback=recency_lookback_bars)
    fresh_cross = bars_ago is not None

    ml_rising = _is_rising(ml, lookback=rising_lookback)
    about_to_cross = (not is_bullish_now) and ml_rising

    qualifies = fresh_cross or about_to_cross

    window = ml.tail(60) if len(ml) >= 60 else ml
    recent_range = float(window.abs().max()) if len(window) else abs(ml_now)
    zone = _zone_tier(ml_now, sl_now, recent_range)

    notes = []
    if not qualifies:
        notes.append(f"{label}: No recent cross within window, not approaching cross — does not qualify")
        return 0.0, {
            "label": label, "qualifies": False, "is_bullish": is_bullish_now,
            "bars_ago": bars_ago, "about_to_cross": about_to_cross,
            "zone": zone, "ml_now": round(ml_now, 4), "sl_now": round(sl_now, 4),
            "notes": notes,
        }

    if fresh_cross:
        recency_factor = 1.0 - (bars_ago / max(recency_lookback_bars, 1)) * 0.4
        base = 14 * recency_factor
        notes.append(f"{label}: Fresh bullish cross {bars_ago} bar(s) ago")
    else:
        base = 9.0
        notes.append(f"{label}: Below signal but MACD line rising — approaching cross")

    if zone == "near_zero":
        zone_bonus = 8
        notes.append(f"{label}: Near zero line — strongest zone (fresh momentum shift) +8")
    elif zone == "far_below_zero":
        zone_bonus = 5
        notes.append(f"{label}: Far below zero — deep reversal potential +5")
    elif zone == "far_above_zero":
        zone_bonus = 2
        notes.append(f"{label}: Far above zero — already established trend +2")
    else:
        zone_bonus = 4
        notes.append(f"{label}: Mid-zone +4")

    score = base + zone_bonus
    return round(score, 1), {
        "label": label, "qualifies": True, "is_bullish": is_bullish_now,
        "bars_ago": bars_ago, "about_to_cross": about_to_cross, "zone": zone,
        "ml_now": round(ml_now, 4), "sl_now": round(sl_now, 4), "notes": notes,
    }


def score_macd_multi_tf(daily_df: Optional[pd.DataFrame],
                         weekly_df: Optional[pd.DataFrame],
                         monthly_df: Optional[pd.DataFrame]) -> Dict[str, Any]:
    """
    Component 3 — corrected per user spec:
      Daily:   cross within last 6 DAYS, or about-to-cross
      Weekly:  cross within last 4 WEEKS, or about-to-cross
      Monthly: cross within last 2 MONTHS, or about-to-cross
    A stock with NO qualifying timeframe scores 0 here.
    """
    daily_close   = daily_df["close"]   if daily_df   is not None and len(daily_df)   >= 35 else pd.Series(dtype=float)
    weekly_close  = weekly_df["close"]  if weekly_df  is not None and len(weekly_df)  >= 30 else pd.Series(dtype=float)
    monthly_close = monthly_df["close"] if monthly_df is not None and len(monthly_df) >= 30 else pd.Series(dtype=float)

    d_score, d_info = (0.0, {"qualifies": False}) if len(daily_close) < 35 else \
        score_macd_timeframe_v3(daily_close, "Daily", recency_lookback_bars=6)

    wk_score, wk_info = (0.0, {"qualifies": False}) if len(weekly_close) < 30 else \
        score_macd_timeframe_v3(weekly_close, "Weekly", recency_lookback_bars=4)

    mo_score, mo_info = (0.0, {"qualifies": False}) if len(monthly_close) < 30 else \
        score_macd_timeframe_v3(monthly_close, "Monthly", recency_lookback_bars=2)

    qualifying_count = sum([
        d_info.get("qualifies", False),
        wk_info.get("qualifies", False),
        mo_info.get("qualifies", False),
    ])

    alignment_bonus = 10 if qualifying_count == 3 else 5 if qualifying_count == 2 else 0

    raw_total = d_score + wk_score + mo_score + alignment_bonus
    normalized = max(0.0, min(25.0, raw_total * 25.0 / 76.0))

    all_notes = d_info.get("notes", []) + wk_info.get("notes", []) + mo_info.get("notes", [])
    if alignment_bonus:
        all_notes.append(f"★ {qualifying_count} timeframes qualifying simultaneously +{alignment_bonus}")

    no_fresh_signal = qualifying_count == 0
    if no_fresh_signal:
        all_notes.append("⚠ No fresh MACD signal on any timeframe — stock may have already moved or has no momentum trigger")

    return {
        "score": round(normalized, 1), "raw": round(raw_total, 1),
        "daily": d_info, "weekly": wk_info, "monthly": mo_info,
        "qualifying_timeframes": qualifying_count, "alignment_bonus": alignment_bonus,
        "no_fresh_signal": no_fresh_signal,
        # Backward-compat keys some callers may read
        "monthly_macd_bull": mo_info.get("is_bullish", False),
        "weekly_macd_bull": wk_info.get("is_bullish", False),
        "cap_reversal": False,
        "is_monthly_bearish_disqualifier": False,
        "notes": all_notes,
    }


# ─────────────────────────────────────────────────────────────────────────────
# COMPONENT 4 — Relative Strength Line (0-10 pts)  [unchanged — already correct]
# ─────────────────────────────────────────────────────────────────────────────

def score_rs_line(weekly_df: pd.DataFrame, nifty_weekly_df: pd.DataFrame) -> Dict[str, Any]:
    if (weekly_df is None or len(weekly_df) < 12 or
            nifty_weekly_df is None or len(nifty_weekly_df) < 12):
        return {"score": 4, "state": "Insufficient data", "notes": []}

    min_len = min(len(weekly_df), len(nifty_weekly_df))
    stock_c = weekly_df["close"].values[-min_len:]
    nifty_c = nifty_weekly_df["close"].values[-min_len:]
    rs = stock_c / nifty_c

    rs_now  = rs[-1]
    rs_4w   = rs[-4]  if len(rs) >= 4  else rs[0]
    rs_12w  = rs[-12] if len(rs) >= 12 else rs[0]
    rs_52h  = max(rs[-52:]) if len(rs) >= 52 else max(rs)
    pct_from_rs_high = (rs_now - rs_52h) / rs_52h * 100

    rising_4w   = rs_now > rs_4w
    rising_12w  = rs_now > rs_12w
    at_new_high = rs_now >= rs_52h * 0.98

    if at_new_high:
        score, state = 10, "RS at new 52W high — stock beating market strongly"
    elif rising_4w and rising_12w:
        score, state = 8, "RS rising on 4W and 12W basis"
    elif rising_4w:
        score, state = 6, "RS rising short-term (4W)"
    elif rising_12w:
        score, state = 5, "RS rising medium-term (12W), short-term dip"
    elif not rising_4w and not rising_12w:
        score, state = 0, "RS declining on both 4W and 12W — stock underperforming"
    else:
        score, state = 3, "RS mixed signals"

    return {
        "score": score, "state": state, "rs_now": round(float(rs_now), 6),
        "pct_from_rs_high": round(pct_from_rs_high, 1),
        "rising_4w": rising_4w, "rising_12w": rising_12w, "at_new_high": at_new_high,
        "notes": [state],
    }


# ─────────────────────────────────────────────────────────────────────────────
# COMPONENT 5 — Weekly Volume Signature (0-10 pts)  [unchanged from v2]
# ─────────────────────────────────────────────────────────────────────────────

def score_weekly_volume(weekly_df: pd.DataFrame, base_weeks: int) -> Dict[str, Any]:
    if weekly_df is None or len(weekly_df) < 12 or base_weeks < 4:
        return {"score": 3, "pattern": "Insufficient data", "notes": []}

    vols   = np.array(weekly_df["volume"].values, dtype=float)
    closes = np.array(weekly_df["close"].values,  dtype=float)

    base_start = max(0, len(vols) - base_weeks)
    base_vols  = vols[base_start:]
    prior_vols = vols[max(0, base_start - 52):base_start] if base_start >= 4 else vols[:base_start]
    recent_4w  = vols[-4:]

    if len(prior_vols) < 4:
        return {"score": 3, "pattern": "Insufficient prior volume", "notes": []}

    base_avg   = float(np.mean(base_vols))
    prior_avg  = float(np.mean(prior_vols))
    recent_avg = float(np.mean(recent_4w))

    vol_declining_in_base = base_avg < prior_avg * 0.70
    vol_explosion_now     = recent_avg > prior_avg * 2.5
    vol_building_now      = recent_avg > prior_avg * 1.5

    cap_spike = False
    reversal_after = False
    for i in range(-8, -1):
        if abs(i) > len(vols): continue
        if vols[i] > prior_avg * 5:
            cap_spike = True
            if abs(i+1) <= len(closes):
                reversal_after = closes[i+1] > closes[i]
            else:
                reversal_after = True
            break

    up_vol = down_vol = 0.0
    n = min(base_weeks, len(closes) - 1, 20)
    for i in range(-n, -1):
        if abs(i) >= len(closes): continue
        if closes[i] > closes[i-1]:
            up_vol += vols[i]
        else:
            down_vol += vols[i]
    more_up_vol = up_vol > down_vol * 1.2 if (up_vol + down_vol) > 0 else False

    if vol_declining_in_base and vol_explosion_now:
        score, pattern = 10, f"Perfect: dry-up in base + explosion ({recent_avg/prior_avg:.1f}x)"
    elif cap_spike and reversal_after:
        score, pattern = 9, "Capitulation spike + reversal candle"
    elif vol_declining_in_base and vol_building_now:
        score, pattern = 8, f"Dry-up in base + building ({recent_avg/prior_avg:.1f}x)"
    elif vol_declining_in_base and more_up_vol:
        score, pattern = 7, "Volume declining in base, more up-day volume"
    elif vol_declining_in_base:
        score, pattern = 6, "Volume declining in base (quiet accumulation)"
    elif more_up_vol and not vol_explosion_now:
        score, pattern = 5, "More volume on up days than down days"
    elif vol_explosion_now and not vol_declining_in_base:
        score, pattern = 4, "Volume surging but no prior dry-up — late entry risk"
    else:
        ratio = base_avg / prior_avg if prior_avg > 0 else 1
        score, pattern = (5, "Moderate volume dry-up in base") if ratio < 0.7 else (2, "No clear volume signature")

    return {
        "score": score, "pattern": pattern,
        "vol_declining_in_base": vol_declining_in_base, "vol_explosion_now": vol_explosion_now,
        "cap_spike": cap_spike, "more_up_vol": more_up_vol,
        "base_avg_vs_prior": round(base_avg / prior_avg, 2) if prior_avg > 0 else None,
        "recent_vs_prior": round(recent_avg / prior_avg, 2) if prior_avg > 0 else None,
        "notes": [pattern],
    }


# ─────────────────────────────────────────────────────────────────────────────
# DISQUALIFIERS
# ─────────────────────────────────────────────────────────────────────────────

def apply_disqualifiers(total: float, stage: int, macd: Dict, rs: Dict,
                         weekly_df: Optional[pd.DataFrame],
                         monthly_df: Optional[pd.DataFrame]) -> Tuple[float, List[str]]:
    disq = []

    if stage in [3, 4]:
        total = min(total, 40.0)
        disq.append(f"Stage {stage} on weekly — capped at 40")

    # NEW v3 disqualifier: no fresh MACD signal on ANY timeframe means
    # this is structurally not an "about to blast" candidate
    if macd.get("no_fresh_signal"):
        total = min(total, 50.0)
        disq.append("No fresh MACD signal on any timeframe — not a fresh momentum setup")

    if rs.get("score", 10) <= 1:
        total = max(0, total - 10)
        disq.append("RS line declining — -10 penalty")

    if weekly_df is not None and len(weekly_df) < 26:
        total = min(total, 35.0)
        disq.append(f"IPO flag: only {len(weekly_df)} weeks of history — insufficient for analysis")

    return max(0.0, min(100.0, total)), disq


# ─────────────────────────────────────────────────────────────────────────────
# MASTER SCORER
# ─────────────────────────────────────────────────────────────────────────────

def compute_technical_score_v2(daily_df: Optional[pd.DataFrame],
                                 weekly_df: Optional[pd.DataFrame],
                                 monthly_df: Optional[pd.DataFrame],
                                 nifty_weekly_df: Optional[pd.DataFrame]
                                 ) -> Dict[str, Any]:
    c1 = score_weekly_base(weekly_df)
    c2 = score_breakout_position(weekly_df, monthly_df)
    c3 = score_macd_multi_tf(daily_df, weekly_df, monthly_df)
    c4 = score_rs_line(weekly_df, nifty_weekly_df)
    base_weeks = c1.get("base_weeks", 0)
    c5 = score_weekly_volume(weekly_df, base_weeks)

    raw_total = c1["score"] + c2["score"] + c3["score"] + c4["score"] + c5["score"]
    final, disqualifiers = apply_disqualifiers(raw_total, c1["stage"], c3, c4, weekly_df, monthly_df)

    if final >= 85:   signal = "Strong Buy"
    elif final >= 70: signal = "Buy"
    elif final >= 55: signal = "Watchlist"
    elif final >= 40: signal = "Weak Watch"
    else:             signal = "Avoid"

    all_notes = c1["notes"] + c2["notes"] + c3["notes"] + c4["notes"] + c5["notes"]

    return {
        "technical_score": round(final, 1),
        "signal": signal,
        "disqualifiers": disqualifiers,
        "score_weekly_base":    c1["score"],
        "score_breakout_pos":   c2["score"],
        "score_macd_multi_tf":  c3["score"],
        "score_rs_line":        c4["score"],
        "score_weekly_volume":  c5["score"],
        "weekly_stage":         c1["stage_label"],
        "base_weeks":           c1["base_weeks"],
        "base_range_pct":       c1["base_range_pct"],
        "base_desc":            c1["base_desc"],
        "pct_from_52w_high":    c2["pct_from_52w_high"],
        "multi_yr_breakout":    c2["multi_yr_breakout"],
        "swing_highs_above":    c2["swing_highs_above"],
        "rs_line_state":        c4["state"],
        "rs_at_new_high":       c4.get("at_new_high", False),
        "macd_alignment_bonus": c3["alignment_bonus"],
        "macd_qualifying_tfs":  c3["qualifying_timeframes"],
        "no_fresh_signal":      c3["no_fresh_signal"],
        "vol_pattern":          c5["pattern"],
        "monthly_macd_bull":    c3.get("monthly_macd_bull", False),
        "weekly_macd_bull":     c3.get("weekly_macd_bull", False),
        "notes": all_notes,
        "detail": {"c1": c1, "c2": c2, "c3": c3, "c4": c4, "c5": c5},
    }