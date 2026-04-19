import logging
from contextlib import suppress

from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session, declarative_base, sessionmaker

from app.core.config import get_settings

settings = get_settings()
logger = logging.getLogger(__name__)


def _build_engine_kwargs(database_url: str) -> dict[str, object]:
    url = make_url(database_url)
    backend = url.get_backend_name()
    driver = url.get_driver_name()
    kwargs: dict[str, object] = {}

    if backend == "postgresql":
        kwargs.update(
            pool_pre_ping=True,
            pool_recycle=1800,
            pool_use_lifo=True,
            pool_timeout=30,
        )
        if driver in {"psycopg2", "psycopg"}:
            kwargs["connect_args"] = {
                "keepalives": 1,
                "keepalives_idle": 30,
                "keepalives_interval": 10,
                "keepalives_count": 5,
            }

    return kwargs


def invalidate_db_session(db: Session) -> None:
    """Rollback and invalidate any checked-out connection after an operational failure."""
    with suppress(Exception):
        db.rollback()

    invalidate = getattr(db, "invalidate", None)
    if callable(invalidate):
        with suppress(Exception):
            invalidate()
        return

    with suppress(Exception):
        connection = db.connection()
        connection.invalidate()


# Create database engine
engine = create_engine(settings.DATABASE_URL, **_build_engine_kwargs(settings.DATABASE_URL))

# Create session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine, expire_on_commit=False)

# Create declarative base for models
Base = declarative_base()


def get_db():
    """Dependency to get database session."""
    db = SessionLocal()
    try:
        yield db
    except OperationalError:
        invalidate_db_session(db)
        logger.warning("Database operational error detected; invalidated the active session.", exc_info=True)
        raise
    except Exception:
        with suppress(Exception):
            db.rollback()
        raise
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
