"""
Profile service — shared logic for loading and querying profile metadata.

Extracted from profiling.py so both the profiling API and the engine
validator can use the same code without circular imports.
"""

import json
from pathlib import Path
from typing import Optional

from fastapi import HTTPException


# Path to the out directory containing profile JSONs
OUT_DIR = Path(__file__).parent.parent.parent / "out"

# Available tables and their profile file names (mart registry)
AVAILABLE_TABLES: dict[str, str] = {
    "mart_sales": "mart_sales_profile.json",
    "mart_customers": "mart_customers_profile.json",
    "mart_stores": "mart_stores_profile.json",
}

# Schema name for mart tables
MARTS_SCHEMA = "marts"


def load_profile(table_name: str) -> dict:
    """
    Load a profile JSON file for the given table.

    Raises HTTPException if the table or file is not found.
    """
    if table_name not in AVAILABLE_TABLES:
        raise HTTPException(status_code=404, detail=f"Table '{table_name}' not found")

    file_path = OUT_DIR / AVAILABLE_TABLES[table_name]

    if not file_path.exists():
        raise HTTPException(
            status_code=404,
            detail=f"Profile file for '{table_name}' not found",
        )

    try:
        with open(file_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except json.JSONDecodeError as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error parsing profile for '{table_name}': {str(e)}",
        )


def is_table_registered(table_name: str) -> bool:
    """Check whether a table is in the mart registry."""
    return table_name in AVAILABLE_TABLES


def get_column_profile_info(table_name: str, column_name: str) -> Optional[dict]:
    """
    Get column profile information including role and type.
    Returns None if the table or column cannot be found.
    """
    try:
        profile = load_profile(table_name)
        columns = profile.get("columns", [])
        for col in columns:
            if col.get("name") == column_name:
                return col
        return None
    except HTTPException:
        return None


def get_all_column_names(table_name: str) -> list[str]:
    """Return a list of all column names for a table."""
    try:
        profile = load_profile(table_name)
        return [col.get("name", "") for col in profile.get("columns", [])]
    except HTTPException:
        return []


def validate_column_exists(table_name: str, column_name: str) -> bool:
    """Check whether a column exists in the table profile."""
    return get_column_profile_info(table_name, column_name) is not None
