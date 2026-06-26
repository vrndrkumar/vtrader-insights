"""
sources/sector_technicals.py — Multi-timeframe technical analysis
applied to a SECTOR INDEX, treating it like a tradeable instrument.

Per user design: a sector's own price action (RSI, MACD, EMA trend)
matters as much as how it compares to Nifty. A sector "beating Nifty"
while both fall is not actually bullish -- this module checks the
sector index's OWN trend quality, not just relative performance.

All functions operate on a single OHLC DataFrame (the sector index
history) with a DatetimeIndex, as returned by yfinance .history().
"""

from __future__ import annotations
from typing import Any, Dict, Optional, Tuple
import pandas as pd
import numpy as np


# ─────────────────────────────────────────────────────────────────────
# Core indicator math
# ─────────────────────────────────────────────────────────────────────

def _ema(series: pd.Series, period: int) -> pd.Series:
    return series.ewm(span=period, adjust=False).mean()


def _rsi(series: pd.Series, period: int = 14) -> pd.Series:
    delta = series.diff()
    gain  = delta.clip(lower=0)
    loss  = (-delta.clip(upper=0))
    avg_gain = gain.ewm(alpha=1/period, adjust=False, min_periods=period).mean()
    avg_loss = loss.ewm(alpha=1/period, adjust=False, min_periods=period).mean()
    rs  = avg_gain / avg_loss.replace(0, np.nan)
    rsi = 100 - (100 / (1 + rs))
    rsi = rsi.fillna(100)   # if avg_loss is 0, RSI = 100
    return rsi


def _macd(series: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9) -> Tuple[pd.Series, pd.Series, pd.Series]:
    ema_fast  = _ema(series, fast)
    ema_slow  = _ema(series, slow)
    macd_line = ema_fast - ema_slow
    signal_line = _ema(macd_line, signal)
    histogram = macd_line - signal_line
    return macd_line, signal_line, histogram


def _resample_weekly(df: pd.DataFrame) -> pd.DataFrame:
    """Resample daily OHLC to weekly bars (week ending Friday)."""
    weekly = df.resample("W-FRI").agg({
        "Open": "first", "High": "max", "Low": "min", "Close": "last",
        "Volume": "sum" if "Volume" in df.columns else "last",
    }).dropna()
    return weekly


# ─────────────────────────────────────────────────────────────────────
# RSI sub-score — multi-timeframe trend-aware
# ─────────────────────────────────────────────────────────────────────

