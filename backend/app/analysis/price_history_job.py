"""
price_history_job.py — DB-backed OHLCV storage for all active EQUITY stocks
"""
from __future__ import annotations

import argparse
import logging
import re
import time
from datetime import datetime, timedelta
from typing import Optional

import pandas as pd
import yfinance as yf
from sqlalchemy.orm import Session

try:
    from .database import (
        SessionLocal, StockMstr,
        PriceHistoryDaily, PriceHistoryWeekly, PriceHistoryMonthly,
        NiftyHistoryWeekly, engine,
    )
except ImportError:
    from app.database import (
        SessionLocal, StockMstr,
        PriceHistoryDaily, PriceHistoryWeekly, PriceHistoryMonthly,
        NiftyHistoryWeekly, engine,
    )

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)

NIFTY_SYMBOL     = "^NSEI"
DAILY_LOOKBACK   = "3y"
WEEKLY_LOOKBACK  = "3y"
MONTHLY_LOOKBACK = "5y"
INITIAL_LOAD_DELAY = 1.2
RETRY_DELAYS = [3, 6, 12]


def _clean_symbol(symbol_code: str) -> str:
    return re.sub(r"[-_](EQ|BE|BL|GC|IL|SM|ST|N1|N2|N3|N4|W1|W2|W3|W4)$", "",
                  symbol_code.strip().upper())


def _yf_symbol(symbol_code: str, exchange: str) -> str:
    clean  = _clean_symbol(symbol_code)
    suffix = ".BO" if (exchange or "NSE").upper() == "BSE" else ".NS"
    return f"{clean}{suffix}"


def _safe_float(val, default: Optional[float] = None) -> Optional[float]:
    if val is None or (isinstance(val, float) and pd.isna(val)):
        return default
    try:
        f = float(val)
        return default if pd.isna(f) else f
    except (TypeError, ValueError):
        return default


def _safe_int(val, default: int = 0) -> int:
    f = _safe_float(val)
    return default if f is None else int(f)


def _fetch_yf(symbol: str, period: str, interval: str = "1d") -> pd.DataFrame:
    for attempt, wait in enumerate([0] + RETRY_DELAYS):
        if wait:
            time.sleep(wait)
        try:
            df = yf.Ticker(symbol).history(period=period, interval=interval, auto_adjust=True)
            if not df.empty:
                df.index = pd.to_datetime(df.index).tz_localize(None)
                return df
        except Exception as e:
            msg = str(e)
            if "429" in msg or "Too Many Requests" in msg:
                log.warning(f"429 on {symbol} attempt {attempt+1}")
            elif attempt >= len(RETRY_DELAYS):
                log.error(f"Failed {symbol}: {msg[:80]}")
    return pd.DataFrame()


def _upsert_daily(db: Session, symbol_code: str, df: pd.DataFrame) -> int:
    if df.empty: return 0
    inserted = 0
    for dt, row in df.iterrows():
        dt_clean = dt.to_pydatetime() if hasattr(dt, "to_pydatetime") else dt
        exists = db.query(PriceHistoryDaily).filter(
            PriceHistoryDaily.symbol_code == symbol_code,
            PriceHistoryDaily.date == dt_clean,
        ).first()
        if not exists:
            close = _safe_float(row.get("Close"))
            if close is None:
                continue
            db.add(PriceHistoryDaily(
                symbol_code=symbol_code, date=dt_clean,
                open=_safe_float(row.get("Open")),
                high=_safe_float(row.get("High")),
                low=_safe_float(row.get("Low")),
                close=close,
                volume=_safe_int(row.get("Volume")),
            ))
            inserted += 1
    if inserted: db.commit()
    return inserted


def _upsert_weekly(db: Session, symbol_code: str, df: pd.DataFrame) -> int:
    if df.empty: return 0
    inserted = 0
    for dt, row in df.iterrows():
        dt_clean = dt.to_pydatetime() if hasattr(dt, "to_pydatetime") else dt
        exists = db.query(PriceHistoryWeekly).filter(
            PriceHistoryWeekly.symbol_code == symbol_code,
            PriceHistoryWeekly.week_start == dt_clean,
        ).first()
        if not exists:
            close = _safe_float(row.get("Close"))
            if close is None:
                continue
            db.add(PriceHistoryWeekly(
                symbol_code=symbol_code, week_start=dt_clean,
                open=_safe_float(row.get("Open")),
                high=_safe_float(row.get("High")),
                low=_safe_float(row.get("Low")),
                close=close,
                volume=_safe_int(row.get("Volume")),
            ))
            inserted += 1
    if inserted: db.commit()
    return inserted


