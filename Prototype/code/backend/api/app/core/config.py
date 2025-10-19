from typing import Optional
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    # Database settings
    DATABASE_URL: Optional[str] = None
    DB_HOST: str = "localhost"
    DB_PORT: int = 3306
    DB_USER: str = "root"
    DB_PASSWORD: str = ""
    DB_NAME: str = "continuum_ai"
    
    # API settings
    SECRET_KEY: str = "your-secret-key-change-this-in-production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    
    # Environment
    ENVIRONMENT: str = "development"
    
    # Build database URL if not provided
    @property
    def database_url(self) -> str:
        # Force SQLite in testing mode regardless of DATABASE_URL
        if self.ENVIRONMENT == "testing":
            return "sqlite:///./test_continuum.db"
        if self.DATABASE_URL:
            return self.DATABASE_URL
        return f"mysql+pymysql://{self.DB_USER}:{self.DB_PASSWORD}@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"
    
    class Config:
        env_file = ".env"
        case_sensitive = True


# Create global settings instance
settings = Settings()
# Add this line after the settings creation (line 34):
print(f"DEBUG: ENVIRONMENT = {settings.ENVIRONMENT}")
print(f"DEBUG: Database URL = {settings.database_url}")