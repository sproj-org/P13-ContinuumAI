from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from datetime import timedelta

from app.db.database import get_db
from app.db.models import User
<<<<<<< HEAD
from app.schemas.user import UserLogin, UserResponse, Token
from app.core.security import (
=======
from app.schemas.user import UserCreate, UserLogin, UserResponse, Token
from app.core.security import (
    get_password_hash,
>>>>>>> 7599888825e1aa7a1658e7d3beb0d95f793251d2
    verify_password,
    create_access_token,
    get_current_user,
)
from app.core.config import get_settings

settings = get_settings()
router = APIRouter(prefix="/auth", tags=["Authentication"])


<<<<<<< HEAD
# NOTE: Public signup has been removed.
# Users are now created by admins through the admin panel.
=======
@router.post("/signup", response_model=Token, status_code=status.HTTP_201_CREATED)
async def signup(user_data: UserCreate, db: Session = Depends(get_db)):
    """Register a new user."""
    
    # Check if email already exists
    existing_email = db.query(User).filter(User.email == user_data.email).first()
    if existing_email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered"
        )
    
    # Check if username already exists
    existing_username = db.query(User).filter(User.username == user_data.username).first()
    if existing_username:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username already taken"
        )
    
    # Create new user
    hashed_password = get_password_hash(user_data.password)
    new_user = User(
        username=user_data.username,
        email=user_data.email,
        hashed_password=hashed_password
    )
    
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    
    # Create access token
    access_token = create_access_token(
        data={"sub": str(new_user.id)},
        expires_delta=timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    
    return Token(
        access_token=access_token,
        token_type="bearer",
        user=UserResponse.model_validate(new_user)
    )
>>>>>>> 7599888825e1aa7a1658e7d3beb0d95f793251d2


@router.post("/login", response_model=Token)
async def login(user_data: UserLogin, db: Session = Depends(get_db)):
    """Authenticate a user and return a token."""
    
    # Find user by username
    user = db.query(User).filter(User.username == user_data.username.lower()).first()
    
    if not user or not verify_password(user_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
<<<<<<< HEAD
    # Check if user is active
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Your account has been deactivated. Please contact your administrator.",
        )
    
    # Check if user's organization is active (if they belong to one)
    if user.organization and not user.organization.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Your organization's access has been suspended. Please contact ContinuumAI support.",
        )
    
=======
>>>>>>> 7599888825e1aa7a1658e7d3beb0d95f793251d2
    # Create access token
    access_token = create_access_token(
        data={"sub": str(user.id)},
        expires_delta=timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    
    return Token(
        access_token=access_token,
        token_type="bearer",
        user=UserResponse.model_validate(user)
    )


@router.get("/me", response_model=UserResponse)
async def get_me(current_user: User = Depends(get_current_user)):
    """Get the current authenticated user."""
    return UserResponse.model_validate(current_user)


@router.post("/verify")
async def verify_token_endpoint(current_user: User = Depends(get_current_user)):
    """Verify if the current token is valid."""
    return {"valid": True, "user_id": current_user.id}
