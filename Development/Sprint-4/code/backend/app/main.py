from contextlib import asynccontextmanager
import hashlib
import logging
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import get_settings
from app.db.database import create_tables
from app.api.auth import router as auth_router
from app.api.admin import router as admin_router
from app.api.datasets import router as datasets_router
from app.api.debug import router as debug_router
from app.api.profiling import router as profiling_router
from app.api.decision import router as decision_router
from app.api.strategy import bundle_router as strategy_bundle_router
from app.api.kpi_registry import router as kpi_registry_router

# Load backend/.env without overriding terminal environment variables.
load_dotenv(Path(__file__).resolve().parents[1] / ".env", override=False)

settings = get_settings()
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan - runs on startup and shutdown."""
    # Startup: Create database tables
    create_tables()
    key = (settings.OPENAI_API_KEY or "").strip()
    fingerprint = hashlib.sha256(key.encode("utf-8")).hexdigest()[:8] if key else "none"
    logger.info(
        "Settings loaded: OPENAI_API_KEY set=%s fingerprint=%s model=%s",
        bool(key),
        fingerprint,
        settings.OPENAI_MODEL,
    )
    yield
    # Shutdown: cleanup if needed


app = FastAPI(
    title="Backend API",
    description="FastAPI backend with JWT authentication",
    version="1.0.0",
    lifespan=lifespan
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.FRONTEND_URL],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(auth_router, prefix="/api")
app.include_router(admin_router, prefix="/api")
app.include_router(profiling_router, prefix="/api")
app.include_router(datasets_router, prefix="/api")
app.include_router(debug_router, prefix="/api")
app.include_router(decision_router, prefix="/api")
app.include_router(strategy_bundle_router, prefix="/api")
app.include_router(kpi_registry_router, prefix="/api")


@app.get("/")
def health_check():
    """Health check endpoint."""
    return {"status": "Backend Running."}


@app.get("/api/health")
def api_health():
    """API health check endpoint."""
    return {"status": "ok", "message": "API is running"}
