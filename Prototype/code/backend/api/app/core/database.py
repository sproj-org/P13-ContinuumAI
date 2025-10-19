"""
Database configuration and connection setup for MySQL
"""

from sqlalchemy import create_engine, MetaData
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import QueuePool
import pymysql

from .config import settings  # Fixed import - added dot for relative import

# Install PyMySQL as MySQLdb
pymysql.install_as_MySQLdb()

# Create engine with connection pooling
engine = create_engine(
    settings.database_url,  # Use property from config, not direct DATABASE_URL
    poolclass=QueuePool,
    pool_size=10,
    max_overflow=20,
    pool_pre_ping=True,
    echo=True if settings.ENVIRONMENT == "development" else False  # Better debugging control
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Base class for models
Base = declarative_base()

# Metadata for table operations
metadata = MetaData()

def create_tables():
    """Create database tables"""
    Base.metadata.create_all(bind=engine)

def get_db():
    """Dependency to get database session"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def check_database_connection():
    """Check if database connection is working"""
    try:
        # Try to connect to the database
        with engine.connect() as connection:
            # Use text() wrapper for raw SQL with SQLAlchemy 2.0
            from sqlalchemy import text
            result = connection.execute(text("SELECT 1"))
            return True
    except Exception as e:
        print(f"Database connection failed: {e}")
        return False