from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from app.core.config import get_settings
from app.db.database import create_tables
from app.api.auth import router as auth_router
from app.api.profiling import router as profiling_router
from app.api.query import router as query_router
from app.api.health import router as health_router

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan - runs on startup and shutdown."""
    # Startup: Create database tables
    create_tables()
    yield
    # Shutdown: cleanup if needed


app = FastAPI(
    title="Backend API",
    description="FastAPI backend with JWT authentication",
    version="1.0.0",
    lifespan=lifespan,
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
app.include_router(profiling_router, prefix="/api")
app.include_router(query_router, prefix="/api")
app.include_router(health_router, prefix="/api")


@app.get("/")
def root_check():
    """Root endpoint."""
    return {"status": "Backend Running."}


@app.get("/api/health")
def api_health():
    """API health check endpoint."""
    return {"status": "ok", "message": "API is running"}
