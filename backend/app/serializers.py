"""Convert SQLAlchemy rows → Pydantic schemas."""

from datetime import datetime
from typing import Optional

from .database import StockAnalysisReport, StockMstr
from . import market_data
from .schemas import (
    StockReport, StockSummary, SwingView, LongTermView,
    FundamentalDetail, SectorDetail, MomentumDetail, TradeSetup,
)


def _clean_sector(value: Optional[str]) -> Optional[str]:
    """Return None if sector is a generic fallback, else return the value."""
    if value in (None, "", "Unclassified", "unclassified", "Unknown", "unknown"):
        return None
    return value


def report_to_schema(report: StockAnalysisReport, stock: Optional[StockMstr] = None) -> StockReport:
    swing_raw = report.swing_view or {}
    setup_raw = swing_raw.get("trade_setup", {}) or {}

    # Resolve sector — prefer real DB value, fall back to LLM result only if not generic
    real_sector     = _clean_sector(stock.sector if stock else None)
    real_industry   = _clean_sector(stock.industry if stock else None)
    llm_sector_name = _clean_sector((report.sector_detail or {}).get("sector_name"))
    resolved_sector = real_sector or llm_sector_name

    return StockReport(
        id          = report.id,
        stock_id    = report.stock_id,
        symbol_code = report.symbol_code,
        symbol_name = stock.symbol_name if stock else None,
        exchange    = report.exchange,

        sector      = resolved_sector,
        industry    = real_industry or _clean_sector(report.industry),
        category    = report.category or (stock.category if stock else None),
        description = stock.description if stock else None,

        overall_score     = report.overall_score,
        fundamental_score = report.fundamental_score,
        technical_score   = report.technical_score,
        sector_score      = report.sector_score,
        momentum_score    = report.momentum_score,

        verdict          = report.verdict,
        confidence       = report.confidence,
        probability_3_6m = report.probability_3_6m,

        swing_view = SwingView(
            trade_setup            = TradeSetup(**setup_raw),
            why_recommended        = swing_raw.get("why_recommended", []),
            why_not_or_caveats     = swing_raw.get("why_not_or_caveats", []),
            technical_trend        = swing_raw.get("technical_trend"),
            support_levels         = swing_raw.get("support_levels", []),
            resistance_levels      = swing_raw.get("resistance_levels", []),
            chart_structure        = swing_raw.get("chart_structure"),
            trade_setup_commentary = swing_raw.get("trade_setup_commentary"),
        ),

        long_term_view = LongTermView(**(report.long_term_view or {})) if report.long_term_view else None,

        fundamental_detail = FundamentalDetail(
            rating                 = (report.fundamental_detail or {}).get("rating"),
            business_quality_notes = (report.fundamental_detail or {}).get("business_quality_notes"),
            financial_health_notes = (report.fundamental_detail or {}).get("financial_health_notes"),
            ownership_notes        = (report.fundamental_detail or {}).get("ownership_notes"),
            valuation_notes        = (report.fundamental_detail or {}).get("valuation_notes"),
            red_flags              = (report.fundamental_detail or {}).get("red_flags", []),
        ),

        sector_detail = SectorDetail(
            sector_name           = resolved_sector,
            sector_trend          = (report.sector_detail or {}).get("sector_trend"),
            sector_strength_score = (report.sector_detail or {}).get("sector_strength_score"),
            sector_outlook        = (report.sector_detail or {}).get("sector_outlook"),
            growth_drivers        = (report.sector_detail or {}).get("growth_drivers", []),
            risks                 = (report.sector_detail or {}).get("risks", []),
        ),

        momentum_detail = MomentumDetail(
            momentum_score               = (report.momentum_detail or {}).get("momentum_score"),
            relative_strength_assessment = (report.momentum_detail or {}).get("relative_strength_assessment"),
            accumulation_distribution    = (report.momentum_detail or {}).get("accumulation_distribution"),
        ),

        technical_detail = report.technical_detail,
        risk_factors     = report.risk_factors or [],
        raw_quote        = report.raw_quote,
        generated_at     = report.generated_at,
    )


def stock_to_summary(stock: StockMstr, report: Optional[StockAnalysisReport] = None) -> StockSummary:
    quote = market_data.quote_from_latest_update(stock.latest_update) or {}

    age_minutes = None
    if report and report.generated_at:
        age_minutes = round((datetime.utcnow() - report.generated_at).total_seconds() / 60, 1)

    return StockSummary(
        id          = stock.id,
        exchange    = stock.exchange,
        symbol_code = stock.symbol_code,
        symbol_name = stock.symbol_name,
        token_id    = stock.token_id,
        sector      = _clean_sector(stock.sector),
        industry    = _clean_sector(stock.industry),
        category    = stock.category,
        description = stock.description,
        last_price  = quote.get("ltp"),
        change_pct  = quote.get("change_pct"),
        volume      = quote.get("volume"),
        overall_score     = report.overall_score     if report else None,
        fundamental_score = report.fundamental_score if report else None,
        technical_score   = report.technical_score   if report else None,
        sector_score      = report.sector_score      if report else None,
        momentum_score    = report.momentum_score    if report else None,
        verdict           = report.verdict           if report else None,
        confidence        = report.confidence        if report else None,
        probability_3_6m  = report.probability_3_6m  if report else None,
        report_age_minutes = age_minutes,
    )