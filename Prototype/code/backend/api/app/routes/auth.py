# backend/api/app/routes/auth.py
from fastapi import APIRouter, Depends, HTTPException, Response, status, Request
from pydantic import BaseModel, EmailStr
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.services.auth import (
    create_tokens,
    decode_token,
    get_user_by_email,
    verify_password,
    ensure_seed_user,
)
from app.models.user import User  # for type hints

router = APIRouter(prefix="/auth", tags=["auth"])


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


@router.on_event("startup")
def _seed_user_on_startup():
    # seed a demo user so you can log in immediately
    from app.core.database import SessionLocal
    with SessionLocal() as db:
        ensure_seed_user(db)


@router.post("/login")
def login(body: LoginRequest, response: Response, db: Session = Depends(get_db)):
    user = get_user_by_email(db, body.email)
    if not user or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

    # If you already store hashed passwords, uncomment this:
    # if not verify_password(body.password, user.hashed_password):
    #     raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

    # For the seeded demo user, accept demo credentials only:
    if body.email != "demo@continuum.ai" or body.password != "demo123":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

    access, refresh = create_tokens(user.email, role=user.role or "user", tenant_id=user.tenant_id or "default")

    # Set HttpOnly refresh cookie (adjust Secure=True when using HTTPS)
    response.set_cookie(
        key="refresh",
        value=refresh,
        httponly=True,
        samesite="lax",
        secure=False,  # switch to True behind TLS
        path="/",
    )
    # Return access in body; frontend stores it in a non-HttpOnly cookie for middleware checks
    return {"access_token": access}


@router.post("/refresh")
def refresh_token(request: Request, response: Response, db: Session = Depends(get_db)):
    cookie_refresh = request.cookies.get("refresh")
    if not cookie_refresh:
        raise HTTPException(status_code=401, detail="Missing refresh cookie")

    # Validate and extract subject
    try:
        payload = decode_token(cookie_refresh, expected_type="refresh")
    except ValueError:
        raise HTTPException(status_code=401, detail="Invalid refresh token")

    user = get_user_by_email(db, payload["sub"])
    if not user or not user.is_active:
        raise HTTPException(status_code=401, detail="User not found or inactive")

    access, new_refresh = create_tokens(user.email, role=user.role or "user", tenant_id=user.tenant_id or "default")

    # Rotate refresh cookie
    response.set_cookie(
        key="refresh",
        value=new_refresh,
        httponly=True,
        samesite="lax",
        secure=False,  # switch to True behind TLS
        path="/",
    )
    return {"access_token": access}
