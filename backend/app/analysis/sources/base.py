"""
sources/base.py — Pluggable analysis source interfaces

VTrader Stock Intelligence supports swapping the engine that produces
Fundamental / Sector / Momentum analysis without touching the rest of
the pipeline. Set ANALYSIS_SOURCE in .env:

  ANALYSIS_SOURCE=yfinance    -> free, structured financial ratios (default)
  ANALYSIS_SOURCE=anthropic   -> Claude + web search (narrative, costs credits)
  ANALYSIS_SOURCE=hybrid      -> yfinance numbers + Claude narrative on top

Every implementation returns the SAME shaped dict so orchestrator.py
and the frontend never need to know which engine actually ran.
The UI always just says "AI Insights" — the source is invisible to users.
"""

from __future__ import annotations
from abc import ABC, abstractmethod
from typing import Any, Dict, Optional


class FundamentalSource(ABC):
    @abstractmethod
    def get_fundamentals(
        self,
        symbol_code: str,
        exchange: str,
        sector: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Must return:
        {
            "score": float (0-100),
            "rating": "Strong" | "Good" | "Average" | "Weak",
            "business_quality_notes": str,
            "financial_health_notes": str,
            "ownership_notes": str,
            "valuation_notes": str,
            "red_flags": list[str],
            "raw_metrics": dict,   # actual numbers for display in report
        }
        """
        ...


class SectorSource(ABC):
    @abstractmethod
    def get_sector_analysis(
        self,
        sector: Optional[str],
        sector_index_symbol: Optional[str],
        db=None,
    ) -> Dict[str, Any]:
        """
        Must return:
        {
            "sector_name": str,
            "sector_trend": "Bullish" | "Neutral" | "Bearish",
            "sector_strength_score": float (0-100),
            "sector_outlook": str,
            "growth_drivers": list[str],
            "risks": list[str],
            "raw_metrics": dict,
        }

        db: optional SQLAlchemy session, used by implementations that
        support daily caching (e.g. YFinanceSectorSource) to avoid
        recomputing the same sector technical score for every stock.
        Implementations that don't need caching can ignore it.
        """
        ...


class MomentumSource(ABC):
    @abstractmethod
    def get_momentum(
        self,
        symbol_code: str,
        price_history,   # pandas DataFrame with date/close/volume
        sector_index_symbol: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Must return:
        {
            "momentum_score": float (0-100),
            "relative_strength_assessment": str,
            "accumulation_distribution": str,
            "raw_metrics": dict,
        }
        """
        ...