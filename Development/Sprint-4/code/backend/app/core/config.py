from functools import lru_cache
from pathlib import Path
from typing import Optional

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings

BACKEND_ROOT = Path(__file__).resolve().parents[2]
ENV_FILE = BACKEND_ROOT / ".env"


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # Database
    DATABASE_URL: str

    # JWT
    JWT_SECRET_KEY: str
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30

    # CORS
    FRONTEND_URL: str = "http://localhost:3000"
    ENABLE_DEBUG: bool = False

    # Cache (standby mode)
    CACHE_ENABLED: bool = False
    CACHE_TTL_SECONDS: int = 600

    # LLM
    OPENAI_API_KEY: str | None = None
    OPENAI_MODEL: str = Field(
        default="gpt-4o-mini",
        validation_alias=AliasChoices("VIZAGENT_MODEL", "OPENAI_MODEL"),
    )

    # Minimal alerts MVP (additive, standalone runner)
    ALERTS_ENABLED: bool = False
    ALERT_STATE_FILE: str = "out/alerts_state.json"
    ALERT_EMAIL_TO: str = ""
    ALERT_EMAIL_FROM: str = ""
    SMTP_HOST: str = ""
    SMTP_PORT: int = 587
    SMTP_USER: Optional[str] = None
    SMTP_PASSWORD: Optional[str] = None
    SMTP_USE_TLS: bool = True

    class Config:
        env_file = str(ENV_FILE)
        case_sensitive = True
        extra = "ignore"


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