def _upsert_monthly(db: Session, symbol_code: str, df: pd.DataFrame) -> int:
    if df.empty: return 0
    inserted = 0
    for dt, row in df.iterrows():
        dt_clean = dt.to_pydatetime() if hasattr(dt, "to_pydatetime") else dt
        exists = db.query(PriceHistoryMonthly).filter(
            PriceHistoryMonthly.symbol_code == symbol_code,
            PriceHistoryMonthly.month_start == dt_clean,
        ).first()
        if not exists:
            close = _safe_float(row.get("Close"))
            if close is None:
                continue
            db.add(PriceHistoryMonthly(
                symbol_code=symbol_code, month_start=dt_clean,
                open=_safe_float(row.get("Open")),
                high=_safe_float(row.get("High")),
                low=_safe_float(row.get("Low")),
                close=close,
                volume=_safe_int(row.get("Volume")),
            ))
            inserted += 1
    if inserted: db.commit()
    return inserted


def _upsert_nifty_weekly(db: Session, df: pd.DataFrame) -> int:
    if df.empty: return 0
    inserted = 0
    for dt, row in df.iterrows():
        dt_clean = dt.to_pydatetime() if hasattr(dt, "to_pydatetime") else dt
        exists = db.query(NiftyHistoryWeekly).filter(
            NiftyHistoryWeekly.week_start == dt_clean,
        ).first()
        if not exists:
            close = _safe_float(row.get("Close"))
            if close is None:
                continue
            db.add(NiftyHistoryWeekly(
                week_start=dt_clean,
                open=_safe_float(row.get("Open")),
                high=_safe_float(row.get("High")),
                low=_safe_float(row.get("Low")),
                close=close,
                volume=_safe_int(row.get("Volume")),
            ))
            inserted += 1
    if inserted: db.commit()
    return inserted


def load_stock_history(db: Session, stock: StockMstr, mode: str = "initial") -> dict:
    sym    = _yf_symbol(stock.symbol_code, stock.exchange or "NSE")
    result = {"symbol": stock.symbol_code, "daily": 0, "weekly": 0, "monthly": 0, "errors": []}
    try:
        if mode == "initial":
            df_d = _fetch_yf(sym, DAILY_LOOKBACK, "1d")
            df_w = _fetch_yf(sym, WEEKLY_LOOKBACK, "1wk")
            df_m = _fetch_yf(sym, MONTHLY_LOOKBACK, "1mo")
            if df_d.empty and df_w.empty:
                sym2 = sym.replace(".NS", ".BO")
                df_d = _fetch_yf(sym2, DAILY_LOOKBACK, "1d")
                df_w = _fetch_yf(sym2, WEEKLY_LOOKBACK, "1wk")
                df_m = _fetch_yf(sym2, MONTHLY_LOOKBACK, "1mo")
            result["daily"]   = _upsert_daily(db, stock.symbol_code, df_d)
            result["weekly"]  = _upsert_weekly(db, stock.symbol_code, df_w)
            result["monthly"] = _upsert_monthly(db, stock.symbol_code, df_m)
        elif mode == "daily":
            df_d = _fetch_yf(sym, "5d", "1d")
            result["daily"] = _upsert_daily(db, stock.symbol_code, df_d)
            today = datetime.utcnow()
            if today.weekday() == 0:
                df_w = _fetch_yf(sym, "14d", "1wk")
                result["weekly"] = _upsert_weekly(db, stock.symbol_code, df_w)
            if today.day <= 3:
                df_m = _fetch_yf(sym, "65d", "1mo")
                result["monthly"] = _upsert_monthly(db, stock.symbol_code, df_m)
    except Exception as e:
        result["errors"].append(str(e)[:120])
    return result


def run_initial_load():
    log.info("=== INITIAL PRICE HISTORY LOAD STARTED ===")
    db = SessionLocal()
    log.info("Loading Nifty 50 weekly history...")
    nifty_df = _fetch_yf(NIFTY_SYMBOL, "3y", "1wk")
    log.info(f"Nifty: {_upsert_nifty_weekly(db, nifty_df)} weeks inserted")
    time.sleep(2)

    from sqlalchemy import or_
    stocks = db.query(StockMstr).filter(
        StockMstr.is_active == True,
        or_(StockMstr.category == "EQUITY", StockMstr.category == None),
    ).all()
    log.info(f"Loading history for {len(stocks)} EQUITY stocks...")

    total_d = total_w = total_m = errors = 0
    for i, stock in enumerate(stocks, 1):
        result = load_stock_history(db, stock, mode="initial")
        total_d += result["daily"]; total_w += result["weekly"]; total_m += result["monthly"]
        if result["errors"]: errors += 1; log.warning(f"  {stock.symbol_code}: {result['errors'][0]}")
        if i % 50 == 0:
            log.info(f"  Progress: {i}/{len(stocks)} | daily={total_d} weekly={total_w} monthly={total_m} errors={errors}")
        time.sleep(INITIAL_LOAD_DELAY)

    db.close()
    log.info(f"=== INITIAL LOAD COMPLETE === daily={total_d} weekly={total_w} monthly={total_m} errors={errors}")


