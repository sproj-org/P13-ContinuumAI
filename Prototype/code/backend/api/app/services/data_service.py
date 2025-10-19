import pandas as pd
import numpy as np
from datetime import datetime, date
from typing import List, Dict, Any
from sqlalchemy.orm import Session

from ..models.sales import SalesDataset
from ..core.database import SessionLocal

class DataService:
    """
    Service layer for handling CSV data storage and retrieval.
    Converts between CSV → DataFrame → JSON → Database and back.
    """
    
    def __init__(self, db: Session):
        self.db = db
    
    def import_csv_to_db(self, df: pd.DataFrame, filename: str, dataset_name: str = None) -> int:
        """
        Convert DataFrame to JSON and store in database.
        
        Args:
            df: Preprocessed DataFrame from your data_logic.py
            filename: Original CSV filename
            dataset_name: Optional custom name for the dataset
            
        Returns:
            dataset_id: ID of created dataset record
        """
        # Convert DataFrame to JSON-serializable format
        records_json = self._dataframe_to_json(df)
        
        # Create dataset record
        dataset = SalesDataset(
            name=dataset_name or filename,
            filename=filename,
            uploaded_at=datetime.utcnow(),
            raw_data=records_json,
            total_records=len(df),
            column_names=list(df.columns)
        )
        
        self.db.add(dataset)
        self.db.commit()
        self.db.refresh(dataset)
        
        return dataset.id
    
    def get_dataframe_from_db(self, dataset_id: int) -> pd.DataFrame:
        """
        Retrieve JSON data and convert back to DataFrame.
        
        Args:
            dataset_id: ID of the dataset to retrieve
            
        Returns:
            DataFrame ready for your existing data_logic.py functions
        """
        dataset = self.db.query(SalesDataset).filter(SalesDataset.id == dataset_id).first()
        
        if not dataset:
            raise ValueError(f"Dataset {dataset_id} not found")
        
        # Convert JSON back to DataFrame
        df = self._json_to_dataframe(dataset.raw_data)
        
        return df
    
    def list_datasets(self) -> List[Dict[str, Any]]:
        """Get all available datasets with metadata"""
        datasets = self.db.query(SalesDataset).all()
        
        return [
            {
                "id": dataset.id,
                "name": dataset.name,
                "filename": dataset.filename,
                "uploaded_at": dataset.uploaded_at,
                "total_records": dataset.total_records,
                "columns": dataset.column_names
            }
            for dataset in datasets
        ]
    
    def delete_dataset(self, dataset_id: int) -> bool:
        """Delete a dataset"""
        dataset = self.db.query(SalesDataset).filter(SalesDataset.id == dataset_id).first()
        if dataset:
            self.db.delete(dataset)
            self.db.commit()
            return True
        return False
    
    def _dataframe_to_json(self, df: pd.DataFrame) -> List[Dict[str, Any]]:
        """Convert DataFrame to JSON with proper type handling"""
        
        records_json = df.to_dict('records')
        
        # Handle pandas/numpy types for JSON serialization
        for record in records_json:
            for key, value in record.items():
                if pd.isna(value):
                    record[key] = None
                elif isinstance(value, (pd.Timestamp, datetime, date)):
                    record[key] = value.isoformat()
                elif isinstance(value, np.integer):
                    record[key] = int(value)
                elif isinstance(value, np.floating):
                    record[key] = float(value) if not np.isnan(value) else None
                elif isinstance(value, np.bool_):
                    record[key] = bool(value)
                elif hasattr(value, 'isoformat'):  # Catch any other date-like objects
                    record[key] = value.isoformat()
        
        return records_json
    
    def _json_to_dataframe(self, json_data: List[Dict[str, Any]]) -> pd.DataFrame:
        """Convert JSON back to DataFrame with proper type restoration"""
        df = pd.DataFrame(json_data)
        
        # Restore date columns (your data_logic.py expects these)
        date_columns = [col for col in df.columns if 'date' in col.lower()]
        for col in date_columns:
            df[col] = pd.to_datetime(df[col], errors='coerce')
        
        return df