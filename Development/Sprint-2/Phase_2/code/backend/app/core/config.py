from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    DATABASE_URL: str
    SECRET_KEY: str = "replace-me"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    ALGORITHM: str = "HS256"
    DEMO_TABLE: str = "sales_demo"
    CSV_PATH: str = "database/data/demo_sales.csv"
    FRONTEND_ORIGIN: str = "http://localhost:5173"
    OPENAI_API_KEY: str | None = None

    class Config:
        env_file = ".env"


@lru_cache
def get_settings() -> Settings:
    return Settings()