def score_rsi_multi_timeframe(daily_close: pd.Series, weekly_close: pd.Series) -> Dict[str, Any]:
    """
    Evaluates RSI not just on current value but on its TREND (rising/
    falling over last 5 bars) and AGREEMENT between daily and weekly.

    A daily RSI that is overbought but still rising, with weekly RSI
    also rising, is NOT penalised the way a naive "RSI > 70 = bad"
    rule would -- per user's explicit point that strong momentum
    stocks/sectors can stay overbought on daily while the broader
    trend continues. The key signal is DIRECTION and AGREEMENT,
    not the raw overbought/oversold level alone.

    Max points: 25
    """
    points = 0.0
    notes  = []

    if len(daily_close) < 20:
        return {"points": 0.0, "notes": ["Insufficient daily data for RSI."], "daily_rsi": None, "weekly_rsi": None}

    daily_rsi  = _rsi(daily_close, 14)
    d_now      = float(daily_rsi.iloc[-1])
    d_5ago     = float(daily_rsi.iloc[-6]) if len(daily_rsi) >= 6 else d_now
    d_rising   = d_now > d_5ago

    weekly_rsi = None
    w_now = w_rising = None
    if weekly_close is not None and len(weekly_close) >= 10:
        weekly_rsi = _rsi(weekly_close, 14)
        w_now    = float(weekly_rsi.iloc[-1])
        w_5ago   = float(weekly_rsi.iloc[-3]) if len(weekly_rsi) >= 3 else w_now
        # Treat near-equal values (flat/saturated RSI) as neutral, not falling --
        # RSI pinned at 100 (or near it) in a strong trend isn't "falling" just
        # because it can't numerically go higher.
        if abs(w_now - w_5ago) < 1.5:
            w_rising = None   # flat -- genuinely no clear direction
        else:
            w_rising = w_now > w_5ago

    # Daily RSI trend direction
    if d_rising:
        points += 8
        notes.append(f"Daily RSI rising ({d_5ago:.1f} → {d_now:.1f}) — momentum building.")
    else:
        points -= 5
        notes.append(f"Daily RSI falling ({d_5ago:.1f} → {d_now:.1f}) — momentum cooling.")

    # Weekly RSI trend direction (stronger signal, more durable)
    if w_rising is not None:
        if w_rising:
            points += 10
            notes.append(f"Weekly RSI rising ({w_5ago:.1f} → {w_now:.1f}) — higher-timeframe momentum confirms.")
        else:
            points -= 8
            notes.append(f"Weekly RSI falling ({w_5ago:.1f} → {w_now:.1f}) — higher-timeframe momentum weakening.")

        # Agreement bonus/penalty
        if d_rising and w_rising:
            points += 5
            notes.append("Daily and weekly RSI both rising — strong multi-timeframe alignment.")
        elif (not d_rising) and (not w_rising):
            points -= 5
            notes.append("Daily and weekly RSI both falling — confirmed weakening across timeframes.")
        elif d_rising and not w_rising:
            notes.append("Daily RSI rising but weekly RSI still falling — early signal, not yet confirmed on higher timeframe.")
        else:
            notes.append("Daily RSI falling but weekly RSI still rising — could be a pause within a larger uptrend, not a reversal.")
    elif w_now is not None:
        # Weekly RSI flat/saturated -- treat as neutral-to-mildly-positive
        # if it's flat at a high level (sustained strength), neutral if flat at mid
        if w_now >= 70:
            points += 4
            notes.append(f"Weekly RSI flat but elevated at {w_now:.1f} — sustained strength, no clear new direction.")
        else:
            notes.append(f"Weekly RSI flat at {w_now:.1f} — no clear higher-timeframe direction.")

    # Extreme zone context (informational, not just penalty -- per user's point that
    # overbought daily RSI doesn't kill a trend if weekly stays strong)
    if d_now > 75 and w_rising:
        notes.append(f"Daily RSI overbought at {d_now:.1f}, but weekly trend still rising — historically this can persist in strong sectors, not an automatic sell signal.")
    elif d_now > 75 and w_rising is False:
        points -= 4
        notes.append(f"Daily RSI overbought at {d_now:.1f} AND weekly momentum not confirming — higher risk of pullback.")
    elif d_now > 75 and w_now is not None and w_now >= 70:
        notes.append(f"Daily RSI overbought at {d_now:.1f}, weekly RSI also elevated ({w_now:.1f}) — sustained strength, not necessarily a reversal signal.")
    elif d_now < 30:
        notes.append(f"Daily RSI oversold at {d_now:.1f} — watch for reversal signal, not yet confirmed.")

    points = max(-25.0, min(25.0, points))

    return {
        "points": round(points, 1),
        "notes": notes,
        "daily_rsi": round(d_now, 1),
        "weekly_rsi": round(w_now, 1) if w_now is not None else None,
        "daily_rsi_rising": d_rising,
        "weekly_rsi_rising": w_rising,
    }


# ─────────────────────────────────────────────────────────────────────
# MACD sub-score — crossover freshness, zero-line position, histogram
# ─────────────────────────────────────────────────────────────────────

def _analyze_macd_timeframe(close: pd.Series, label: str) -> Dict[str, Any]:
    macd_line, signal_line, hist = _macd(close)

    if len(macd_line.dropna()) < 5:
        return {"available": False}

    m_now, s_now, h_now = macd_line.iloc[-1], signal_line.iloc[-1], hist.iloc[-1]
    h_prev = hist.iloc[-2] if len(hist) >= 2 else h_now
    h_prev2 = hist.iloc[-3] if len(hist) >= 3 else h_prev

    is_bullish = m_now > s_now
    histogram_expanding = abs(h_now) > abs(h_prev) > abs(h_prev2) if len(hist) >= 3 else None

    # Find how many bars since the last crossover
    diff = macd_line - signal_line
    sign = np.sign(diff)
    crossover_bars_ago = None
    for i in range(2, min(len(sign), 60)):
        if sign.iloc[-i] != sign.iloc[-1] and sign.iloc[-i] != 0:
            crossover_bars_ago = i - 1
            break

    # Zero-line position — far below / near below / near above / far above
    # "Near" zero defined relative to the recent MACD range for scale-independence
    macd_range = float(macd_line.tail(60).abs().max()) if len(macd_line) >= 5 else abs(m_now) or 1.0
    macd_range = macd_range or 1.0
    zero_distance_pct = (m_now / macd_range) * 100  # -100..+100 roughly

    if m_now >= 0:
        zero_position = "Far above zero" if zero_distance_pct > 30 else "Near zero (above)"
    else:
        zero_position = "Far below zero" if zero_distance_pct < -30 else "Near zero (below)"

    return {
        "available": True,
        "label": label,
        "is_bullish": bool(is_bullish),
        "macd": round(float(m_now), 2),
        "signal": round(float(s_now), 2),
        "histogram": round(float(h_now), 2),
        "histogram_expanding": histogram_expanding,
        "crossover_bars_ago": crossover_bars_ago,
        "zero_position": zero_position,
        "zero_distance_pct": round(zero_distance_pct, 1),
    }


