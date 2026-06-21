"""
sources/__init__.py — Source factory

Reads ANALYSIS_SOURCE from settings and returns the correct
Fundamental/Sector/Momentum source implementations as a matched set.

Usage in orchestrator.py:
    from .sources import get_analysis_sources
    fund_src, sector_src, momentum_src = get_analysis_sources()
"""

from __future__ import annotations
from typing import Tuple

from ...config import get_settings
from .base import FundamentalSource, SectorSource, MomentumSource
from .yfinance_source import (
    YFinanceFundamentalSource, YFinanceSectorSource, YFinanceMomentumSource,
)
from .anthropic_source import (
    AnthropicFundamentalSource, AnthropicSectorSource, AnthropicMomentumSource,
)

settings = get_settings()


def get_analysis_sources() -> Tuple[FundamentalSource, SectorSource, MomentumSource]:
    """
    Returns (fundamental_source, sector_source, momentum_source)
    matched to the configured ANALYSIS_SOURCE.

    yfinance  -> all three from structured financial data, free, no API cost
    anthropic -> all three from Claude + web search, shares one API call
    hybrid    -> fundamental/sector/momentum NUMBERS from yfinance,
                 narrative enrichment layered on top by orchestrator
                 (orchestrator handles the blending, not this factory)
    """
    source = (getattr(settings, "analysis_source", "yfinance") or "yfinance").lower()

    if source == "anthropic":
        fund = AnthropicFundamentalSource()
        return fund, AnthropicSectorSource(fund), AnthropicMomentumSource(fund)

    # "yfinance" and "hybrid" both start from yfinance numbers.
    # In hybrid mode, orchestrator.py additionally calls llm_engine
    # for narrative (why_recommended, risk_factors, long_term_view)
    # but the SCORES themselves still come from yfinance — cheaper
    # and more numerically reliable than asking an LLM to estimate ratios.
    return YFinanceFundamentalSource(), YFinanceSectorSource(), YFinanceMomentumSource()