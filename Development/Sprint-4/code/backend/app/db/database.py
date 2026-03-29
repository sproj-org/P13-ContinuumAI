from sqlalchemy import create_engine
from sqlalchemy import text
from sqlalchemy.orm import sessionmaker, declarative_base
from app.core.config import get_settings

settings = get_settings()

# Create database engine
engine = create_engine(settings.DATABASE_URL)

# Create session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Create declarative base for models
Base = declarative_base()


def get_db():
    """Dependency to get database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def create_tables():
    """Create all database tables."""
    Base.metadata.create_all(bind=engine)

    # Lightweight additive migration for pre-existing databases.
    with engine.begin() as conn:
        conn.execute(
            text(
                """
                ALTER TABLE saved_charts
                ADD COLUMN IF NOT EXISTS dashboard_name VARCHAR(120) NOT NULL DEFAULT 'Default'
                """
            )
        )
