from pydantic_settings import BaseSettings
from functools import lru_cache


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

    # Cache (standby mode)
    CACHE_ENABLED: bool = False
    CACHE_TTL_SECONDS: int = 600

    # LLM
    OPENAI_API_KEY: str | None = "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"
    OPENAI_MODEL: str = "gpt-4o-mini"
    
    class Config:
        env_file = ".env"
        case_sensitive = True


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
