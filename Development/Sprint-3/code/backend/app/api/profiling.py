"""
Profiling API endpoints.
Serves pre-generated profile JSON files from the out/ directory.
"""

from fastapi import APIRouter, HTTPException

from app.services.profile_service import (
    load_profile,
    AVAILABLE_TABLES,
)

router = APIRouter(prefix="/profiling", tags=["profiling"])


@router.get("/aggregations")
def list_aggregations():
    """List all available aggregation tables with summary info."""
    aggregations = []

    for table_name in AVAILABLE_TABLES:
        try:
            profile = load_profile(table_name)
            aggregations.append(
                {
                    "table_name": profile.get("table_name")
                    or profile.get("dataset_name"),
                    "schema_name": profile.get("schema_name", "aggregations"),
                    "row_count": profile.get("row_count", 0),
                    "column_count": profile.get("column_count", 0),
                    "profiled_at": profile.get("profiled_at", ""),
                }
            )
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
        detail=f"Column '{column_name}' not found in table '{table_name}'",
    )
