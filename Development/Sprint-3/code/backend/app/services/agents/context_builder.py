"""Build chat context for single-mart chart generation."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from fastapi import HTTPException

from app.core.mart_registry import get_mart
from app.services.charts.models import ChartSpecV1
from app.services.strategy.kpi_registry import list_kpis

OUT_DIR = Path(__file__).resolve().parents[3] / "out"


def _load_profile(dataset_id: str, table: str) -> dict[str, Any]:
    try:
        mart = get_mart(dataset_id, table)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    profile_path = OUT_DIR / str(mart["profile_file"])
    if not profile_path.exists():
        raise HTTPException(status_code=404, detail=f"Profile file not found for table '{table}'")
    try:
        return json.loads(profile_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=500, detail=f"Invalid profile JSON for table '{table}': {exc}") from exc


def _column_snapshot(profile: dict[str, Any], *, max_columns: int = 40) -> list[dict[str, Any]]:
    columns = profile.get("columns", [])
    if not isinstance(columns, list):
        return []

    snapshot: list[dict[str, Any]] = []
    for raw_column in columns[:max_columns]:
        if not isinstance(raw_column, dict):
            continue
        snapshot.append(
            {
                "name": raw_column.get("name"),
                "role": raw_column.get("effective_role", raw_column.get("base_role")),
                "physical_type": raw_column.get("physical_type"),
                "null_fraction": raw_column.get("null_fraction"),
                "distinct_count": raw_column.get("distinct_count"),
                "sample_values": list(raw_column.get("sample_values", [])[:3]),
            }
        )
    return snapshot


def _example_spec(dataset_id: str, table: str, profile: dict[str, Any]) -> dict[str, Any]:
    columns = profile.get("columns", [])
    if not isinstance(columns, list):
        return {}

    first_dimension = None
    first_measure = None
    for raw_column in columns:
        if not isinstance(raw_column, dict):
            continue
        role = str(raw_column.get("effective_role", raw_column.get("base_role", ""))).lower()
        name = raw_column.get("name")
        if not isinstance(name, str):
            continue
        if first_dimension is None and role in {"dimension", "datetime", "temporal", "id", "text", "boolean"}:
            first_dimension = name
        if first_measure is None and role == "measure":
            first_measure = name
        if first_dimension and first_measure:
            break

    if not first_dimension or not first_measure:
        return {}

    return ChartSpecV1(
        version="v1",
        dataset_id=dataset_id,
        table=table,
        chart={"type": "bar"},
        encoding={
            "x": {"field": first_dimension},
            "y": [{"field": first_measure, "aggregation": "sum", "alias": "metric_value"}],
        },
        filters=[],
        sort=[{"field": "metric_value", "direction": "desc"}],
        limit=20,
    ).model_dump(mode="json")


def build_chat_prompts(
    *,
    dataset_id: str,
    table: str,
    message: str,
    state: dict[str, Any] | None = None,
) -> tuple[str, str]:
    mart = get_mart(dataset_id, table)
    profile = _load_profile(dataset_id, table)
    kpis = [item for item in list_kpis(dataset_id) if item["table"] == table]
    context_payload = {
        "dataset_id": dataset_id,
        "table": table,
        "mart": {
            "id": mart.get("id"),
            "label": mart.get("label"),
            "description": mart.get("description"),
            "schema": mart.get("schema"),
        },
        "columns": _column_snapshot(profile),
        "kpis": kpis,
        "chartspec_schema": ChartSpecV1.model_json_schema(),
        "chartspec_example": _example_spec(dataset_id, table, profile),
        "state": state or {},
        "message": message,
    }

    system_prompt = (
        "You are a chart planning assistant for ContinuumAI. "
        "Output JSON only. Do not output SQL. Do not invent columns. "
        "Use only provided table and provided columns. "
        "Return one object that matches ChartSpec v1."
    )
    user_prompt = (
        "Build a ChartSpec v1 JSON object for the request below. "
        "Keep table exactly as provided and set version='v1'. "
        "Prefer limit <= 50 and include sort by metric_value desc.\n\n"
        f"{json.dumps(context_payload, ensure_ascii=True)}"
    )
    return system_prompt, user_prompt
