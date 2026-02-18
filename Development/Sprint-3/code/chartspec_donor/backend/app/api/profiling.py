"""
Profiling API endpoints.
Serves pre-generated profile JSON files from the out/ directory.
Also provides chart data querying from the database.
"""

import json
import re
from pathlib import Path
from typing import Optional, Literal, List
from decimal import Decimal
from datetime import date, datetime

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, field_validator
from sqlalchemy.orm import Session
from sqlalchemy import text

from app.db.database import get_db

router = APIRouter(prefix="/profiling", tags=["profiling"])

# Path to the out directory containing profile JSONs
OUT_DIR = Path(__file__).parent.parent.parent / "out"

# Available tables and their profile file names
AVAILABLE_TABLES = {
    "mart_sales": "mart_sales_profile.json",
    "mart_customers": "mart_customers_profile.json",
    "mart_stores": "mart_stores_profile.json",
}

# Schema name for mart tables
MARTS_SCHEMA = "marts"

# Allowed aggregation functions (whitelist for security)
ALLOWED_AGGREGATIONS = {"sum", "avg", "count", "min", "max"}


# ============================================
# Chart Data Models
# ============================================

class ChartDataRequest(BaseModel):
    """Request body for chart data query."""
    table_name: str
    x_axis: str
    y_axis: str
    aggregation_fn: Literal["sum", "avg", "count", "min", "max"] = "sum"
    limit: int = 20
    
    @field_validator("table_name")
    @classmethod
    def validate_table_name(cls, v: str) -> str:
        if v not in AVAILABLE_TABLES:
            raise ValueError(f"Invalid table name: {v}")
        return v
    
    @field_validator("x_axis", "y_axis")
    @classmethod
    def validate_column_name(cls, v: str) -> str:
        # Only allow alphanumeric and underscore (prevent SQL injection)
        if not re.match(r'^[a-zA-Z_][a-zA-Z0-9_]*$', v):
            raise ValueError(f"Invalid column name: {v}")
        return v


class ChartDataPoint(BaseModel):
    """Single data point for chart."""
    x: str
    y: float


class ChartDataResponse(BaseModel):
    """Response for chart data query."""
    x: List[str]
    y: List[float]
    title: str
    x_axis_label: str
    y_axis_label: str


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


# ============================================
# Chart Data Endpoints
# ============================================

def validate_column_exists(table_name: str, column_name: str) -> bool:
    """Validate that a column exists in the table profile."""
    try:
        profile = load_profile(table_name)
        columns = profile.get("columns", [])
        return any(col.get("name") == column_name for col in columns)
    except HTTPException:
        return False


def get_column_profile_info(table_name: str, column_name: str) -> Optional[dict]:
    """Get column profile information including role and type."""
    try:
        profile = load_profile(table_name)
        columns = profile.get("columns", [])
        for col in columns:
            if col.get("name") == column_name:
                return col
        return None
    except HTTPException:
        return None


def validate_aggregation_compatibility(
    column_profile: dict,
    aggregation_fn: str
) -> tuple[bool, str]:
    """
    Validate that the aggregation function is compatible with the column type.
    Returns (is_valid, error_message)
    """
    # Get role from effective_role (what the profiler determined)
    role = column_profile.get("effective_role", column_profile.get("base_role", "dimension"))
    physical_type = column_profile.get("physical_type", "string")
    column_name = column_profile.get("name", "unknown")
    
    # COUNT works on any column
    if aggregation_fn == "count":
        return True, ""
    
    # SUM and AVG require numeric columns (measures)
    if aggregation_fn in ["sum", "avg"]:
        # Check if it's a measure role
        if role != "measure":
            return False, (
                f"Cannot apply {aggregation_fn.upper()} to '{column_name}' - "
                f"it's a {role}, not a measure. Try using COUNT instead, "
                f"or select a numeric column like revenue, quantity, or amount."
            )
        
        # Also verify the physical type is numeric
        numeric_types = ["int", "float", "decimal", "numeric", "double", "real", "bigint", "smallint"]
        if not any(nt in physical_type.lower() for nt in numeric_types):
            return False, (
                f"Cannot apply {aggregation_fn.upper()} to '{column_name}' - "
                f"column type '{physical_type}' is not numeric."
            )
        
        return True, ""
    
    # MIN and MAX work on measures and temporal, and strings (alphabetically)
    if aggregation_fn in ["min", "max"]:
        # Allow on measures and temporal
        if role in ["measure", "datetime"]:
            return True, ""
        # Allow on string dimensions (alphabetical min/max) but it's less common
        if role in ["dimension", "id", "text", "boolean"]:
            # Allow but could warn - for now just allow
            return True, ""
        return True, ""
    
    return True, ""


def serialize_value(val):
    """Convert database values to JSON-serializable types."""
    if val is None:
        return None
    if isinstance(val, Decimal):
        return float(val)
    if isinstance(val, (date, datetime)):
        return val.isoformat()
    return val


@router.post("/chart-data", response_model=ChartDataResponse)
def get_chart_data(request: ChartDataRequest, db: Session = Depends(get_db)):
    """
    Query aggregated data from marts tables for chart visualization.
    
    This endpoint executes a GROUP BY query on the specified table,
    grouping by x_axis column and aggregating y_axis column.
    """
    # Validate x_axis column exists
    x_column_profile = get_column_profile_info(request.table_name, request.x_axis)
    if not x_column_profile:
        raise HTTPException(
            status_code=400,
            detail=f"Column '{request.x_axis}' not found in table '{request.table_name}'"
        )
    
    # Validate y_axis column exists
    y_column_profile = get_column_profile_info(request.table_name, request.y_axis)
    if not y_column_profile:
        raise HTTPException(
            status_code=400,
            detail=f"Column '{request.y_axis}' not found in table '{request.table_name}'"
        )
    
    # Validate aggregation is compatible with y_axis column type
    is_valid, error_msg = validate_aggregation_compatibility(
        y_column_profile,
        request.aggregation_fn
    )
    if not is_valid:
        raise HTTPException(
            status_code=400,
            detail=error_msg
        )
    
    # Build the aggregation function part
    agg_fn = request.aggregation_fn.upper()
    
    # Build safe SQL query using identifier quoting
    # Note: Column names are validated above against the profile
    query = text(f"""
        SELECT 
            CAST("{request.x_axis}" AS TEXT) as x_value,
            {agg_fn}("{request.y_axis}") as y_value
        FROM {MARTS_SCHEMA}."{request.table_name}"
        WHERE "{request.x_axis}" IS NOT NULL
        GROUP BY "{request.x_axis}"
        ORDER BY y_value DESC
        LIMIT :limit
    """)
    
    try:
        result = db.execute(query, {"limit": request.limit})
        rows = result.fetchall()
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Database query failed: {str(e)}"
        )
    
    if not rows:
        raise HTTPException(
            status_code=404,
            detail="No data found for the specified query"
        )
    
    # Extract x and y values
    x_values = [str(serialize_value(row[0])) if row[0] is not None else "NULL" for row in rows]
    y_values = [float(serialize_value(row[1])) if row[1] is not None else 0.0 for row in rows]
    
    # Build title
    title = f"{agg_fn}({request.y_axis}) by {request.x_axis}"
    
    return ChartDataResponse(
        x=x_values,
        y=y_values,
        title=title,
        x_axis_label=request.x_axis,
        y_axis_label=f"{agg_fn}({request.y_axis})"
    )
