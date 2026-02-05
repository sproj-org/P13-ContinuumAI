from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.controllers.auth import router as auth_router
from app.controllers.query import router as query_router
import os

app = FastAPI(title="ContinuumAI Backend")
app.include_router(query_router, prefix="/api")

FRONTEND_ORIGINS = os.environ.get("FRONTEND_ORIGINS", "http://localhost:3000")
origins = [origin.strip() for origin in FRONTEND_ORIGINS.split(",")]

# CORS Configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(auth_router)

@app.get("/health")
def health_check():
    return {"status": "ok"}
