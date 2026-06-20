"""Stock listing, search, and individual stock detail."""

from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import or_, func
from sqlalchemy.orm import Session

from ..database import StockAnalysisReport, StockMstr, get_db
from ..analysis import orchestrator
from ..schemas import StockListResponse, StockReport, StockSummary
from ..serializers import stock_to_summary, report_to_schema

router = APIRouter(prefix="/stocks", tags=["stocks"])


@router.get("", response_model=StockListResponse)
def list_stocks(
    q:        Optional[str] = Query(None, description="Search by symbol, company name, sector or industry"),
    verdict:  Optional[str] = Query(None),
    sector:   Optional[str] = Query(None),
    industry: Optional[str] = Query(None),
    exchange: Optional[str] = Query(None),
    category: Optional[str] = Query(None, description="EQUITY | ETF | MF — defaults to EQUITY only"),
    limit:    int = Query(500, le=2000),
    offset:   int = 0,
    db: Session = Depends(get_db),
):
    query = db.query(StockMstr).filter(StockMstr.is_active == True)  # noqa: E712

    # Default: show EQUITY only (exclude ETF and MF from the analysis universe)
    # unless caller explicitly requests a specific category or "all"
    if category and category.upper() == "ALL":
        pass   # show everything
    elif category:
        query = query.filter(StockMstr.category == category.upper())
    else:
        # Default to EQUITY — but also include rows where category is NULL
        # (legacy rows that haven't been categorised yet)
        query = query.filter(
            or_(StockMstr.category == "EQUITY", StockMstr.category == None)  # noqa: E711
        )

    if exchange:
        query = query.filter(StockMstr.exchange == exchange)
    if sector:
        query = query.filter(StockMstr.sector == sector)
    if industry:
        query = query.filter(StockMstr.industry == industry)
    if q:
        like = f"%{q}%"
        query = query.filter(or_(
            StockMstr.symbol_code.like(like),
            StockMstr.symbol_name.like(like),
            StockMstr.sector.like(like),
            StockMstr.industry.like(like),
        ))

    total  = query.count()
    stocks = query.order_by(StockMstr.symbol_name.asc()).offset(offset).limit(limit).all()

    stock_ids = [s.id for s in stocks]
    reports_by_stock = {}
    if stock_ids:
        latest = (
            db.query(StockAnalysisReport)
            .filter(
                StockAnalysisReport.stock_id.in_(stock_ids),
                StockAnalysisReport.is_latest == True,  # noqa: E712
            )
            .all()
        )
        reports_by_stock = {r.stock_id: r for r in latest}

    items = []
    for stock in stocks:
        report = reports_by_stock.get(stock.id)
        if verdict and (not report or report.verdict != verdict):
            continue
        items.append(stock_to_summary(stock, report))

    return StockListResponse(total=total, items=items)


@router.get("/meta/sectors", response_model=List[str])
def list_sectors(db: Session = Depends(get_db)):
    """All distinct sectors in the EQUITY universe."""
    rows = (
        db.query(StockMstr.sector)
        .filter(StockMstr.is_active == True, StockMstr.sector != None,  # noqa: E711, E712
                or_(StockMstr.category == "EQUITY", StockMstr.category == None))  # noqa: E711
        .distinct()
        .order_by(StockMstr.sector.asc())
        .all()
    )
    return [r.sector for r in rows if r.sector]


@router.get("/meta/industries", response_model=List[str])
def list_industries(sector: Optional[str] = None, db: Session = Depends(get_db)):
    """All distinct industries, optionally filtered by sector."""
    q = (
        db.query(StockMstr.industry)
        .filter(StockMstr.is_active == True, StockMstr.industry != None,  # noqa: E711, E712
                or_(StockMstr.category == "EQUITY", StockMstr.category == None))  # noqa: E711
    )
    if sector:
        q = q.filter(StockMstr.sector == sector)
    rows = q.distinct().order_by(StockMstr.industry.asc()).all()
    return [r.industry for r in rows if r.industry]


@router.get("/{symbol_code}", response_model=StockReport)
def get_stock(symbol_code: str, db: Session = Depends(get_db)):
    stock = db.query(StockMstr).filter(StockMstr.symbol_code == symbol_code).first()
    if not stock:
        raise HTTPException(status_code=404, detail="Stock not found")
    report = orchestrator.get_latest_report(db, stock.id)
    if not report:
        raise HTTPException(
            status_code=404,
            detail="No analysis yet. Click Analyse Now to generate a report.",
        )
    return report_to_schema(report, stock)