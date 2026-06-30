"""
Database layer — VTrader Stock Analyser

stock_mstr columns (updated by user, June 2026):
  symbol_name   — proper company name (e.g. "Reliance Industries Ltd")
  sector        — sector name (e.g. "Energy")
  industry      — industry name (e.g. "Oil & Gas Refining")
  description   — short company description (may be blank)
  category      — ENUM: 'EQUITY', 'ETF', 'MF'

Analysis only runs on EQUITY stocks (ETF/MF excluded automatically).
"""

from datetime import datetime
from sqlalchemy import (
    create_engine, Column, BigInteger, Integer, String,
    Boolean, Text, TIMESTAMP, JSON, Float, ForeignKey, func, Enum,
)
from sqlalchemy.orm import declarative_base, sessionmaker, Session
from .config import get_settings

settings = get_settings()

engine = create_engine(
    settings.sqlalchemy_database_uri,
    pool_pre_ping=True,
    pool_recycle=280,
    future=True,
)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
Base = declarative_base()


# ── Existing table (mapped, never altered by this app) ───────────────
class StockMstr(Base):
    __tablename__ = "stock_mstr"

    id          = Column(BigInteger, primary_key=True, autoincrement=True)
    exchange    = Column(String(5))
    symbol_code = Column(String(20))
    symbol_name = Column(String(200), nullable=False)
    token_id    = Column(Integer)
    created_at  = Column(TIMESTAMP, server_default=func.now())
    updated_at  = Column(TIMESTAMP)
    is_active   = Column(Boolean, default=True)
    latest_update = Column(JSON)

    # New enrichment columns (added by user)
    sector      = Column(String(100), nullable=True)
    industry    = Column(String(100), nullable=True)
    description = Column(Text, nullable=True)
    category    = Column(String(10), nullable=True)   # EQUITY | ETF | MF
    sector_index_symbol = Column(String(20), nullable=True)


# ── New tables owned by this app ─────────────────────────────────────
class SectorScoreCache(Base):
    """
    Stores the computed sector technical score ONCE PER DAY per
    sector_index_symbol, so it doesn't get recomputed on every single
    stock analysis. A sector index's RSI/MACD/EMA only meaningfully
    changes once a day (after market close) -- recalculating it for
    every one of hundreds of stocks in the same sector during a batch
    run was pure waste, and was part of what triggered the Yahoo
    Finance rate-limiting issues.

    Keyed by sector_index_symbol (not sector name) since multiple
    sector labels can share a fallback index (^CRSLDX).
    """
    __tablename__ = "sector_score_cache"

    id                   = Column(BigInteger, primary_key=True, autoincrement=True)
    sector_index_symbol  = Column(String(20), unique=True, index=True, nullable=False)

    sector_strength_score = Column(Float)
    sector_trend          = Column(String(60))
    sector_outlook         = Column(Text)
    growth_drivers         = Column(JSON)
    risks                  = Column(JSON)
    raw_metrics             = Column(JSON)

    computed_at          = Column(TIMESTAMP, server_default=func.now(), index=True)


class StockAnalysisReport(Base):
    __tablename__ = "stock_analysis_reports"

    id          = Column(BigInteger, primary_key=True, autoincrement=True)
    stock_id    = Column(BigInteger, ForeignKey("stock_mstr.id"), index=True, nullable=False)
    symbol_code = Column(String(20), index=True)
    exchange    = Column(String(5))

    # Enrichment snapshot (copied from stock_mstr at analysis time)
    sector      = Column(String(100), nullable=True)
    industry    = Column(String(100), nullable=True)
    category    = Column(String(10),  nullable=True)

    overall_score     = Column(Float)
    fundamental_score = Column(Float)
    technical_score   = Column(Float)
    sector_score      = Column(Float)
    momentum_score    = Column(Float)

    verdict        = Column(String(20))
    confidence     = Column(String(20))
    probability_3_6m = Column(Float)

    swing_view         = Column(JSON)
    long_term_view     = Column(JSON)
    technical_detail   = Column(JSON)
    fundamental_detail = Column(JSON)
    sector_detail      = Column(JSON)
    momentum_detail    = Column(JSON)
    risk_factors       = Column(JSON)
    raw_quote          = Column(JSON)

    is_latest    = Column(Boolean, default=True, index=True)
    generated_at = Column(TIMESTAMP, server_default=func.now(), index=True)


class MarketOverview(Base):
    __tablename__ = "market_overview"

    id                = Column(BigInteger, primary_key=True, autoincrement=True)
    market_view       = Column(Text)
    favoured_sectors  = Column(JSON)
    avoid_sectors     = Column(JSON)
    key_risks         = Column(JSON)
    key_opportunities = Column(JSON)
    raw               = Column(JSON)
    generated_at      = Column(TIMESTAMP, server_default=func.now())


class AnalysisJob(Base):
    __tablename__ = "analysis_jobs"

    id             = Column(BigInteger, primary_key=True, autoincrement=True)
    job_type       = Column(String(20))
    status         = Column(String(20), default="pending")
    total          = Column(Integer, default=0)
    completed      = Column(Integer, default=0)
    failed         = Column(Integer, default=0)
    symbols        = Column(JSON)
    result_summary = Column(JSON)
    error          = Column(Text, nullable=True)
    created_at     = Column(TIMESTAMP, server_default=func.now())
    updated_at     = Column(TIMESTAMP, onupdate=func.now())
    completed_at   = Column(TIMESTAMP, nullable=True)


