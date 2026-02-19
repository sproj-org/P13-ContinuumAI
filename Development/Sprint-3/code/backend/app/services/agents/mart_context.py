"""Compact mart context builder for chat planning."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from fastapi import HTTPException

from app.core.mart_registry import get_mart

OUT_DIR = Path(__file__).resolve().parents[3] / "out"
DIMENSION_ROLES = {"dimension", "id", "text", "boolean"}
TEMPORAL_ROLES = {"datetime", "temporal"}
MEASURE_ROLES = {"measure"}
MAX_DIMENSIONS = 25
MAX_MEASURES = 25
MAX_SAMPLE_VALUES = 4


def _load_profile(dataset_id: str, table: str) -> tuple[dict[str, Any], dict[str, Any]]:
    try:
        mart = get_mart(dataset_id, table)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    profile_path = OUT_DIR / str(mart["profile_file"])
    if not profile_path.exists():
        raise HTTPException(status_code=404, detail=f"Profile file not found for table '{table}'")

    try:
        profile = json.loads(profile_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=500, detail=f"Invalid profile JSON for table '{table}': {exc}") from exc

    return mart, profile


def _safe_list(values: Any, *, max_items: int) -> list[Any]:
    if not isinstance(values, list):
        return []
    return values[:max_items]


def _effective_role(raw_column: dict[str, Any]) -> str:
    role = raw_column.get("effective_role") or raw_column.get("base_role") or ""
    return str(role).lower()


def _base_entry(raw_column: dict[str, Any]) -> dict[str, Any]:
    return {
        "name": raw_column.get("name"),
        "type": raw_column.get("physical_type"),
        "role": _effective_role(raw_column),
    }


def _temporal_entry(raw_column: dict[str, Any]) -> dict[str, Any]:
    stats = raw_column.get("stats", {}) if isinstance(raw_column.get("stats"), dict) else {}
    entry = _base_entry(raw_column)
    entry["min"] = stats.get("min")
    entry["max"] = stats.get("max")
    entry["null_rate"] = raw_column.get("null_fraction")
    return entry


def _dimension_entry(raw_column: dict[str, Any]) -> dict[str, Any]:
    entry = _base_entry(raw_column)
    entry["distinct_count"] = raw_column.get("distinct_count")
    entry["sample_values"] = _safe_list(raw_column.get("sample_values"), max_items=MAX_SAMPLE_VALUES)
    return entry


def _measure_entry(raw_column: dict[str, Any]) -> dict[str, Any]:
    stats = raw_column.get("stats", {}) if isinstance(raw_column.get("stats"), dict) else {}
    entry = _base_entry(raw_column)
    entry["min"] = stats.get("min")
    entry["max"] = stats.get("max")
    entry["avg"] = stats.get("mean")
    entry["null_rate"] = raw_column.get("null_fraction")
    return entry


def _rank_dimension(entry: dict[str, Any]) -> tuple[int, int, str]:
    distinct = entry.get("distinct_count")
    distinct_value = int(distinct) if isinstance(distinct, int) else 0
    name = str(entry.get("name") or "")
    # Prefer dimensions with moderate/high cardinality, then stable lexical ordering.
    return (0 if distinct_value > 1 else 1, -distinct_value, name)


def _rank_measure(entry: dict[str, Any]) -> tuple[int, str]:
    null_rate = entry.get("null_rate")
    null_score = int(float(null_rate) * 1000) if isinstance(null_rate, (int, float)) else 1000
    name = str(entry.get("name") or "")
    return (null_score, name)


def build_compact_mart_context(dataset_id: str, table: str) -> dict[str, Any]:
    """Build compact context for a selected mart based on profiling metadata."""
    mart, profile = _load_profile(dataset_id=dataset_id, table=table)
    raw_columns = profile.get("columns", [])
    if not isinstance(raw_columns, list):
        raw_columns = []

    temporals: list[dict[str, Any]] = []
    dimensions: list[dict[str, Any]] = []
    measures: list[dict[str, Any]] = []

    for raw_column in raw_columns:
        if not isinstance(raw_column, dict):
            continue
        name = raw_column.get("name")
        if not isinstance(name, str):
            continue
        role = _effective_role(raw_column)
        if role in TEMPORAL_ROLES:
            temporals.append(_temporal_entry(raw_column))
            continue
        if role in MEASURE_ROLES:
            measures.append(_measure_entry(raw_column))
            continue
        if role in DIMENSION_ROLES:
            dimensions.append(_dimension_entry(raw_column))

    dimensions = sorted(dimensions, key=_rank_dimension)[:MAX_DIMENSIONS]
    measures = sorted(measures, key=_rank_measure)[:MAX_MEASURES]

    return {
        "table_id": table,
        "description": mart.get("description"),
        "temporals": temporals,
        "dimensions": dimensions,
        "measures": measures,
        "role_rules": {
            "x": "dimension|temporal",
            "y": "measure with agg",
            "filters": "must reference valid fields",
        },
    }
