"""Pydantic schemas for API requests and responses."""

from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel


class StockSummary(BaseModel):
    id:          int
    exchange:    Optional[str] = None
    symbol_code: Optional[str] = None
    symbol_name: str
    token_id:    Optional[int] = None

    # Enrichment
    sector:      Optional[str] = None
    industry:    Optional[str] = None
    category:    Optional[str] = None   # EQUITY | ETF | MF
    description: Optional[str] = None

    # Live quote
    last_price:  Optional[float] = None
    change_pct:  Optional[float] = None
    volume:      Optional[float] = None

    # Latest analysis
    overall_score:     Optional[float] = None
    fundamental_score: Optional[float] = None
    technical_score:   Optional[float] = None
    sector_score:      Optional[float] = None
    momentum_score:    Optional[float] = None
    verdict:           Optional[str]   = None
    confidence:        Optional[str]   = None
    probability_3_6m:  Optional[float] = None
    report_age_minutes: Optional[float] = None

    class Config:
        from_attributes = True


class StockListResponse(BaseModel):
    total: int
    items: List[StockSummary]


class TradeSetup(BaseModel):
    current_price:      Optional[float] = None
    entry_zone_low:     Optional[float] = None
    entry_zone_high:    Optional[float] = None
    breakout_trigger:   Optional[float] = None
    stop_loss:          Optional[float] = None
    target1:            Optional[float] = None
    target2:            Optional[float] = None
    target3:            Optional[float] = None
    expected_return_pct: Optional[float] = None
    risk_reward_ratio:  Optional[float] = None


class SwingView(BaseModel):
    trade_setup:          TradeSetup
    why_recommended:      List[str] = []
    why_not_or_caveats:   List[str] = []
    technical_trend:      Optional[str] = None
    support_levels:       List[float]   = []
    resistance_levels:    List[float]   = []
    chart_structure:      Optional[str] = None
    trade_setup_commentary: Optional[str] = None


class LongTermView(BaseModel):
    horizon:           str = "1-3 years"
    thesis:            Optional[str] = None
    structural_score:  Optional[float] = None
    growth_drivers:    List[str] = []
    long_term_risks:   List[str] = []
    valuation_view:    Optional[str] = None
    suitable_for_long_term: Optional[bool] = None


class SectorDetail(BaseModel):
    sector_name:          Optional[str]   = None
    sector_trend:         Optional[str]   = None
    sector_strength_score: Optional[float] = None
    sector_outlook:       Optional[str]   = None
    growth_drivers:       List[str]       = []
    risks:                List[str]       = []


class FundamentalDetail(BaseModel):
    rating:                Optional[str] = None
    business_quality_notes: Optional[str] = None
    financial_health_notes: Optional[str] = None
    ownership_notes:        Optional[str] = None
    valuation_notes:        Optional[str] = None
    red_flags:              List[str]     = []


class MomentumDetail(BaseModel):
    momentum_score:               Optional[float] = None
    relative_strength_assessment: Optional[str]   = None
    accumulation_distribution:    Optional[str]   = None


class StockReport(BaseModel):
    id:          Optional[int]  = None
    stock_id:    int
    symbol_code: Optional[str]  = None
    symbol_name: Optional[str]  = None
    exchange:    Optional[str]  = None

    # Enrichment
    sector:      Optional[str]  = None
    industry:    Optional[str]  = None
    category:    Optional[str]  = None
    description: Optional[str]  = None

    overall_score:     Optional[float] = None
    fundamental_score: Optional[float] = None
    technical_score:   Optional[float] = None
    sector_score:      Optional[float] = None
    momentum_score:    Optional[float] = None

    verdict:         Optional[str]   = None
    confidence:      Optional[str]   = None
    probability_3_6m: Optional[float] = None

    swing_view:         Optional[SwingView]         = None
    long_term_view:     Optional[LongTermView]      = None
    fundamental_detail: Optional[FundamentalDetail] = None
    sector_detail:      Optional[SectorDetail]      = None
    momentum_detail:    Optional[MomentumDetail]    = None
    technical_detail:   Optional[Dict[str, Any]]    = None
    risk_factors:       List[str]                   = []
    raw_quote:          Optional[Dict[str, Any]]    = None
    generated_at:       Optional[datetime]          = None

    class Config:
        from_attributes = True


class AnalyzeRequest(BaseModel):
    symbols:       Optional[List[str]] = None
    force_refresh: bool = True


class JobStatus(BaseModel):
    id:             int
    job_type:       str
    status:         str
    total:          int
    completed:      int
    failed:         int
    result_summary: Optional[Dict[str, Any]] = None
    error:          Optional[str]            = None
    created_at:     Optional[datetime]       = None
    completed_at:   Optional[datetime]       = None

    class Config:
        from_attributes = True


class MarketOverviewSchema(BaseModel):
    market_view:       Optional[str]            = None
    favoured_sectors:  List[Dict[str, Any]]     = []
    avoid_sectors:     List[Dict[str, Any]]     = []
    key_risks:         List[str]                = []
    key_opportunities: List[str]                = []
    generated_at:      Optional[datetime]       = None


class DashboardResponse(BaseModel):
    market_overview:  Optional[MarketOverviewSchema] = None
    verdict_counts:   Dict[str, int]                 = {}
    sector_strength:  List[Dict[str, Any]]           = []
    industry_strength: List[Dict[str, Any]]          = []
    top_picks:        List[StockReport]              = []
    last_batch_job:   Optional[JobStatus]            = None
    total_stocks:     int = 0
    equity_stocks:    int = 0
    analyzed_stocks:  int = 0
    category_counts:  Dict[str, int]                 = {}