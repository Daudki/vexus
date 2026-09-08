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
    SECRET_KEY: str = "dev-secret-key-change-me"
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
    
    # AI Configuration
    AI_PROVIDER: str = "none"
    DEEPSEEK_API_KEY: Optional[str] = None
    DEEPSEEK_MODEL: str = "deepseek-chat"
    CLOUD_AI_PROVIDER: str = "anthropic"
    CLOUD_AI_MODEL: str = "claude-3-sonnet-20241022"
    ANTHROPIC_API_KEY: Optional[str] = None
    
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


# Create a global settings instance
settings = Settings()


@lru_cache()
def get_settings() -> Settings:
    """Get the settings instance (cached; tests call .cache_clear() after
    changing environment variables via monkeypatch)."""
    return Settings()