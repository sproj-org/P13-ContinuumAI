from sqlalchemy import Column, Integer, String, DateTime, JSON, Text
from datetime import datetime
from ..core.database import Base  # Import shared Base instead of creating new one

class SalesDataset(Base):
    """
    Simple model to store entire CSV datasets as JSON.
    This allows us to work with any CSV structure without 
    predefined schema constraints.
    """
    __tablename__ = "sales_datasets"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)  # User-friendly name
    filename = Column(String(255), nullable=True)  # Original filename
    uploaded_at = Column(DateTime, default=datetime.utcnow)
    description = Column(Text, nullable=True)  # Optional description
    
    # Store the entire CSV data as JSON array
    # Format: [{"Order Date": "2024-01-01", "Revenue": 1000, "Region": "North"}, ...]
    raw_data = Column(JSON, nullable=False)
    
    # Metadata about the dataset
    total_records = Column(Integer, default=0)
    column_names = Column(JSON, nullable=True)  # Store column names for quick reference
    
    def __repr__(self):
        return f"<SalesDataset(name='{self.name}', records={self.total_records})>"