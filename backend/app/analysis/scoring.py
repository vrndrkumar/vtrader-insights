"""
Weighted scoring + verdict classification.

Mirrors the original screening framework:
    Final Score = 25% Fundamental + 40% Technical + 20% Sector + 15% Momentum

Verdict thresholds and confidence/probability mapping are centralised
here so they're easy to tune without touching the orchestrator.
"""

from __future__ import annotations

from typing import Tuple

from ..config import get_settings

settings = get_settings()


def weighted_final_score(fundamental: float, technical: float, sector: float, momentum: float) -> float:
    score = (
        fundamental * settings.weight_fundamental
        + technical * settings.weight_technical
        + sector * settings.weight_sector
        + momentum * settings.weight_momentum
    )
    return round(max(0.0, min(100.0, score)), 1)


def verdict_for_score(score: float, has_red_flags: bool, risk_reward: float | None) -> str:
    """
    Verdict thresholds:
      >= 78  Strong Buy   (also requires no red flags and R:R >= 2)
      >= 65  Buy
      >= 50  Watchlist
      <  50  Avoid

    Red flags or poor risk-reward cap the verdict at "Watchlist" even if
    the composite score is high -- this enforces the capital-preservation
    rule from the original brief.
    """
    rr_ok = risk_reward is None or risk_reward >= 2.0

    if score >= 78 and not has_red_flags and rr_ok:
        return "Strong Buy"
    if score >= 65 and rr_ok:
        return "Buy" if not has_red_flags else "Watchlist"
    if score >= 50:
        return "Watchlist"
    return "Avoid"


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
