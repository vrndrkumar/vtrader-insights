"""
Weighted scoring + verdict classification.

DUAL WEIGHT PROFILES (per user requirement):
  Swing Trade (3-6M)  -> Technical + Sector dominate; Fundamental is
                         mostly a red-flag GATE, not a heavy weight.
                         Time horizon is too short for fundamentals
                         to matter much -- price structure and sector
                         tailwind drive the outcome.
  Long-Term (1-3Y)    -> Fundamental dominates; Technical only matters
                         for entry timing within an already-sound thesis.

Both profiles use the SAME underlying scores (fundamental_score,
technical_score, sector_score, momentum_score) -- only the WEIGHTS
differ. The report always displays the real fundamental/sector/momentum
numbers regardless of which profile is driving the verdict.
"""

from __future__ import annotations

from typing import Tuple

from ..config import get_settings

settings = get_settings()


# ── Swing trade weights (3-6 month horizon) — DEFAULT / used for overall_score ──
SWING_WEIGHTS = {
    "technical":   0.45,
    "sector":      0.30,
    "momentum":    0.15,
    "fundamental": 0.10,
}

# ── Long-term weights (1-3 year horizon) ──
LONG_TERM_WEIGHTS = {
    "fundamental": 0.45,
    "sector":      0.25,
    "technical":   0.15,
    "momentum":    0.15,
}


def weighted_final_score(fundamental: float, technical: float, sector: float, momentum: float,
                          profile: str = "swing") -> float:
    """
    profile: "swing" (default, 3-6M) or "long_term" (1-3Y)
    """
    weights = LONG_TERM_WEIGHTS if profile == "long_term" else SWING_WEIGHTS
    score = (
        fundamental * weights["fundamental"]
        + technical * weights["technical"]
        + sector * weights["sector"]
        + momentum * weights["momentum"]
    )
    return round(max(0.0, min(100.0, score)), 1)


def swing_verdict_for_score(score: float, has_red_flags: bool, risk_reward: float | None,
                             fundamental_score: float = 50.0) -> str:
    """
    Swing trade verdict. Fundamental acts as a GATE, not a weight:
    even a great technical+sector score gets capped at Watchlist if
    fundamentals are genuinely weak (red flags present or score < 30).
    """
    rr_ok = risk_reward is None or risk_reward >= 2.0
    fundamental_gate_failed = has_red_flags or fundamental_score < 30

    if score >= 78 and not fundamental_gate_failed and rr_ok:
        return "Strong Buy"
    if score >= 65 and rr_ok:
        return "Buy" if not fundamental_gate_failed else "Watchlist"
    if score >= 50:
        return "Watchlist"
    return "Avoid"


def long_term_verdict_for_score(score: float, has_red_flags: bool) -> str:
    """
    Long-term verdict. Fundamentals already dominate the score itself
    (45% weight), so red flags are a harder block here than in swing.
    """
    if score >= 75 and not has_red_flags:
        return "Strong Buy"
    if score >= 62 and not has_red_flags:
        return "Buy"
    if score >= 45:
        return "Watchlist"
    return "Avoid"


# Backward-compatible alias — existing code calling verdict_for_score()
# keeps working, mapped to the swing profile (the default/primary verdict).
def verdict_for_score(score: float, has_red_flags: bool, risk_reward: float | None,
                       fundamental_score: float = 50.0) -> str:
    return swing_verdict_for_score(score, has_red_flags, risk_reward, fundamental_score)


def confidence_for(score: float, verdict: str) -> str:
    if verdict == "Strong Buy" and score >= 82:
        return "Very High"
    if verdict in ("Strong Buy", "Buy") and score >= 68:
        return "High"
    if verdict in ("Buy", "Watchlist"):
        return "Medium"
    return "Low"


def probability_3_6m(score: float, verdict: str) -> float:
    """A simple, transparent mapping from score -> indicative probability.
    NOT a statistical model -- intended as a directional confidence read,
    consistent with how the original report framed 'Probability of Profitability'."""
    base = {
        "Strong Buy": 70,
        "Buy": 62,
        "Watchlist": 50,
        "Avoid": 35,
    }.get(verdict, 50)
    # Nudge by how far above/below the verdict's threshold the score sits
    nudge = (score - 50) * 0.15
    return round(max(20.0, min(85.0, base + nudge)), 1)


def has_fundamental_red_flags(fundamental_detail: dict) -> bool:
    flags = fundamental_detail.get("red_flags") or []
    return len(flags) > 0