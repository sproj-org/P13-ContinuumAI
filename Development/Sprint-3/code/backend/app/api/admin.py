"""Admin API endpoints for managing organizations and users."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List

from app.db.database import get_db
from app.db.models import User, Organization, OrganizationDataset
from app.schemas.user import (
    UserResponse,
    AdminUserCreate,
    OrganizationCreate,
    OrganizationUpdate,
    OrganizationResponse,
    OrganizationWithUsers,
    OrganizationDatasetCreate,
    OrganizationDatasetResponse,
    OrganizationDatasetBasic,
)
from app.core.security import get_password_hash, get_current_user

router = APIRouter(prefix="/admin", tags=["Admin"])


# ============================================
# Admin Authentication Dependency
# ============================================

async def get_current_admin(current_user: User = Depends(get_current_user)) -> User:
    """Verify that the current user is an admin."""
    if not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required"
        )
    return current_user


# ============================================
# Organization Management
# ============================================

@router.get("/organizations", response_model=List[OrganizationWithUsers])
async def list_organizations(
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin)
):
    """List all organizations with their users and datasets."""
    organizations = db.query(Organization).order_by(Organization.created_at.desc()).all()
    return [OrganizationWithUsers.model_validate(org) for org in organizations]


@router.post("/organizations", response_model=OrganizationResponse, status_code=status.HTTP_201_CREATED)
async def create_organization(
    org_data: OrganizationCreate,
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin)
):
    """Create a new organization."""
    # Check if slug already exists
    existing = db.query(Organization).filter(Organization.slug == org_data.slug).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Organization with this slug already exists"
        )
    
    # Check if name already exists
    existing_name = db.query(Organization).filter(Organization.name == org_data.name).first()
    if existing_name:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Organization with this name already exists"
        )
    
    organization = Organization(
        name=org_data.name,
        slug=org_data.slug,
        description=org_data.description
    )
    
    db.add(organization)
    db.commit()
    db.refresh(organization)
    
    return organization


@router.get("/organizations/{org_id}", response_model=OrganizationWithUsers)
async def get_organization(
    org_id: int,
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin)
):
    """Get organization details with users and datasets."""
    organization = db.query(Organization).filter(Organization.id == org_id).first()
    if not organization:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Organization not found"
        )
    return OrganizationWithUsers.model_validate(organization)


@router.put("/organizations/{org_id}", response_model=OrganizationResponse)
async def update_organization(
    org_id: int,
    org_data: OrganizationUpdate,
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin)
):
    """Update an organization."""
    organization = db.query(Organization).filter(Organization.id == org_id).first()
    if not organization:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Organization not found"
        )
    
    if org_data.name is not None:
        # Check if name is taken by another org
        existing = db.query(Organization).filter(
            Organization.name == org_data.name,
            Organization.id != org_id
        ).first()
        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Organization name already taken"
            )
        organization.name = org_data.name
    
    if org_data.slug is not None:
        # Check if slug is taken by another org
        existing = db.query(Organization).filter(
            Organization.slug == org_data.slug,
            Organization.id != org_id
        ).first()
        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Organization slug already taken"
            )
        organization.slug = org_data.slug
    
    if org_data.description is not None:
        organization.description = org_data.description
    
    if org_data.is_active is not None:
        organization.is_active = org_data.is_active
    
    db.commit()
    db.refresh(organization)
    
    return organization


@router.delete("/organizations/{org_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_organization(
    org_id: int,
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin)
):
    """Delete an organization (soft delete by deactivating)."""
    organization = db.query(Organization).filter(Organization.id == org_id).first()
    if not organization:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Organization not found"
        )
    
    # Soft delete - just deactivate
    organization.is_active = False
    db.commit()
    
    return None


# ============================================
# Organization Dataset Management
# ============================================

@router.get("/organizations/{org_id}/datasets", response_model=List[OrganizationDatasetResponse])
async def list_organization_datasets(
    org_id: int,
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin)
):
    """List datasets assigned to an organization."""
    organization = db.query(Organization).filter(Organization.id == org_id).first()
    if not organization:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Organization not found"
        )
    
    return organization.datasets


@router.post("/organizations/{org_id}/datasets", response_model=OrganizationDatasetResponse, status_code=status.HTTP_201_CREATED)
async def assign_dataset_to_organization(
    org_id: int,
    dataset_data: OrganizationDatasetCreate,
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin)
):
    """Assign a dataset to an organization."""
    organization = db.query(Organization).filter(Organization.id == org_id).first()
    if not organization:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Organization not found"
        )
    
    # Check if dataset already assigned
    existing = db.query(OrganizationDataset).filter(
        OrganizationDataset.organization_id == org_id,
        OrganizationDataset.dataset_id == dataset_data.dataset_name
    ).first()
    
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Dataset already assigned to this organization"
        )
    
    org_dataset = OrganizationDataset(
        organization_id=org_id,
        dataset_id=dataset_data.dataset_name,  # Store as dataset_id in DB
        display_name=dataset_data.display_name
    )
    
    db.add(org_dataset)
    db.commit()
    db.refresh(org_dataset)
    
    # Return with mapped field name
    return OrganizationDatasetResponse.from_orm_with_mapping(org_dataset)


@router.delete("/organizations/{org_id}/datasets/{dataset_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_dataset_from_organization(
    org_id: int,
    dataset_id: int,  # This is the OrganizationDataset.id, not the dataset_name
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin)
):
    """Remove a dataset from an organization by assignment ID."""
    org_dataset = db.query(OrganizationDataset).filter(
        OrganizationDataset.organization_id == org_id,
        OrganizationDataset.id == dataset_id
    ).first()
    
    if not org_dataset:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Dataset assignment not found"
        )
    
    db.delete(org_dataset)
    db.commit()
    
    return None


# ============================================
# User Management
# ============================================

@router.get("/users", response_model=List[UserResponse])
async def list_users(
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin)
):
    """List all users."""
    users = db.query(User).order_by(User.created_at.desc()).all()
    return users


@router.post("/users", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def create_user(
    user_data: AdminUserCreate,
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin)
):
    """Create a new user (admin only)."""
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
    
    # Check if organization exists
    organization = db.query(Organization).filter(Organization.id == user_data.organization_id).first()
    if not organization:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Organization not found"
        )
    
    # Create user
    hashed_password = get_password_hash(user_data.password)
    new_user = User(
        username=user_data.username,
        email=user_data.email,
        hashed_password=hashed_password,
        organization_id=user_data.organization_id,
        is_admin=user_data.is_admin
    )
    
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    
    return new_user


@router.get("/users/{user_id}", response_model=UserResponse)
async def get_user(
    user_id: int,
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin)
):
    """Get user details."""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    return user


@router.put("/users/{user_id}", response_model=UserResponse)
async def update_user(
    user_id: int,
    user_data: dict,
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin)
):
    """Update user details."""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    # Prevent admin from deactivating themselves
    if "is_active" in user_data and not user_data["is_active"] and user.id == admin.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot deactivate your own account"
        )
    
    # Update allowed fields
    if "is_active" in user_data:
        user.is_active = user_data["is_active"]
    if "is_admin" in user_data:
        user.is_admin = user_data["is_admin"]
    if "email" in user_data:
        user.email = user_data["email"]
    
    db.commit()
    db.refresh(user)
    
    return user


@router.delete("/users/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user(
    user_id: int,
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin)
):
    """Delete a user."""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    # Prevent admin from deleting themselves
    if user.id == admin.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot delete your own account"
        )
    
    db.delete(user)
    db.commit()
    
    return None


# ============================================
# Available Datasets (for dropdown in admin)
# ============================================

@router.get("/available-datasets")
async def list_available_datasets(
    admin: User = Depends(get_current_admin)
):
    """List all available dataset IDs that can be assigned to organizations."""
    # For now, return hardcoded list. Later this can query from a datasets table.
    return {
        "datasets": [
            {"id": "silkroute", "name": "Silkroute Sales", "description": "Sample sales database"}
        ]
    }
