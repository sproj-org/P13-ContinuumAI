from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

from app.core.database import create_tables, check_database_connection
from app.routes import data, auth

from app.core.database import Base, engine
from app.routes import auth, data
from app.core.config import settings
from app.routes import data, auth  # <-- now auth imports won't crash
from app.models.user import User   # ensure model is registered before create_all



# Create FastAPI app
app = FastAPI(
    title="ContinuumAI Sales Analytics API",
    description="API for sales data analytics and dashboard backend",
    version="1.0.0"
)

# Add CORS middleware for frontend integration
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:8501",
        "http://localhost:3000",
        "https://*.vercel.app",  # Vercel preview deployments
        "https://continuum-cxx5dcm73-mustufas-projects-837a1f16.vercel.app",  # Your Vercel deployment
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(data.router)
app.include_router(auth.router)

Base.metadata.create_all(bind=engine)

@app.on_event("startup")
async def startup_event():
    """Initialize database on startup"""
    print("Starting ContinuumAI API...")
    
    # Check database connection
    if check_database_connection():
        print("✅ Database connection successful")
        create_tables()
        print("✅ Database tables ready")
    else:
        print("❌ Database connection failed - check your configuration")

@app.get("/")
async def root():
    return {
        "message": "ContinuumAI Sales Analytics API",
        "version": "1.0.0",
        "docs": "/docs"
    }

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    db_status = check_database_connection()
    return {
        "status": "healthy" if db_status else "unhealthy",
        "database": "connected" if db_status else "disconnected"
    }

if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True
    )