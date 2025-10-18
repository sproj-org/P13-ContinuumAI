"""
ContinuumAI Sales Dashboard Backend API
FastAPI application with PostgreSQL and OAuth authentication

IMPORTANT: This backend runs independently and does NOT affect 
the existing Streamlit functionality during development.
"""

from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import uvicorn
import os
from contextlib import asynccontextmanager

# Add the app directory to Python path for imports
import sys
app_dir = os.path.join(os.path.dirname(__file__), 'app')
if app_dir not in sys.path:
    sys.path.insert(0, app_dir)

# Import configuration
from core.config import settings


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan management"""
    print("🚀 ContinuumAI API Server starting...")
    print(f"📊 Streamlit Frontend: http://localhost:8501")
    print(f"🔧 FastAPI Backend: http://localhost:{settings.API_PORT}")
    print(f"📚 API Documentation: http://localhost:{settings.API_PORT}/docs")
    yield
    print("🛑 ContinuumAI API Server shutting down...")


# Create FastAPI application
app = FastAPI(
    title="ContinuumAI Sales Dashboard API",
    description="Backend API for sales analytics dashboard with user management",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan
)

# Configure CORS for Streamlit integration
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)


# Root endpoint
@app.get("/")
async def root():
    """API root endpoint"""
    return {
        "service": "ContinuumAI Sales Dashboard API",
        "version": "1.0.0",
        "status": "running",
        "docs": "/docs",
        "frontend": "http://localhost:8501"
    }


# Health check endpoint
@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "service": "continuumai-api",
        "message": "Backend is running independently alongside Streamlit"
    }


# Development server startup
if __name__ == "__main__":
    print("🔥 Starting ContinuumAI FastAPI Development Server...")
    print("📝 Note: Existing Streamlit app continues to work normally")
    
    uvicorn.run(
        "main:app",
        host=settings.API_HOST,
        port=settings.API_PORT,
        reload=True,
        log_level="info"
    )