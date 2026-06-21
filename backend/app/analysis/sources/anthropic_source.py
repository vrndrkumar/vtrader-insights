"""
sources/anthropic_source.py — Claude + web search as a pluggable source

Wraps the existing llm_engine.py logic behind the same interface as
the yfinance source, so orchestrator.py can swap between them with
zero changes to the rest of the pipeline.
"""

from __future__ import annotations
from typing import Any, Dict, Optional

import pandas as pd

from .base import FundamentalSource, SectorSource, MomentumSource
from .. import llm_engine


class AnthropicFundamentalSource(FundamentalSource):
    """
    Calls Claude with web search for fundamental research.
    Note: this makes a full analyze_stock_with_llm call internally,
    which also returns sector/momentum/swing data — those extra
    fields are cached on the instance so Sector/Momentum sources
    below can reuse the same API call instead of triggering 3
    separate Claude calls per stock.
    """

    def __init__(self):
        self._cache: Dict[str, Dict[str, Any]] = {}

    def _ensure_called(self, symbol_code: str, **kwargs) -> Dict[str, Any]:
        if symbol_code not in self._cache:
            self._cache[symbol_code] = llm_engine.analyze_stock_with_llm(**kwargs)
        return self._cache[symbol_code]

    def get_fundamentals(self, symbol_code: str, exchange: str, sector: Optional[str] = None,
                          symbol_name: str = "", technical: Optional[dict] = None,
                          suggested_setup: Optional[dict] = None, industry: str = "",
                          description: str = "") -> Dict[str, Any]:
        result = self._ensure_called(
            symbol_code,
            symbol_name=symbol_name, symbol_code=symbol_code, exchange=exchange,
            technical=technical or {}, suggested_setup=suggested_setup or {},
            sector=sector or "", industry=industry, description=description,
        )
        fund = result.get("fundamental", {})
        fund.setdefault("raw_metrics", {})
        return fund


class AnthropicSectorSource(SectorSource):
    def __init__(self, shared_fundamental_source: Optional[AnthropicFundamentalSource] = None):
        self._shared = shared_fundamental_source

    def get_sector_analysis(self, sector: Optional[str], sector_index_symbol: Optional[str] = None,
                             **kwargs) -> Dict[str, Any]:
        # If called standalone without the shared cache, fall back gracefully
        if self._shared is None or kwargs.get("symbol_code") not in self._shared._cache:
            return {
                "sector_name": sector or "Unclassified",
                "sector_trend": "Neutral",
                "sector_strength_score": 50.0,
                "sector_outlook": "AI sector research unavailable in this context.",
                "growth_drivers": [], "risks": [], "raw_metrics": {},
            }
        result = self._shared._cache[kwargs["symbol_code"]]
        sec = result.get("sector", {})
        sec.setdefault("raw_metrics", {})
        return sec


class AnthropicMomentumSource(MomentumSource):
    def __init__(self, shared_fundamental_source: Optional[AnthropicFundamentalSource] = None):
        self._shared = shared_fundamental_source

    def get_momentum(self, symbol_code: str, price_history: pd.DataFrame,
                      sector_index_symbol: Optional[str] = None) -> Dict[str, Any]:
        if self._shared is None or symbol_code not in self._shared._cache:
            return {
                "momentum_score": 50.0,
                "relative_strength_assessment": "AI momentum research unavailable in this context.",
                "accumulation_distribution": "—",
                "raw_metrics": {},
            }
        result = self._shared._cache[symbol_code]
        mom = result.get("momentum", {})
        mom.setdefault("raw_metrics", {})
        return mom