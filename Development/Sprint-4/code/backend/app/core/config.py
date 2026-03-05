<<<<<<< HEAD
from pathlib import Path
from functools import lru_cache

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict
=======
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv
from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings

BACKEND_DIR = Path(__file__).resolve().parents[2]
ENV_FILE_PATH = BACKEND_DIR / ".env"
load_dotenv(dotenv_path=ENV_FILE_PATH, override=False)
>>>>>>> 7599888825e1aa7a1658e7d3beb0d95f793251d2


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
<<<<<<< HEAD
=======
    ENABLE_DEBUG: bool = False
>>>>>>> 7599888825e1aa7a1658e7d3beb0d95f793251d2

    # Cache (standby mode)
    CACHE_ENABLED: bool = False
    CACHE_TTL_SECONDS: int = 600

    # LLM
    OPENAI_API_KEY: str | None = None
    OPENAI_MODEL: str = Field(
        default="gpt-4o-mini",
<<<<<<< HEAD
        validation_alias=AliasChoices("VIZAGENT_MODEL", "OPENAI_MODEL"),
    )

    # Debug/runtime flags
    ENABLE_DEBUG: bool = False

    model_config = SettingsConfigDict(
        env_file=Path(__file__).resolve().parents[2] / ".env",
        case_sensitive=True,
    )
=======
        validation_alias=AliasChoices("OPENAI_MODEL", "VIZAGENT_MODEL"),
    )
    
    class Config:
        env_file = str(ENV_FILE_PATH)
        case_sensitive = True
        extra = "ignore"
>>>>>>> 7599888825e1aa7a1658e7d3beb0d95f793251d2


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
