"""
Batch analysis jobs — VTrader Stock Analyser
"""

from __future__ import annotations

import time
import traceback
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from typing import List, Optional

from .config import get_settings
from .database import AnalysisJob, StockMstr, SessionLocal
from .analysis import orchestrator

settings = get_settings()


def _analyze_one(stock_id: int, delay: float = 0.3, retry: bool = True) -> dict:
    """
    Runs in a worker thread with its own DB session.
    Small delay at START of each call to stagger Yahoo Finance requests.
    Retries once on failure.
    """
    time.sleep(delay)   # stagger HERE inside worker, not in submission loop

    db = SessionLocal()
    try:
        stock = db.query(StockMstr).filter(StockMstr.id == stock_id).first()
        if not stock:
            return {"stock_id": stock_id, "ok": False, "error": "Stock not found"}

        report = orchestrator.analyze_stock(db, stock)
        return {
            "stock_id":      stock_id,
            "symbol_code":   stock.symbol_code,
            "symbol_name":   stock.symbol_name,
            "ok":            True,
            "verdict":       report.verdict,
            "overall_score": report.overall_score,
        }

    except Exception as exc:
        err_msg = str(exc)
        trace   = traceback.format_exc(limit=3)

        if retry:
            db.close()
            time.sleep(2.0)
            return _analyze_one(stock_id, delay=0.0, retry=False)

        return {
            "stock_id": stock_id,
            "ok":       False,
            "error":    err_msg,
            "trace":    trace,
        }
    finally:
        db.close()


def run_batch_job(job_id: int, symbol_codes: Optional[List[str]] = None) -> None:
    db = SessionLocal()
    try:
        job = db.query(AnalysisJob).filter(AnalysisJob.id == job_id).first()
        if job is None:
            return

        from sqlalchemy import or_
        query = db.query(StockMstr).filter(StockMstr.is_active == True)  # noqa: E712
        if symbol_codes:
            query = query.filter(StockMstr.symbol_code.in_(symbol_codes))
        else:
            # Default batch: EQUITY stocks only — skip ETFs and MFs
            query = query.filter(
                or_(StockMstr.category == "EQUITY", StockMstr.category == None)  # noqa: E711
            )
        stocks = query.all()

        job.total     = len(stocks)
        job.status    = "running"
        job.completed = 0
        job.failed    = 0
        db.add(job)
        db.commit()

        results     = []
        concurrency = max(1, min(settings.batch_concurrency, 3))

        with ThreadPoolExecutor(max_workers=concurrency) as pool:
            # Submit ALL futures immediately — delay is inside each worker
            futures = {
                pool.submit(_analyze_one, s.id, 0.3): s
                for s in stocks
            }

            for future in as_completed(futures):
                result = future.result()
                results.append(result)

                if result.get("ok"):
                    job.completed = (job.completed or 0) + 1
                else:
                    job.failed = (job.failed or 0) + 1

                # Update progress every 5 stocks
                if (job.completed + job.failed) % 5 == 0:
                    db.add(job)
                    db.commit()

        # Final progress commit
        db.add(job)
        db.commit()

        # Summary
        verdict_counts: dict = {}
        errors = []
        for r in results:
            if r.get("ok"):
                v = r.get("verdict") or "Unknown"
                verdict_counts[v] = verdict_counts.get(v, 0) + 1
            else:
                errors.append({
                    "symbol_code": r.get("symbol_code", f"id:{r.get('stock_id')}"),
                    "error":       r.get("error", "unknown"),
                })

        job.status         = "completed"
        job.completed_at   = datetime.utcnow()
        job.result_summary = {
            "verdict_counts": verdict_counts,
            "total_errors":   len(errors),
            "errors":         errors[:50],
        }
        db.add(job)
        db.commit()

    except Exception as exc:
        try:
            job = db.query(AnalysisJob).filter(AnalysisJob.id == job_id).first()
            if job:
                job.status       = "failed"
                job.error        = f"{exc}\n{traceback.format_exc(limit=3)}"
                job.completed_at = datetime.utcnow()
                db.add(job)
                db.commit()
        except Exception:
            pass
    finally:
        db.close()