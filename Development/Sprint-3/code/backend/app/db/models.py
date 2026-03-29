from sqlalchemy import Column, Integer, String, DateTime, Boolean, ForeignKey, Text
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.db.database import Base


class Organization(Base):
    """Organization model - companies onboarded to the platform."""
    
    __tablename__ = "organizations"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), unique=True, nullable=False)
    slug = Column(String(100), unique=True, index=True, nullable=False)  # URL-friendly identifier
    description = Column(Text, nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relationships
    users = relationship("User", back_populates="organization")
    datasets = relationship("OrganizationDataset", back_populates="organization")
    
    def __repr__(self):
        return f"<Organization(id={self.id}, name={self.name}, slug={self.slug})>"


class OrganizationDataset(Base):
    """Links organizations to datasets they have access to."""
    
    __tablename__ = "organization_datasets"
    
    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=False)
    dataset_id = Column(String(100), nullable=False)  # e.g., "silkroute"
    display_name = Column(String(255), nullable=True)  # Custom name for the org
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationships
    organization = relationship("Organization", back_populates="datasets")
    
    def __repr__(self):
        return f"<OrganizationDataset(org_id={self.organization_id}, dataset={self.dataset_id})>"


class User(Base):
    """User model for authentication."""
    
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True, index=True, nullable=False)
    email = Column(String(255), unique=True, index=True, nullable=False)
    hashed_password = Column(String(255), nullable=False)
    
    # Organization link
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=True)
    
    # Admin flag (for super admin access to admin panel)
    is_admin = Column(Boolean, default=False)
    is_active = Column(Boolean, default=True)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relationships
    organization = relationship("Organization", back_populates="users")
    
    def __repr__(self):
        return f"<User(id={self.id}, username={self.username}, email={self.email})>"
