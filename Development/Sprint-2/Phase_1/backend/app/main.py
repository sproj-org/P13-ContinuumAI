from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.routes import auth, query
from app.core.config import get_settings

settings = get_settings()

app = FastAPI(title="Continuum Vizro Backend")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.FRONTEND_ORIGIN, "http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(query.router)


@app.get("/health")
def health():
    return {"status": "ok"}
