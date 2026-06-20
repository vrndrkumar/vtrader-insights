"""
FastAPI entrypoint.

Run with:
    uvicorn app.main:app --reload --port 8000

On startup, ensures the three new tables (stock_analysis_reports,
market_overview, analysis_jobs) exist in `knowingly_trade`.
stock_mstr itself is never modified.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import get_settings
from .database import init_db
from .routers import stocks, analysis, dashboard

settings = get_settings()

app = FastAPI(
    title="Swing Trade Analysis System",
    description="Real-time fundamental + technical + sector + momentum analysis for the knowingly_trade stock universe.",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def on_startup():
    init_db()


@app.get("/api/health")
def health():
    return {
        "status": "ok",
        "market_data_provider": settings.market_data_provider,
        "llm_configured": bool(settings.anthropic_api_key),
    }


app.include_router(stocks.router, prefix=settings.api_prefix)
app.include_router(analysis.router, prefix=settings.api_prefix)
app.include_router(dashboard.router, prefix=settings.api_prefix)
