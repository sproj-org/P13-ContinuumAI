# backend/api/app/routes/auth.py
from fastapi import APIRouter, Depends, HTTPException, Response, status, Request
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy.orm import Session

from sqlalchemy.exc import IntegrityError
from app.services.auth import hash_password, create_tokens, get_user_by_email


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

class SignupRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8)
    role: str = "user"
    tenant_id: str = "default"


@router.on_event("startup")
def _seed_user_on_startup():
    # seed a demo user so you can log in immediately
    from app.core.database import SessionLocal
    with SessionLocal() as db:
        ensure_seed_user(db)


@router.post("/login")
def login(body: LoginRequest, response: Response, db: Session = Depends(get_db)):
    from app.services.auth import normalize_email, verify_password, create_tokens, get_user_by_email
    email = normalize_email(body.email)

    user = get_user_by_email(db, email)
    if not user or not user.is_active:
        raise HTTPException(status_code=401, detail="Invalid credentials")

    if not verify_password(body.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Invalid credentials")

    access, refresh = create_tokens(user.email, role=user.role or "user", tenant_id=user.tenant_id or "default")
    response.set_cookie(key="refresh", value=refresh, httponly=True, samesite="lax", secure=False, path="/")
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

@router.post("/logout")
def logout(response: Response):
    # delete HttpOnly refresh cookie
    response.delete_cookie(key="refresh", path="/")
    return {"ok": True}

@router.post("/signup")
def signup(body: SignupRequest, response: Response, db: Session = Depends(get_db)):

    from app.services.auth import normalize_email
    email = normalize_email(body.email)

    
    # Reject if already exists
    if get_user_by_email(db, body.email):
        raise HTTPException(status_code=409, detail="User already exists")

    # Create user
    u = User(
        email=email,
        hashed_password=hash_password(body.password),
        is_active=True,
        role=body.role,
        tenant_id=body.tenant_id,
    )
    try:
        db.add(u)
        db.commit()
        db.refresh(u)
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="User already exists")

    # Issue tokens just like /auth/login
    access, refresh = create_tokens(u.email, role=u.role or "user", tenant_id=u.tenant_id or "default")

    # Set HttpOnly refresh cookie (Secure=True once HTTPS)
    response.set_cookie(
        key="refresh",
        value=refresh,
        httponly=True,
        samesite="lax",
        secure=False,
        path="/",
    )
    return {"access_token": access}