def init_db() -> None:
    """Add new columns to stock_analysis_reports if they don't exist, create new tables."""
    from sqlalchemy import text, inspect
    with engine.connect() as conn:
        inspector = inspect(engine)
        existing  = [c["name"] for c in inspector.get_columns("stock_analysis_reports")] \
                    if "stock_analysis_reports" in inspector.get_table_names() else []

        for col, definition in [
            ("sector",   "VARCHAR(100) NULL"),
            ("industry", "VARCHAR(100) NULL"),
            ("category", "VARCHAR(10)  NULL"),
        ]:
            if existing and col not in existing:
                conn.execute(text(f"ALTER TABLE stock_analysis_reports ADD COLUMN `{col}` {definition}"))
                conn.commit()

    Base.metadata.create_all(
        bind=engine,
        tables=[
            StockAnalysisReport.__table__,
            MarketOverview.__table__,
            AnalysisJob.__table__,
            SectorScoreCache.__table__,
            PriceHistoryDaily.__table__,
            PriceHistoryWeekly.__table__,
            PriceHistoryMonthly.__table__,
            NiftyHistoryWeekly.__table__,
            StockTechnicalScore.__table__,
        ],
    )


def get_db():
    db: Session = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ── Price History Tables ──────────────────────────────────────────────────────

class PriceHistoryDaily(Base):
    """
    Daily OHLCV for all active EQUITY stocks.
    3 years of history (~750 rows per stock).
    Updated by the daily price job after market close.
    """
    __tablename__ = "price_history_daily"
    __table_args__ = (
        {"mysql_engine": "InnoDB", "mysql_row_format": "COMPRESSED"},
    )

    id          = Column(BigInteger, primary_key=True, autoincrement=True)
    symbol_code = Column(String(20), nullable=False, index=True)
    date        = Column(TIMESTAMP, nullable=False, index=True)
    open        = Column(Float)
    high        = Column(Float)
    low         = Column(Float)
    close       = Column(Float, nullable=False)
    volume      = Column(BigInteger)


class PriceHistoryWeekly(Base):
    """
    Weekly OHLCV for all active EQUITY stocks.
    3 years of history (~156 rows per stock).
    Updated every Monday after market close.
    """
    __tablename__ = "price_history_weekly"
    __table_args__ = (
        {"mysql_engine": "InnoDB", "mysql_row_format": "COMPRESSED"},
    )

    id          = Column(BigInteger, primary_key=True, autoincrement=True)
    symbol_code = Column(String(20), nullable=False, index=True)
    week_start  = Column(TIMESTAMP, nullable=False, index=True)
    open        = Column(Float)
    high        = Column(Float)
    low         = Column(Float)
    close       = Column(Float, nullable=False)
    volume      = Column(BigInteger)


class PriceHistoryMonthly(Base):
    """
    Monthly OHLCV for all active EQUITY stocks.
    5 years of history (~60 rows per stock).
    Updated on first trading day of each month.
    """
    __tablename__ = "price_history_monthly"
    __table_args__ = (
        {"mysql_engine": "InnoDB", "mysql_row_format": "COMPRESSED"},
    )

    id          = Column(BigInteger, primary_key=True, autoincrement=True)
    symbol_code = Column(String(20), nullable=False, index=True)
    month_start = Column(TIMESTAMP, nullable=False, index=True)
    open        = Column(Float)
    high        = Column(Float)
    low         = Column(Float)
    close       = Column(Float, nullable=False)
    volume      = Column(BigInteger)


class NiftyHistoryWeekly(Base):
    """
    Nifty 50 weekly OHLCV — shared benchmark for RS Line calculation.
    All stocks use this single table instead of each fetching Nifty separately.
    """
    __tablename__ = "nifty_history_weekly"

    id         = Column(BigInteger, primary_key=True, autoincrement=True)
    week_start = Column(TIMESTAMP, nullable=False, unique=True, index=True)
    open       = Column(Float)
    high       = Column(Float)
    low        = Column(Float)
    close      = Column(Float, nullable=False)
    volume     = Column(BigInteger)


class StockTechnicalScore(Base):
    """
    Stores computed technical scores per stock per analysis.
    Includes all 5 component scores so we can later use outcomes
    to recalibrate weights (the learning system — Point 3).
    outcome_30d/60d/90d filled by nightly outcome job.
    """
    __tablename__ = "stock_technical_scores"

    id              = Column(BigInteger, primary_key=True, autoincrement=True)
    symbol_code     = Column(String(20), nullable=False, index=True)
    analysis_date   = Column(TIMESTAMP, nullable=False, index=True)
    price_at_analysis = Column(Float)

    # 5 component scores
    score_weekly_base    = Column(Float)  # Component 1: 0-30
    score_breakout_pos   = Column(Float)  # Component 2: 0-25
    score_macd_multi_tf  = Column(Float)  # Component 3: 0-25
    score_rs_line        = Column(Float)  # Component 4: 0-10
    score_weekly_volume  = Column(Float)  # Component 5: 0-10
    total_technical      = Column(Float)  # 0-100

    # Stage and key signals for filtering/research
    weekly_stage        = Column(String(20))
    base_weeks          = Column(Integer)
    base_range_pct      = Column(Float)
    pct_from_52w_high   = Column(Float)
    rs_line_state       = Column(String(30))
    monthly_macd_state  = Column(String(30))
    weekly_macd_state   = Column(String(30))
    disqualifiers       = Column(JSON)

    # Outcomes — filled by nightly job 30/60/90 days later
    outcome_30d  = Column(Float, nullable=True)
    outcome_60d  = Column(Float, nullable=True)
    outcome_90d  = Column(Float, nullable=True)
    is_correct_30d = Column(Boolean, nullable=True)
    is_correct_60d = Column(Boolean, nullable=True)
    is_correct_90d = Column(Boolean, nullable=True)