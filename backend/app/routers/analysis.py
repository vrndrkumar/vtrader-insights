from __future__ import annotations

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy.orm import Session

from ..database import AnalysisJob, StockMstr, get_db
from ..analysis import orchestrator
from ..jobs import run_batch_job
from ..schemas import AnalyzeRequest, JobStatus, StockReport
from ..serializers import report_to_schema

router = APIRouter(tags=["analysis"])


@router.post("/analyze/batch", response_model=JobStatus)
def analyze_batch(req: AnalyzeRequest, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    job_type = "selected" if req.symbols else "all"
    job = AnalysisJob(job_type=job_type, status="pending", symbols=req.symbols, total=0, completed=0, failed=0)
    db.add(job)
    db.commit()
    db.refresh(job)
    background_tasks.add_task(run_batch_job, job.id, req.symbols)
    return JobStatus.model_validate(job)


@router.post("/analyze/{symbol_code}", response_model=StockReport)
def analyze_single(symbol_code: str, db: Session = Depends(get_db)):
    stock = db.query(StockMstr).filter(StockMstr.symbol_code == symbol_code).first()
    if not stock:
        raise HTTPException(status_code=404, detail="Stock not found")
    report = orchestrator.analyze_stock(db, stock)
    return report_to_schema(report, stock)


@router.get("/jobs/{job_id}", response_model=JobStatus)
def get_job(job_id: int, db: Session = Depends(get_db)):
    job = db.query(AnalysisJob).filter(AnalysisJob.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return JobStatus.model_validate(job)


@router.get("/jobs", response_model=list[JobStatus])
def list_jobs(limit: int = 10, db: Session = Depends(get_db)):
    jobs = db.query(AnalysisJob).order_by(AnalysisJob.id.desc()).limit(limit).all()
    return [JobStatus.model_validate(j) for j in jobs]