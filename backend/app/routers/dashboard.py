"""Dashboard aggregation endpoint."""

from collections import defaultdict
from fastapi import APIRouter, Depends
from sqlalchemy import or_
from sqlalchemy.orm import Session

from ..database import AnalysisJob, StockAnalysisReport, StockMstr, get_db
from ..analysis import orchestrator
from ..schemas import DashboardResponse, JobStatus, MarketOverviewSchema
from ..serializers import report_to_schema

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("", response_model=DashboardResponse)
def get_dashboard(top_n: int = 6, db: Session = Depends(get_db)):
    # Universe counts
    total_stocks  = db.query(StockMstr).filter(StockMstr.is_active == True).count()  # noqa: E712
    equity_stocks = db.query(StockMstr).filter(
        StockMstr.is_active == True,  # noqa: E712
        or_(StockMstr.category == "EQUITY", StockMstr.category == None)  # noqa: E711
    ).count()

    # Category breakdown
    from sqlalchemy import func
    cat_rows = (
        db.query(StockMstr.category, func.count(StockMstr.id))
        .filter(StockMstr.is_active == True)  # noqa: E712
        .group_by(StockMstr.category)
        .all()
    )
    category_counts = {(r[0] or "UNKNOWN"): r[1] for r in cat_rows}

    # Latest reports
    latest_reports = (
        db.query(StockAnalysisReport)
        .filter(StockAnalysisReport.is_latest == True)  # noqa: E712
        .all()
    )
    analyzed_stocks = len(latest_reports)

    verdict_counts:  dict = defaultdict(int)
    sector_scores:   dict = defaultdict(list)
    industry_scores: dict = defaultdict(list)

    for r in latest_reports:
        verdict_counts[r.verdict or "Unknown"] += 1
        if r.sector and r.sector_score is not None:
            sector_scores[r.sector].append(r.sector_score)
        industry = r.industry
        if industry and r.sector_score is not None:
            industry_scores[industry].append(r.sector_score)

    sector_strength = sorted(
        [{"sector": s, "avg_score": round(sum(v)/len(v), 1), "count": len(v)} for s, v in sector_scores.items()],
        key=lambda x: x["avg_score"], reverse=True
    )
    industry_strength = sorted(
        [{"industry": s, "avg_score": round(sum(v)/len(v), 1), "count": len(v)} for s, v in industry_scores.items()],
        key=lambda x: x["avg_score"], reverse=True
    )[:20]

    # Top picks: Buy/Strong Buy, EQUITY only, sorted by score
    equity_only = [r for r in latest_reports if r.category not in ("ETF", "MF")]
    candidates  = [r for r in equity_only if r.verdict in ("Strong Buy", "Buy")]
    if not candidates:
        candidates = equity_only
    candidates.sort(key=lambda r: r.overall_score or 0, reverse=True)

    top_picks = []
    for r in candidates[:top_n]:
        stock = db.query(StockMstr).filter(StockMstr.id == r.stock_id).first()
        top_picks.append(report_to_schema(r, stock))

    overview = orchestrator.get_latest_market_overview(db)
    overview_schema = MarketOverviewSchema(
        market_view       = overview.market_view,
        favoured_sectors  = overview.favoured_sectors or [],
        avoid_sectors     = overview.avoid_sectors    or [],
        key_risks         = overview.key_risks        or [],
        key_opportunities = overview.key_opportunities or [],
        generated_at      = overview.generated_at,
    ) if overview else None

    last_job = db.query(AnalysisJob).order_by(AnalysisJob.id.desc()).first()

    return DashboardResponse(
        market_overview   = overview_schema,
        verdict_counts    = dict(verdict_counts),
        sector_strength   = sector_strength,
        industry_strength = industry_strength,
        top_picks         = top_picks,
        last_batch_job    = JobStatus.model_validate(last_job) if last_job else None,
        total_stocks      = total_stocks,
        equity_stocks     = equity_stocks,
        analyzed_stocks   = analyzed_stocks,
        category_counts   = category_counts,
    )


