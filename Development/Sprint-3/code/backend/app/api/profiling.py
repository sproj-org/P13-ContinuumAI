"""
Profiling API endpoints.
Serves pre-generated profile JSON files from the out/ directory.
"""

import json
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, HTTPException

router = APIRouter(prefix="/profiling", tags=["profiling"])

# Path to the out directory containing profile JSONs
OUT_DIR = Path(__file__).parent.parent.parent / "out"

# Available tables and their profile file names
AVAILABLE_TABLES = {
    "mart_sales": "mart_sales_profile.json",
    "mart_customers": "mart_customers_profile.json",
    "mart_stores": "mart_stores_profile.json",
}


def load_profile(table_name: str) -> dict:
    """Load a profile JSON file for the given table."""
    if table_name not in AVAILABLE_TABLES:
        raise HTTPException(status_code=404, detail=f"Table '{table_name}' not found")
    
    file_path = OUT_DIR / AVAILABLE_TABLES[table_name]
    
    if not file_path.exists():
        raise HTTPException(
            status_code=404, 
            detail=f"Profile file for '{table_name}' not found"
        )
    
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except json.JSONDecodeError as e:
        raise HTTPException(
            status_code=500, 
            detail=f"Error parsing profile for '{table_name}': {str(e)}"
        )


@router.get("/aggregations")
def list_aggregations():
    """List all available aggregation tables with summary info."""
    aggregations = []
    
    for table_name in AVAILABLE_TABLES:
        try:
            profile = load_profile(table_name)
            aggregations.append({
                "table_name": profile.get("table_name") or profile.get("dataset_name"),
                "schema_name": profile.get("schema_name", "aggregations"),
                "row_count": profile.get("row_count", 0),
                "column_count": profile.get("column_count", 0),
                "profiled_at": profile.get("profiled_at", ""),
            })
        except HTTPException:
            # Skip tables that can't be loaded
            continue
    
    return {"aggregations": aggregations}


@router.get("/aggregations/{table_name}/profile")
def get_table_profile(table_name: str):
    """Get the full profile for a specific table."""
    return load_profile(table_name)


@router.get("/aggregations/{table_name}/columns/{column_name}")
def get_column_profile(table_name: str, column_name: str):
    """Get the profile for a specific column in a table."""
    profile = load_profile(table_name)
    
    columns = profile.get("columns", [])
    for col in columns:
        if col.get("name") == column_name:
            return col
    
    raise HTTPException(
        status_code=404, 
        detail=f"Column '{column_name}' not found in table '{table_name}'"
    )
