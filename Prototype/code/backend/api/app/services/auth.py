# backend/api/app/services/auth.py
from datetime import datetime, timedelta, timezone
from typing import Tuple, Optional
from jose import jwt, JWTError
from passlib.context import CryptContext
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.user import User  # <-- FIXED: use your User model

pwd = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")


# ---- password helpers ----
def hash_password(p: str) -> str:
    return pwd.hash(p)

def verify_password(p: str, h: str) -> bool:
    return pwd.verify(p, h)

def normalize_email(email: str) -> str:
    return (email or "").strip().lower()


# ---- JWT helpers ----
def _exp_m(minutes: int) -> datetime:
    return datetime.now(tz=timezone.utc) + timedelta(minutes=minutes)

def _exp_d(days: int) -> datetime:
    return datetime.now(tz=timezone.utc) + timedelta(days=days)

def create_tokens(sub: str, role: str = "user", tenant_id: str = "default") -> Tuple[str, str]:
    base = {
        "sub": sub,
        "role": role,
        "tenant_id": tenant_id,
        "iss": settings.JWT_ISS if hasattr(settings, "JWT_ISS") else "continuum.backend",
        "aud": settings.JWT_AUD if hasattr(settings, "JWT_AUD") else "continuum.frontend",
        "iat": int(datetime.now(tz=timezone.utc).timestamp()),
    }
    access = jwt.encode(
        {**base, "type": "access", "exp": _exp_m(getattr(settings, "ACCESS_TOKEN_EXPIRE_MIN", 30))},
        settings.SECRET_KEY,
        algorithm=settings.ALGORITHM,
    )
    refresh = jwt.encode(
        {**base, "type": "refresh", "exp": _exp_d(getattr(settings, "REFRESH_TOKEN_EXPIRE_DAYS", 14))},
        settings.SECRET_KEY,
        algorithm=settings.ALGORITHM,
    )
    return access, refresh

def decode_token(token: str, expected_type: str = "access") -> dict:
    try:
        payload = jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=[settings.ALGORITHM],
            audience=(settings.JWT_AUD if hasattr(settings, "JWT_AUD") else "continuum.frontend"),
            issuer=(settings.JWT_ISS if hasattr(settings, "JWT_ISS") else "continuum.backend"),
        )
        if payload.get("type") != expected_type:
            raise JWTError("wrong token type")
        return payload
    except JWTError as e:
        raise ValueError(str(e))


# ---- DB helpers ----
def get_user_by_email(db: Session, email: str) -> Optional[User]:
    return db.query(User).filter(User.email == email).first()

def ensure_seed_user(db: Session):
    """Create a demo admin user if the table is empty."""
    if db.query(User).count() == 0:
        u = User(
            email="demo@continuum.ai",
            hashed_password=hash_password("demo123"),
            is_active=True,
            role="admin",
            tenant_id="default",
        )
        db.add(u)
        db.commit()
