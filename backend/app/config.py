"""
Central configuration for the Swing Trade Analysis System.

All values are read from environment variables (see .env.example).
NOTHING is hardcoded here on purpose -- credentials live in your `.env`
file only, which should NEVER be committed to source control.
"""

import os
from functools import lru_cache
from typing import List
from urllib.parse import quote_plus 

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # ---------------------------------------------------------------
    # MySQL (knowingly_trade.stock_mstr lives here)
    # ---------------------------------------------------------------
    db_host: str = "127.0.0.1"
    db_port: int = 3306
    db_user: str = "root"
    db_password: str = ""
    db_name: str = "knowingly_trade"

    @property
    def sqlalchemy_database_uri(self) -> str:
        password = quote_plus(self.db_password)
        return (
            f"mysql+pymysql://{self.db_user}:{password}"
            f"@{self.db_host}:{self.db_port}/{self.db_name}?charset=utf8mb4"
        )

    # ---------------------------------------------------------------
    # Claude / Anthropic -- used for the qualitative research engine
    # (fundamentals, sector view, narrative, long-term thesis, etc.)
    # ---------------------------------------------------------------
    anthropic_api_key: str = ""
    claude_model: str = "claude-sonnet-4-6"
    claude_max_tokens: int = 4000
    # Enable Claude's hosted web_search tool so the analysis reflects
    # current news / results / price targets at request time.
    claude_enable_web_search: bool = True
    claude_max_search_uses: int = 6

    # ---------------------------------------------------------------
    # Market data provider
    #   mock   -> deterministic synthetic OHLCV (no external calls,
    #             useful for local dev / demos without API keys)
    #   fyers  -> Fyers v3 REST API (matches the `token_id` column
    #             already present in stock_mstr)
    #   yfinance -> Yahoo Finance fallback (symbol.NS / symbol.BO)
    # ---------------------------------------------------------------
    market_data_provider: str = "mock"

    fyers_app_id: str = ""
    fyers_access_token: str = ""
    fyers_base_url: str = "https://api-t1.fyers.in/data"

    # ---------------------------------------------------------------
    # Analysis behaviour
    # ---------------------------------------------------------------
    # Weighting from the original screening framework
    weight_fundamental: float = 0.25
    weight_technical: float = 0.40
    weight_sector: float = 0.20
    weight_momentum: float = 0.15

    # How long a cached report is considered "fresh" before the
    # dashboard suggests re-running it (minutes).
    report_freshness_minutes: int = 240

    # Max parallel stock analyses when running a batch job
    batch_concurrency: int = 3

    # ---------------------------------------------------------------
    # API / CORS
    # ---------------------------------------------------------------
    cors_origins: List[str] = ["*"]
    api_prefix: str = "/api"


@lru_cache
def get_settings() -> Settings:
    return Settings()
