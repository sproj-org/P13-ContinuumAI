from contextlib import asynccontextmanager
import logging
<<<<<<< HEAD
from pathlib import Path

from dotenv import load_dotenv
=======

>>>>>>> 7599888825e1aa7a1658e7d3beb0d95f793251d2
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import get_settings
from app.db.database import create_tables
from app.api.auth import router as auth_router
<<<<<<< HEAD
from app.api.admin import router as admin_router
=======
>>>>>>> 7599888825e1aa7a1658e7d3beb0d95f793251d2
from app.api.datasets import router as datasets_router
from app.api.debug import router as debug_router
from app.api.profiling import router as profiling_router

<<<<<<< HEAD
# Load backend/.env without overriding terminal environment variables.
load_dotenv(Path(__file__).resolve().parents[1] / ".env", override=False)

=======
>>>>>>> 7599888825e1aa7a1658e7d3beb0d95f793251d2
settings = get_settings()
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan - runs on startup and shutdown."""
    # Startup: Create database tables
    create_tables()
<<<<<<< HEAD
    logger.info("Loaded settings: OPENAI_API_KEY set: %s", bool((settings.OPENAI_API_KEY or "").strip()))
=======
    logger.info("Loaded settings: OPENAI_API_KEY set: %s", bool(settings.OPENAI_API_KEY))
>>>>>>> 7599888825e1aa7a1658e7d3beb0d95f793251d2
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
<<<<<<< HEAD
app.include_router(admin_router, prefix="/api")
=======
>>>>>>> 7599888825e1aa7a1658e7d3beb0d95f793251d2
app.include_router(profiling_router, prefix="/api")
app.include_router(datasets_router, prefix="/api")
app.include_router(debug_router, prefix="/api")


@app.get("/")
def health_check():
    """Health check endpoint."""
    return {"status": "Backend Running."}


@app.get("/api/health")
def api_health():
    """API health check endpoint."""
    return {"status": "ok", "message": "API is running"}
