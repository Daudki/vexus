"""
Central application configuration.

All configuration is loaded from environment variables (see .env.example).
Never hardcode secrets here. This module is imported everywhere via the
`get_settings()` cached accessor so settings are read once per process.
"""
from functools import lru_cache
from typing import List

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # --- App ---
    APP_NAME: str = "VEXUS"
    APP_ENV: str = "development"  # development | staging | production
    DEBUG: bool = True

    # --- Security ---
    SECRET_KEY: str  # required, no default — must come from .env
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # --- CORS ---
    CORS_ORIGINS: List[str] = ["http://localhost:5173"]

    # --- Database ---
    # Falls back to local SQLite for development; use PostgreSQL in production.
    DATABASE_URL: str = "sqlite:///./vexus_dev.db"

    # --- Redis (job queue, rate limiting) ---
    REDIS_URL: str = "redis://localhost:6379/0"

    # --- Discovery safety ---
    # Discovery scans are refused for any target outside these CIDR ranges.
    # This is intentionally empty by default — an operator must explicitly
    # authorize ranges before any scan can run.
    AUTHORIZED_SCAN_RANGES: List[str] = []

    # --- AI provider ---
    AI_PROVIDER: str = "none"  # none | cloud | local
    ANTHROPIC_API_KEY: str = ""
    # Update to whichever model string your API key has access to.
    AI_MODEL: str = "claude-sonnet-4-5-20250929"

    # --- Rate limiting ---
    LOGIN_RATE_LIMIT: str = "5/minute"


@lru_cache
def get_settings() -> Settings:
    return Settings()
