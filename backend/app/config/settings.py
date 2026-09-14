from functools import lru_cache
from typing import Optional, List, Union
from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application configuration."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    # Application
    APP_NAME: str = "VEXUS"
    APP_ENV: str = "development"
    DEBUG: bool = True
    # No default: SECRET_KEY signs every JWT in the system, so a
    # deployment that forgets to set it must fail loudly at startup
    # (a pydantic ValidationError) rather than silently running with a
    # known, working value. This file previously defaulted to
    # "dev-secret-key-change-me" -- since this is a public repo, that
    # exact string was public too, which would let anyone forge a
    # valid admin JWT against any deployment that never overrode it.
    SECRET_KEY: str
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # Database
    DATABASE_URL: str = "sqlite:///./vexus.db"
    POSTGRES_PASSWORD: Optional[str] = None
    
    # Redis
    REDIS_URL: Optional[str] = None
    
    # Frontend
    FRONTEND_URL: str = "http://localhost:5173"
    
    # Rate Limiting
    RATE_LIMIT_AUTH_REQUESTS: int = 5
    RATE_LIMIT_AUTH_WINDOW_MINUTES: int = 15
    LOGIN_RATE_LIMIT: str = "5/minute"
    
    # Security
    CORS_ORIGINS: str = "http://localhost:5173"
    SECURE_HEADERS_ENABLED: bool = True
    
    # Discovery & Scanning
    AUTHORIZED_SCAN_RANGES: Union[List[str], str, None] = None
    DISCOVERY_COLLECTOR: str = "auto"
    DISCOVERY_PORTS: Union[List[int], str] = [22, 80, 443, 445, 3389, 8000, 8080]
    DISCOVERY_TIMEOUT_SECONDS: float = 0.35
    DISCOVERY_MAX_WORKERS: int = 64

    # Background scheduler (V2: recurring monitoring/detection/discovery/
    # sense evaluation instead of requiring a manual API call every time).
    # Off by default: an opt-in flag rather than tied to APP_ENV, so a
    # test run (which exercises the FastAPI lifespan via `with
    # TestClient(app)`) never starts real background loops against
    # whatever DATABASE_URL happens to be configured for the test
    # process — every existing test's DB access goes through the
    # `get_db` dependency override instead, which this intentionally
    # bypasses (see app/core/scheduler.py).
    SCHEDULER_ENABLED: bool = False
    SCHEDULER_MONITORING_INTERVAL_SECONDS: int = 300
    SCHEDULER_DETECTION_INTERVAL_SECONDS: int = 120
    SCHEDULER_DISCOVERY_INTERVAL_SECONDS: int = 3600
    SCHEDULER_SENSE_INTERVAL_SECONDS: int = 900

    # Threat Intelligence (NVD CVE feed)
    NVD_ENABLED: bool = False
    NVD_API_URL: str = "https://services.nvd.nist.gov/rest/json"
    NVD_API_KEY: Optional[str] = None
    NVD_TIMEOUT_SECONDS: float = 15.0
    # Manual, per-CVE sync only (POST /threat-intel/sync/cve/{id}) makes a
    # real outbound call to NVD's API and can block a worker thread for up
    # to NVD_TIMEOUT_SECONDS -- rate limited for the same reason login is:
    # protects both NVD's service (repeated hammering risks the
    # deployment's IP getting rate-limited/banned by NVD) and this
    # server's own thread pool from being exhausted by rapid repeated
    # syncs.
    THREAT_INTEL_SYNC_RATE_LIMIT: str = "10/minute"

    # AI Configuration
    AI_PROVIDER: str = "none"
    DEEPSEEK_API_KEY: Optional[str] = None
    DEEPSEEK_MODEL: str = "deepseek-chat"
    CLOUD_AI_PROVIDER: str = "anthropic"
    CLOUD_AI_MODEL: str = "claude-3-sonnet-20241022"
    ANTHROPIC_API_KEY: Optional[str] = None
    LOCAL_AI_URL: str = "http://127.0.0.1:11434"
    LOCAL_AI_MODEL: str = "llama3.2:3b"
    LOCAL_AI_TIMEOUT_SECONDS: float = 120.0
    
    # Admin User
    VEXUS_ADMIN_USERNAME: str = "admin"
    VEXUS_ADMIN_EMAIL: str = "admin@vexus.local"
    VEXUS_ADMIN_PASSWORD: Optional[str] = None
    
    @property
    def cors_origins_list(self) -> List[str]:
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",")]
    
    @property
    def is_development(self) -> bool:
        return self.APP_ENV == "development"
    
    @property
    def is_testing(self) -> bool:
        return self.APP_ENV == "testing"
    
    @property
    def use_sqlite(self) -> bool:
        return self.DATABASE_URL.startswith("sqlite")
    
    @field_validator('AUTHORIZED_SCAN_RANGES', mode='before')
    @classmethod
    def parse_authorized_scan_ranges(cls, v):
        """Parse AUTHORIZED_SCAN_RANGES from string to list."""
        if v is None:
            return []
        if isinstance(v, list):
            return v
        if isinstance(v, str):
            v = v.strip()
            if v.startswith('[') and v.endswith(']'):
                v = v[1:-1]
            if not v:
                return []
            return [item.strip().strip('"').strip("'") for item in v.split(',') if item.strip()]
        return []
    
    @property
    def authorized_scan_ranges_list(self) -> List[str]:
        """Get authorized scan ranges as a list."""
        if isinstance(self.AUTHORIZED_SCAN_RANGES, list):
            return self.AUTHORIZED_SCAN_RANGES
        return []

    @property
    def discovery_ports_list(self) -> List[int]:
        if isinstance(self.DISCOVERY_PORTS, list):
            return self.DISCOVERY_PORTS
        if isinstance(self.DISCOVERY_PORTS, str):
            return [int(port.strip()) for port in self.DISCOVERY_PORTS.split(",") if port.strip()]
        return []


# Create a global settings instance
settings = Settings()


@lru_cache()
def get_settings() -> Settings:
    """Get the settings instance (cached; tests call .cache_clear() after
    changing environment variables via monkeypatch)."""
    return Settings()