def score_macd_multi_timeframe(daily_close: pd.Series, weekly_close: pd.Series) -> Dict[str, Any]:
    """
    Evaluates MACD crossover quality on daily AND weekly:
      - Direction (bullish/bearish crossover)
      - Freshness (how many bars since crossover -- fresher = more weight)
      - Position vs zero line (above zero = established trend, below = early/speculative)
      - Histogram expanding or shrinking (accelerating or decelerating momentum)

    Max points: 30
    """
    points = 0.0
    notes  = []

    daily  = _analyze_macd_timeframe(daily_close, "Daily")
    weekly = _analyze_macd_timeframe(weekly_close, "Weekly") if weekly_close is not None and len(weekly_close) >= 10 else {"available": False}

    if not daily.get("available"):
        return {"points": 0.0, "notes": ["Insufficient data for MACD."], "daily": daily, "weekly": weekly}

    # ── Daily MACD scoring ──
    if daily["is_bullish"]:
        base = 8
        # Freshness bonus -- a crossover in the last 3 days is much more
        # actionable than one from 3 weeks ago that's already played out
        cba = daily["crossover_bars_ago"]
        if cba is not None and cba <= 3:
            base += 4
            notes.append(f"Daily MACD bullish crossover {cba} session(s) ago — fresh signal.")
        elif cba is not None and cba <= 10:
            notes.append(f"Daily MACD bullish, crossover {cba} sessions ago — still developing.")
        else:
            notes.append("Daily MACD bullish, but crossover happened a while ago — trend may be maturing.")

        if daily["zero_position"] == "Far above zero":
            base += 2
            notes.append("Daily MACD far above zero line — established uptrend already confirmed.")
        elif "below" in daily["zero_position"]:
            notes.append("Daily MACD bullish but still below zero line — early-stage signal, less confirmed.")

        if daily.get("histogram_expanding"):
            base += 3
            notes.append("Daily MACD histogram expanding — bullish momentum accelerating.")
        elif daily.get("histogram_expanding") is False:
            base -= 2
            notes.append("Daily MACD histogram shrinking — bullish momentum losing steam.")

        points += base
    else:
        base = -6
        cba = daily["crossover_bars_ago"]
        if cba is not None and cba <= 3:
            base -= 3
            notes.append(f"Daily MACD bearish crossover {cba} session(s) ago — fresh weakness signal.")
        if daily["zero_position"] == "Far below zero":
            base -= 2
            notes.append("Daily MACD far below zero line — confirmed downtrend.")
        points += base

    # ── Weekly MACD scoring (weighted higher -- "stronger trend confirmation" per spec) ──
    if weekly.get("available"):
        if weekly["is_bullish"]:
            base = 10
            cba = weekly["crossover_bars_ago"]
            if cba is not None and cba <= 2:
                base += 5
                notes.append(f"Weekly MACD bullish crossover {cba} week(s) ago — fresh higher-timeframe signal.")
            else:
                notes.append("Weekly MACD bullish — higher-timeframe trend confirmed.")

            if weekly["zero_position"] == "Far above zero":
                base += 3
                notes.append("Weekly MACD far above zero — mature, well-established uptrend.")

            if weekly.get("histogram_expanding"):
                base += 4
                notes.append("Weekly MACD histogram expanding — longer-term momentum accelerating.")
            points += base
        else:
            base = -8
            if weekly["zero_position"] == "Far below zero":
                base -= 3
                notes.append("Weekly MACD far below zero — confirmed longer-term downtrend.")
            else:
                notes.append("Weekly MACD bearish — higher-timeframe momentum not supportive.")
            points += base

        # Multi-timeframe agreement bonus
        if daily["is_bullish"] and weekly["is_bullish"]:
            points += 5
            notes.append("Daily and weekly MACD both bullish — strong multi-timeframe confirmation.")
        elif (not daily["is_bullish"]) and (not weekly["is_bullish"]):
            points -= 3
            notes.append("Daily and weekly MACD both bearish — confirmed weakness across timeframes.")

    points = max(-30.0, min(30.0, points))

    return {
        "points": round(points, 1),
        "notes": notes,
        "daily": daily,
        "weekly": weekly,
    }


