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


# ── New tables owned by this app ─────────────────────────────────────
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
        ],
    )


def get_db():
    db: Session = SessionLocal()
    try:
        yield db
    finally:
        db.close()