"""Build concise, role-aware prompts for chat orchestration."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from fastapi import HTTPException

from app.core.mart_registry import get_mart
from app.services.strategy.kpi_registry import list_kpis

OUT_DIR = Path(__file__).resolve().parents[3] / "out"
DIMENSION_ROLES = {"dimension", "id", "text", "boolean"}
TEMPORAL_ROLES = {"datetime", "temporal"}
MEASURE_ROLES = {"measure"}


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


def _field_candidates(profile: dict[str, Any]) -> dict[str, list[str]]:
    columns = profile.get("columns", [])
    dims: list[str] = []
    temporals: list[str] = []
    measures: list[str] = []
    if isinstance(columns, list):
        for raw in columns:
            if not isinstance(raw, dict):
                continue
            name = raw.get("name")
            if not isinstance(name, str):
                continue
            role = str(raw.get("effective_role", raw.get("base_role", ""))).lower()
            if role in TEMPORAL_ROLES:
                temporals.append(name)
            elif role in MEASURE_ROLES:
                measures.append(name)
            elif role in DIMENSION_ROLES:
                dims.append(name)
    return {
        "dimensions": dims[:30],
        "temporals": temporals[:20],
        "measures": measures[:30],
    }


def _column_notes(profile: dict[str, Any], *, max_notes: int = 15) -> list[dict[str, Any]]:
    columns = profile.get("columns", [])
    notes: list[dict[str, Any]] = []
    if not isinstance(columns, list):
        return notes
    for raw in columns[:max_notes]:
        if not isinstance(raw, dict):
            continue
        name = raw.get("name")
        if not isinstance(name, str):
            continue
        notes.append(
            {
                "name": name,
                "role": raw.get("effective_role", raw.get("base_role")),
                "null_fraction": raw.get("null_fraction"),
                "distinct_count": raw.get("distinct_count"),
                "sample_values": list(raw.get("sample_values", [])[:2]),
            }
        )
    return notes


def _micro_examples(table: str, candidates: dict[str, list[str]]) -> list[dict[str, Any]]:
    dimensions = candidates["dimensions"]
    temporals = candidates["temporals"]
    measures = candidates["measures"]
    x_dim = dimensions[0] if dimensions else (temporals[0] if temporals else "")
    y_measure = measures[0] if measures else ""
    alt_dim = dimensions[1] if len(dimensions) > 1 else x_dim

    examples: list[dict[str, Any]] = []
    if x_dim and y_measure:
        examples.append(
            {
                "intent": "chart",
                "response_type": "chart",
                "chart_spec": {
                    "version": "v1",
                    "table": table,
                    "chart": {"type": "bar"},
                    "encoding": {
                        "x": {"field": x_dim},
                        "y": [{"field": y_measure, "aggregation": "sum", "alias": "metric_value"}],
                    },
                    "filters": [],
                    "sort": [{"field": "metric_value", "direction": "desc"}],
                    "limit": 20,
                },
            }
        )
        examples.append(
            {
                "intent": "follow_up_patch",
                "response_type": "chart_patch",
                "patch": {
                    "set": {"encoding.x.field": alt_dim},
                    "unset": [],
                    "add": {},
                },
            }
        )
    examples.append(
        {
            "intent": "vague_prompt",
            "response_type": "clarify",
            "message": "Do you want breakdown by a dimension (for example region) or a time trend?",
        }
    )
    return examples


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
    candidates = _field_candidates(profile)
    column_notes = _column_notes(profile)
    state = state or {}

    system_prompt = (
        "You are ContinuumAI assistant for a single mart. "
        "Return one JSON object only. No markdown, no backticks, no SQL. "
        "Never fabricate numbers. If numbers are needed, provide a chart/chart_patch plan for execution. "
        "Allowed response_type: chart, chart_patch, explain, clarify, refuse. "
        "DO NOT copy examples verbatim; examples are illustrative only."
    )

    user_prompt = (
        f"User message: {message}\n\n"
        f"Dataset: {dataset_id}\n"
        f"Table: {table}\n"
        f"Mart label: {mart.get('label')}\n"
        f"Mart description: {mart.get('description')}\n\n"
        "Field candidates by role:\n"
        f"- dimensions: {json.dumps(candidates['dimensions'], ensure_ascii=True)}\n"
        f"- temporals: {json.dumps(candidates['temporals'], ensure_ascii=True)}\n"
        f"- measures: {json.dumps(candidates['measures'], ensure_ascii=True)}\n"
        "- allowed aggregations: [\"sum\",\"avg\",\"count\",\"min\",\"max\"]\n\n"
        f"Last chart state: {json.dumps(state.get('last_chart_spec'), ensure_ascii=True)}\n\n"
        f"KPI hints for this table: {json.dumps(kpis, ensure_ascii=True)}\n\n"
        f"Column notes: {json.dumps(column_notes, ensure_ascii=True)}\n\n"
        "Output shape rules:\n"
        "- chart: {response_type, chart_spec}\n"
        "- chart_patch: {response_type, patch:{set,unset,add}, narrative?}\n"
        "- explain: {response_type, message}\n"
        "- clarify: {response_type, message, questions?}\n"
        "- refuse: {response_type, message}\n\n"
        f"Examples only (do not copy): {json.dumps(_micro_examples(table, candidates), ensure_ascii=True)}"
    )
    return system_prompt, user_prompt
