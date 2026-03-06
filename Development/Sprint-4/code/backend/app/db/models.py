from sqlalchemy import Column, Integer, String, DateTime, Boolean, ForeignKey, Text
from sqlalchemy.dialects.postgresql import JSON
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
    saved_charts = relationship("SavedChart", back_populates="user", cascade="all, delete-orphan")
    chat_threads = relationship("ChatThread", back_populates="user", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<User(id={self.id}, username={self.username}, email={self.email})>"


class SavedChart(Base):
    """Persisted chart saved by a user to their dashboard."""

    __tablename__ = "saved_charts"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    dataset_id = Column(String(100), nullable=False, index=True)
    mart_id = Column(String(100), nullable=False)
    title = Column(String(500), nullable=False)
    chart_spec = Column(JSON, nullable=False)
    rows_snapshot = Column(JSON, nullable=False)
    position = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    user = relationship("User", back_populates="saved_charts")

    def __repr__(self):
        return f"<SavedChart(id={self.id}, user_id={self.user_id}, title={self.title})>"


class ChatThread(Base):
    """Persisted chat thread per user per dataset:mart key."""

    __tablename__ = "chat_threads"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    thread_key = Column(String(255), nullable=False, index=True)  # e.g. "silkroute:gold_sales_daily"
    turns = Column(JSON, nullable=False, default=list)             # ChatTurn[]
    chat_state = Column(JSON, nullable=True)                       # ChatThreadState
    last_chart_spec = Column(JSON, nullable=True)                  # ChartSpecV1 | null
    saved_prompts = Column(JSON, nullable=False, default=list)     # string[]
    chat_mode = Column(String(20), nullable=False, default="auto") # 'auto' | 'chart' | 'explain'
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # Relationships
    user = relationship("User", back_populates="chat_threads")

    def __repr__(self):
        return f"<ChatThread(id={self.id}, user_id={self.user_id}, key={self.thread_key})>"