def run_daily_update():
    log.info("=== DAILY PRICE UPDATE STARTED ===")
    db = SessionLocal()
    nifty_df = _fetch_yf(NIFTY_SYMBOL, "14d", "1wk")
    _upsert_nifty_weekly(db, nifty_df)
    time.sleep(1)

    from sqlalchemy import or_
    stocks = db.query(StockMstr).filter(
        StockMstr.is_active == True,
        or_(StockMstr.category == "EQUITY", StockMstr.category == None),
    ).all()

    total_d = errors = 0
    for i, stock in enumerate(stocks, 1):
        result = load_stock_history(db, stock, mode="daily")
        total_d += result["daily"]
        if result["errors"]: errors += 1
        time.sleep(0.4)
        if i % 100 == 0: log.info(f"  Progress: {i}/{len(stocks)} rows={total_d}")

    db.close()
    log.info(f"=== DAILY UPDATE COMPLETE === rows={total_d} errors={errors}")


def run_single(symbol_code: str):
    db = SessionLocal()
    stock = db.query(StockMstr).filter(StockMstr.symbol_code == symbol_code).first()
    if not stock:
        log.error(f"Stock not found: {symbol_code}"); db.close(); return
    result = load_stock_history(db, stock, mode="initial")
    log.info(f"{symbol_code}: daily={result['daily']} weekly={result['weekly']} monthly={result['monthly']}")
    if result["errors"]: log.error(f"Errors: {result['errors']}")
    db.close()


def get_price_history(db: Session, symbol_code: str) -> dict:
    """Called by orchestrator during analysis — reads from DB, no yfinance calls."""
    def _rows_to_df(rows, date_col):
        if not rows: return pd.DataFrame()
        data = [{"date": getattr(r, date_col), "open": r.open, "high": r.high,
                  "low": r.low, "close": r.close, "volume": r.volume} for r in rows]
        return pd.DataFrame(data).set_index("date").sort_index()

    daily_rows   = db.query(PriceHistoryDaily).filter(
        PriceHistoryDaily.symbol_code == symbol_code
    ).order_by(PriceHistoryDaily.date).all()
    weekly_rows  = db.query(PriceHistoryWeekly).filter(
        PriceHistoryWeekly.symbol_code == symbol_code
    ).order_by(PriceHistoryWeekly.week_start).all()
    monthly_rows = db.query(PriceHistoryMonthly).filter(
        PriceHistoryMonthly.symbol_code == symbol_code
    ).order_by(PriceHistoryMonthly.month_start).all()
    nifty_rows   = db.query(NiftyHistoryWeekly).order_by(NiftyHistoryWeekly.week_start).all()

    return {
        "daily":          _rows_to_df(daily_rows,   "date"),
        "weekly":         _rows_to_df(weekly_rows,  "week_start"),
        "monthly":        _rows_to_df(monthly_rows, "month_start"),
        "nifty_weekly":   _rows_to_df(nifty_rows,  "week_start"),
        "has_data":       len(daily_rows) >= 60,
        "weeks_available":  len(weekly_rows),
        "months_available": len(monthly_rows),
    }


def run_outcome_fill():
    try:
        from .database import StockTechnicalScore
    except ImportError:
        from app.database import StockTechnicalScore

    db = SessionLocal()
    now = datetime.utcnow()
    rows = db.query(StockTechnicalScore).filter(StockTechnicalScore.outcome_90d == None).all()
    filled = 0
    for row in rows:
        if not row.analysis_date or not row.price_at_analysis: continue
        for days, attr_price, attr_correct in [
            (30, "outcome_30d", "is_correct_30d"),
            (60, "outcome_60d", "is_correct_60d"),
            (90, "outcome_90d", "is_correct_90d"),
        ]:
            if getattr(row, attr_price) is not None: continue
            target_date = row.analysis_date + timedelta(days=days)
            if target_date > now: continue
            price_row = db.query(PriceHistoryDaily).filter(
                PriceHistoryDaily.symbol_code == row.symbol_code,
                PriceHistoryDaily.date >= target_date,
            ).order_by(PriceHistoryDaily.date).first()
            if price_row:
                ret = (price_row.close - row.price_at_analysis) / row.price_at_analysis * 100
                setattr(row, attr_price, round(ret, 2))
                setattr(row, attr_correct, ret > 5 if (row.total_technical or 0) >= 70 else ret < 5)
                filled += 1
    if filled: db.commit()
    db.close()
    log.info(f"Outcome fill: {filled} fields updated")