@router.get("/sector-summary")
def get_sector_summary(db: Session = Depends(get_db)):
    """
    Per-sector breakdown for the Sector Strength card UI.

    Shows:
    - sector_score: the SECTOR INDEX technical score (RSI/MACD/EMA/RS
      of the actual Nifty sector index) from sector_score_cache.
      This is the "how strong is this sector right now" signal.
    - verdict_counts: count of Strong Buy/Buy/Watchlist/Avoid within
      the sector, for the stacked bar chart.
    - best/worst stock by overall_score.
    - stock_count: total analysed stocks in sector.

    Sorted by sector_score (index strength) descending.
    """
    from ..database import SectorScoreCache

    latest_reports = (
        db.query(StockAnalysisReport)
        .filter(
            StockAnalysisReport.is_latest == True,  # noqa: E712
            StockAnalysisReport.category.notin_(["ETF", "MF"]),
        )
        .all()
    )

    # Load sector index scores from daily cache
    cache_rows = db.query(SectorScoreCache).all()
    sector_index_scores: dict = {row.sector_index_symbol: row.sector_strength_score for row in cache_rows}

    # Pull sector_index_symbol per sector from stock_mstr
    from ..database import StockMstr
    sector_to_index: dict = {}
    index_rows = (
        db.query(StockMstr.sector, StockMstr.sector_index_symbol)
        .filter(StockMstr.sector != None, StockMstr.sector_index_symbol != None)  # noqa: E711
        .distinct()
        .all()
    )
    for row in index_rows:
        if row.sector not in sector_to_index:
            sector_to_index[row.sector] = row.sector_index_symbol

    by_sector: dict = defaultdict(list)
    for r in latest_reports:
        if r.sector and r.overall_score is not None:
            by_sector[r.sector].append(r)

    summary = []
    for sector_name, reports in by_sector.items():
        # Verdict breakdown for stacked bar
        verdict_counts = {"Strong Buy": 0, "Buy": 0, "Watchlist": 0, "Avoid": 0}
        for r in reports:
            v = r.verdict or "Watchlist"
            if v in verdict_counts:
                verdict_counts[v] += 1

        best  = max(reports, key=lambda r: r.overall_score or 0)
        worst = min(reports, key=lambda r: r.overall_score or 0)

        # Use real sector index score if available in daily cache
        idx_sym        = sector_to_index.get(sector_name)
        sector_score   = sector_index_scores.get(idx_sym) if idx_sym else None
        # Fallback: avg stock sector_score from their latest reports
        if sector_score is None:
            ss_vals = [r.sector_score for r in reports if r.sector_score is not None]
            sector_score = round(sum(ss_vals) / len(ss_vals), 1) if ss_vals else 50.0

        summary.append({
            "sector": sector_name,
            "stock_count": len(reports),
            "sector_score": round(sector_score, 1),
            "verdict_counts": verdict_counts,
            "best_stock": {
                "symbol_code": best.symbol_code,
                "score": round(best.overall_score, 1),
            },
            "worst_stock": {
                "symbol_code": worst.symbol_code,
                "score": round(worst.overall_score, 1),
            },
        })

    # Sort by sector index score — strongest sector first
    summary.sort(key=lambda x: x["sector_score"], reverse=True)
    return {"sectors": summary}


@router.post("/refresh-market-overview", response_model=MarketOverviewSchema)
def refresh_market_overview(db: Session = Depends(get_db)):
    overview = orchestrator.refresh_market_overview(db)
    return MarketOverviewSchema(
        market_view       = overview.market_view,
        favoured_sectors  = overview.favoured_sectors or [],
        avoid_sectors     = overview.avoid_sectors    or [],
        key_risks         = overview.key_risks        or [],
        key_opportunities = overview.key_opportunities or [],
        generated_at      = overview.generated_at,
    )