# ─────────────────────────────────────────────────────────────────────
# EMA trend-alignment sub-score
# ─────────────────────────────────────────────────────────────────────

def score_ema_trend(close: pd.Series) -> Dict[str, Any]:
    """
    Checks price position relative to EMA50 and EMA100 -- the
    "absolute trend gate" -- price above both = healthy uptrend
    structure, below both = downtrend, mixed = transition zone.

    Max points: 15
    """
    if len(close) < 50:
        return {"points": 0.0, "notes": ["Insufficient data for EMA50/EMA100."], "ema50": None, "ema100": None}

    ema50  = _ema(close, 50)
    price  = float(close.iloc[-1])
    e50    = float(ema50.iloc[-1])

    e100 = None
    if len(close) >= 100:
        ema100 = _ema(close, 100)
        e100   = float(ema100.iloc[-1])

    points = 0.0
    notes  = []

    if e100 is not None:
        if price > e50 > e100:
            points = 15
            notes.append(f"Price ({price:.0f}) above EMA50 ({e50:.0f}) above EMA100 ({e100:.0f}) — clean uptrend structure.")
        elif price < e50 < e100:
            points = -12
            notes.append(f"Price ({price:.0f}) below EMA50 ({e50:.0f}) below EMA100 ({e100:.0f}) — clean downtrend structure.")
        elif price > e100 and price < e50:
            points = 5
            notes.append("Price above EMA100 but below EMA50 — early recovery, not yet confirmed.")
        elif price > e50 and price < e100:
            points = -3
            notes.append("Price above EMA50 but below EMA100 — short-term bounce within a longer downtrend, use caution.")
        else:
            points = 0
            notes.append("Price/EMA structure mixed — no clear trend alignment.")
    else:
        # Only EMA50 available (less than 100 bars of history)
        if price > e50:
            points = 8
            notes.append(f"Price above EMA50 ({e50:.0f}) — short-term trend positive. (EMA100 unavailable, insufficient history.)")
        else:
            points = -8
            notes.append(f"Price below EMA50 ({e50:.0f}) — short-term trend negative. (EMA100 unavailable, insufficient history.)")

    return {
        "points": round(points, 1),
        "notes": notes,
        "ema50": round(e50, 2),
        "ema100": round(e100, 2) if e100 is not None else None,
        "price": round(price, 2),
    }


# ─────────────────────────────────────────────────────────────────────
# Combined sector technical score
# ─────────────────────────────────────────────────────────────────────

def compute_sector_technical_score(index_hist: pd.DataFrame) -> Dict[str, Any]:
    """
    Combines RSI multi-TF + MACD multi-TF + EMA trend into a single
    technical quality score for a sector index, treating it like a
    tradeable instrument per user's design intent.

    Returns raw points (not yet blended with Relative Strength --
    that blending happens in yfinance_source.py).
    """
    if index_hist is None or index_hist.empty or len(index_hist) < 30:
        return {
            "technical_points": 0.0,
            "rsi": {"points": 0.0, "notes": []},
            "macd": {"points": 0.0, "notes": []},
            "ema": {"points": 0.0, "notes": []},
            "notes": ["Insufficient sector index history for technical analysis."],
        }

    daily_close  = index_hist["Close"]
    weekly_hist  = _resample_weekly(index_hist)
    weekly_close = weekly_hist["Close"] if not weekly_hist.empty else None

    rsi_result  = score_rsi_multi_timeframe(daily_close, weekly_close)
    macd_result = score_macd_multi_timeframe(daily_close, weekly_close)
    ema_result  = score_ema_trend(daily_close)

    # Raw points: RSI(±25) + MACD(±30) + EMA(±15) = range roughly -70..+70
    total_points = rsi_result["points"] + macd_result["points"] + ema_result["points"]

    return {
        "technical_points": round(total_points, 1),
        "rsi": rsi_result,
        "macd": macd_result,
        "ema": ema_result,
    }