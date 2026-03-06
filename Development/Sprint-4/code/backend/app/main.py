from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from app.core.config import get_settings
from app.db.database import create_tables
from app.api.auth import router as auth_router
from app.api.admin import router as admin_router
from app.api.datasets import router as datasets_router
from app.api.profiling import router as profiling_router
from app.api.dashboards import router as dashboards_router
from app.api.chat_threads import router as chat_threads_router

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
app.include_router(dashboards_router, prefix="/api")
app.include_router(chat_threads_router, prefix="/api")


@app.get("/")
def health_check():
    """Health check endpoint."""
    return {"status": "Backend Running."}


@app.get("/api/health")
def api_health():
    """API health check endpoint."""
    return {"status": "ok", "message": "API is running"}
