from pydantic import BaseModel, EmailStr, field_validator
from datetime import datetime
from typing import Optional


class UserCreate(BaseModel):
    """Schema for user registration (admin only)."""
    username: str
    email: EmailStr
    password: str
    confirm_password: str
    organization_id: Optional[int] = None
    is_admin: bool = False

    @field_validator("username")
    @classmethod
    def username_valid(cls, v: str) -> str:
        if len(v) < 3:
            raise ValueError("Username must be at least 3 characters long")
        if len(v) > 50:
            raise ValueError("Username must be at most 50 characters long")
        if not v.isalnum():
            raise ValueError("Username must contain only alphanumeric characters")
        return v.lower()

    @field_validator("password")
    @classmethod
    def password_valid(cls, v: str) -> str:
        if len(v) < 6:
            raise ValueError("Password must be at least 6 characters long")
        return v

    @field_validator("confirm_password")
    @classmethod
    def passwords_match(cls, v: str, info) -> str:
        if "password" in info.data and v != info.data["password"]:
            raise ValueError("Passwords do not match")
        return v


class UserLogin(BaseModel):
    """Schema for user login."""
    username: str
    password: str


class OrganizationBasic(BaseModel):
    """Basic organization info for embedding in responses."""
    id: int
    name: str
    slug: str

    class Config:
        from_attributes = True


class UserResponse(BaseModel):
    """Schema for user response (public data only)."""
    id: int
    username: str
    email: str
    is_admin: bool = False
    is_active: bool = True
    organization: Optional[OrganizationBasic] = None
    organization_id: Optional[int] = None
    created_at: datetime

    class Config:
        from_attributes = True


class Token(BaseModel):
    """Schema for JWT token response."""
    access_token: str
    token_type: str = "bearer"
    user: UserResponse


class TokenData(BaseModel):
    """Schema for token payload data."""
    user_id: Optional[int] = None


# ============================================
# Organization Schemas
# ============================================

class OrganizationCreate(BaseModel):
    """Schema for creating an organization."""
    name: str
    slug: str
    description: Optional[str] = None

    @field_validator("slug")
    @classmethod
    def slug_valid(cls, v: str) -> str:
        if len(v) < 2:
            raise ValueError("Slug must be at least 2 characters long")
        if len(v) > 100:
            raise ValueError("Slug must be at most 100 characters long")
        if not v.replace("-", "").replace("_", "").isalnum():
            raise ValueError("Slug must contain only alphanumeric characters, hyphens, and underscores")
        return v.lower()


class OrganizationUpdate(BaseModel):
    """Schema for updating an organization."""
    name: Optional[str] = None
    slug: Optional[str] = None
    description: Optional[str] = None
    is_active: Optional[bool] = None


class OrganizationResponse(BaseModel):
    """Schema for organization response."""
    id: int
    name: str
    slug: str
    description: Optional[str] = None
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True


class OrganizationDatasetBasic(BaseModel):
    """Basic dataset info for embedding in organization responses."""
    id: int
    dataset_name: str

    class Config:
        from_attributes = True


class OrganizationWithUsers(OrganizationResponse):
    """Organization with its users and datasets."""
    users: list[UserResponse] = []
    datasets: list[OrganizationDatasetBasic] = []

    class Config:
        from_attributes = True

    @classmethod
    def model_validate(cls, obj, **kwargs):
        """Custom validation to map dataset_id to dataset_name."""
        # Convert datasets from ORM objects
        datasets_mapped = []
        if hasattr(obj, 'datasets') and obj.datasets:
            for d in obj.datasets:
                datasets_mapped.append(OrganizationDatasetBasic(
                    id=d.id,
                    dataset_name=d.dataset_id  # Map dataset_id -> dataset_name
                ))

        return cls(
            id=obj.id,
            name=obj.name,
            slug=obj.slug,
            description=obj.description,
            is_active=obj.is_active,
            created_at=obj.created_at,
            users=obj.users or [],
            datasets=datasets_mapped
        )


# ============================================
# Organization Dataset Schemas
# ============================================

class OrganizationDatasetCreate(BaseModel):
    """Schema for assigning a dataset to an organization."""
    dataset_name: str  # The dataset identifier (e.g., "silkroute", "gold_customer_360")
    display_name: Optional[str] = None


class OrganizationDatasetResponse(BaseModel):
    """Schema for organization dataset response."""
    id: int
    organization_id: int
    dataset_name: str  # Maps to dataset_id column in DB
    display_name: Optional[str] = None
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True

    @classmethod
    def from_orm_with_mapping(cls, obj):
        """Map dataset_id to dataset_name from ORM object."""
        return cls(
            id=obj.id,
            organization_id=obj.organization_id,
            dataset_name=obj.dataset_id,  # Map dataset_id -> dataset_name
            display_name=obj.display_name,
            is_active=obj.is_active,
            created_at=obj.created_at
        )


# ============================================
# Admin User Creation Schema
# ============================================

class AdminUserCreate(BaseModel):
    """Schema for admin creating a user."""
    username: str
    email: EmailStr
    password: str
    organization_id: int
    is_admin: bool = False

    @field_validator("username")
    @classmethod
    def username_valid(cls, v: str) -> str:
        if len(v) < 3:
            raise ValueError("Username must be at least 3 characters long")
        if len(v) > 50:
            raise ValueError("Username must be at most 50 characters long")
        if not v.isalnum():
            raise ValueError("Username must contain only alphanumeric characters")
        return v.lower()

    @field_validator("password")
    @classmethod
    def password_valid(cls, v: str) -> str:
        if len(v) < 6:
            raise ValueError("Password must be at least 6 characters long")
        return v
