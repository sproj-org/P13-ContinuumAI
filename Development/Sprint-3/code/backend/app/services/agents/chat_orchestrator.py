"""Single-mart chat orchestration with typed response branches."""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any

from fastapi import HTTPException
from pydantic import TypeAdapter, ValidationError
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.mart_registry import get_mart
from app.services.agents.chat_models import (
    ChatChartResponse,
    ChatClarifyResponse,
    ChatExplainResponse,
    ChatRefuseResponse,
    ChatResponseUnion,
)
from app.services.agents.context_builder import build_chat_prompts
from app.services.agents.spec_patch import apply_patch
from app.services.charts.models import ChartSpecV1
from app.services.charts.spec_resolver import execute_chart_preview
from app.services.llm.openai_client import OpenAIClient, OpenAIJSONError

OUT_DIR = Path(__file__).resolve().parents[3] / "out"
_CHAT_ADAPTER = TypeAdapter(ChatResponseUnion)
_OFF_TOPIC_RE = re.compile(r"\b(poem|poetry|song|lyrics|story|novel|oceans?|haiku)\b", re.IGNORECASE)
_VAGUE_RE = re.compile(r"^\s*(help|analyze|chart|show|what next)\s*$", re.IGNORECASE)
_CHART_BY_RE = re.compile(
    r"(?:show|plot|chart|graph|display)?\s*(?P<metric>[a-zA-Z_][a-zA-Z0-9_]*)\s+(?:by|per|across)\s+(?P<x>[a-zA-Z_][a-zA-Z0-9_]*)",
    re.IGNORECASE,
)
_X_DIMENSION_ROLES = {"dimension", "id", "text", "boolean", "datetime", "temporal"}


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


def _chart_spec_hash(chart_spec: ChartSpecV1) -> str:
    canonical = json.dumps(chart_spec.model_dump(mode="json"), sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _format_metric_value(value: Any) -> str:
    if isinstance(value, (int, float)):
        return f"{value:,.2f}"
    return str(value)


def _build_chart_response(
    *,
    chart_spec: ChartSpecV1,
    preview_payload: dict[str, Any],
    base_narrative: str | None = None,
) -> ChatChartResponse:
    rows = preview_payload.get("rows", [])
    meta = preview_payload.get("meta", {})
    x_field = chart_spec.encoding.x.field
    metric_info = meta.get("metric", {})
    metric_column = metric_info.get("output_column", "agg_value")
    metric_label = f"{metric_info.get('aggregation', 'value')}({metric_info.get('field', metric_column)})"

    if rows:
        top_row = rows[0]
        top_x = top_row.get(x_field)
        top_metric = top_row.get(metric_column)
        summary = (
            f"Computed {len(rows)} grouped rows. "
            f"Top {x_field} is '{top_x}' with {metric_label} = {_format_metric_value(top_metric)}."
        )
    else:
        summary = "No rows were returned for this chart request."

    narrative = summary if not base_narrative else f"{base_narrative} {summary}"

    return ChatChartResponse(
        response_type="chart",
        chart_spec=chart_spec,
        columns=list(preview_payload.get("columns", [])),
        rows=list(rows),
        narrative=narrative,
        meta=dict(meta),
    )


def _build_clarify(message: str, questions: list[str] | None = None) -> ChatClarifyResponse:
    return ChatClarifyResponse(
        response_type="clarify",
        message=message,
        questions=questions or [],
        meta={},
    )


def _guardrail_or_none(message: str) -> ChatResponseUnion | None:
    if _OFF_TOPIC_RE.search(message):
        return ChatRefuseResponse(
            response_type="refuse",
            message="I can help with analytics for the selected mart. Ask about metrics, trends, filters, or breakdowns.",
            meta={},
        )
    if len(message.strip()) < 8 or _VAGUE_RE.match(message):
        return _build_clarify(
            "Please specify the metric and breakdown you want.",
            questions=[
                "Which measure should I use (for example net_sales, gross_sales, orders)?",
                "How should it be broken down (for example region, channel_type, sales_date)?",
            ],
        )
    return None


def _coerce_chart_spec(dataset_id: str, table: str, candidate: ChartSpecV1) -> ChartSpecV1:
    return candidate.model_copy(
        update={
            "version": "v1",
            "dataset_id": dataset_id,
            "table": table,
        }
    )


def _detect_aggregation(message: str) -> str:
    lowered = message.lower()
    if "average" in lowered or "mean" in lowered or "avg" in lowered:
        return "avg"
    if "count" in lowered or "number of" in lowered:
        return "count"
    if "min" in lowered or "lowest" in lowered:
        return "min"
    if "max" in lowered or "highest" in lowered:
        return "max"
    return "sum"


def _build_rule_based_chart_spec(dataset_id: str, table: str, message: str) -> ChartSpecV1 | None:
    match = _CHART_BY_RE.search(message.strip())
    if not match:
        return None

    metric_field = str(match.group("metric"))
    x_field = str(match.group("x"))
    profile = _load_profile(dataset_id, table)
    columns = profile.get("columns", [])
    role_by_name: dict[str, str] = {}
    if isinstance(columns, list):
        for raw in columns:
            if not isinstance(raw, dict):
                continue
            name = raw.get("name")
            if not isinstance(name, str):
                continue
            role_by_name[name] = str(raw.get("effective_role", raw.get("base_role", ""))).lower()

    metric_role = role_by_name.get(metric_field)
    x_role = role_by_name.get(x_field)
    if metric_role != "measure" or x_role not in _X_DIMENSION_ROLES:
        return None

    aggregation = _detect_aggregation(message)
    chart_type = "line" if x_role in {"datetime", "temporal"} else "bar"
    return ChartSpecV1(
        version="v1",
        dataset_id=dataset_id,
        table=table,
        chart={"type": chart_type},
        encoding={
            "x": {"field": x_field},
            "y": [
                {
                    "field": metric_field,
                    "aggregation": aggregation,
                    "alias": "metric_value",
                }
            ],
        },
        filters=[],
        sort=[{"field": "metric_value", "direction": "desc"}],
        limit=20,
    )


def _execute_chart_spec(dataset_id: str, chart_spec: ChartSpecV1, db: Session, *, narrative: str | None = None) -> ChatResponseUnion:
    try:
        preview_payload = execute_chart_preview(dataset_id=dataset_id, chart_spec=chart_spec, db=db)
    except HTTPException as exc:
        return _build_clarify(
            f"That chart is not valid for this mart: {exc.detail}",
            questions=["Pick an X field from dimensions/temporals and a Y field from measures."],
        )
    return _build_chart_response(chart_spec=chart_spec, preview_payload=preview_payload, base_narrative=narrative)


def _ground_explanation(dataset_id: str, table: str, message: str, db: Session) -> ChatExplainResponse:
    profile = _load_profile(dataset_id, table)
    row_count = profile.get("row_count")
    column_count = profile.get("column_count")
    topic = " ".join(message.strip().split())
    base = (
        f"For your question '{topic}', {table} currently has "
        f"{row_count} rows and {column_count} columns."
    )

    columns = profile.get("columns", [])
    temporal = None
    measure = None
    if isinstance(columns, list):
        for raw in columns:
            if not isinstance(raw, dict):
                continue
            name = raw.get("name")
            if not isinstance(name, str):
                continue
            role = str(raw.get("effective_role", raw.get("base_role", ""))).lower()
            if temporal is None and role in {"datetime", "temporal"}:
                temporal = name
            if measure is None and role == "measure":
                measure = name
            if temporal and measure:
                break

    if not temporal or not measure:
        return ChatExplainResponse(
            response_type="explain",
            message=base,
            citations=[f"profile:{table}"],
            meta={},
        )

    probe_spec = ChartSpecV1(
        version="v1",
        dataset_id=dataset_id,
        table=table,
        chart={"type": "line"},
        encoding={
            "x": {"field": temporal},
            "y": [{"field": measure, "aggregation": "sum", "alias": "metric_value"}],
        },
        filters=[],
        sort=[{"field": temporal, "direction": "desc"}],
        limit=2,
    )
    try:
        probe = execute_chart_preview(dataset_id=dataset_id, chart_spec=probe_spec, db=db)
        rows = probe.get("rows", [])
    except HTTPException:
        rows = []

    if isinstance(rows, list) and len(rows) >= 2:
        latest = rows[0]
        previous = rows[1]
        latest_v = latest.get("metric_value")
        previous_v = previous.get("metric_value")
        base = (
            f"{base} Recent executed values for {measure} by {temporal}: "
            f"{latest.get(temporal)}={_format_metric_value(latest_v)}, "
            f"{previous.get(temporal)}={_format_metric_value(previous_v)}."
        )

    return ChatExplainResponse(
        response_type="explain",
        message=base,
        citations=[f"profile:{table}", f"aggregate_probe:{measure}_by_{temporal}"],
        meta={},
    )


def _generate_llm_response(
    *,
    dataset_id: str,
    table: str,
    message: str,
    state: dict[str, Any] | None,
) -> ChatResponseUnion:
    settings = get_settings()
    if not settings.OPENAI_API_KEY:
        return _build_clarify("Chat model is unavailable because OPENAI_API_KEY is not configured.")

    system_prompt, user_prompt = build_chat_prompts(
        dataset_id=dataset_id,
        table=table,
        message=message,
        state=state,
    )
    try:
        client = OpenAIClient(
            api_key=settings.OPENAI_API_KEY,
            model=settings.OPENAI_MODEL,
            temperature=0.2,
        )
    except OpenAIJSONError as exc:
        return _build_clarify(str(exc))

    corrective_prompt: str | None = None
    for attempt in range(2):
        try:
            payload = client.generate_json(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                corrective_prompt=corrective_prompt,
            )
        except OpenAIJSONError:
            if attempt == 0:
                corrective_prompt = (
                    "Your previous response was invalid JSON. "
                    "Return exactly one valid JSON object with response_type."
                )
                continue
            return _build_clarify("I could not parse the request. Please rephrase with metric and breakdown.")
        except Exception:
            return _build_clarify("Chat model is temporarily unavailable. Please try again.")

        try:
            return _CHAT_ADAPTER.validate_python(payload)
        except ValidationError:
            if attempt == 0:
                corrective_prompt = (
                    "Your previous response did not match schema. "
                    "Return one JSON object with response_type in [chart,chart_patch,explain,clarify,refuse]."
                )
                continue
            return _build_clarify("I need a clearer analytics request. Please mention metric and grouping.")

    return _build_clarify("Please rephrase your request.")


def run_chat_orchestration(
    *,
    dataset_id: str,
    message: str,
    table: str,
    state: dict[str, Any] | None,
    db: Session,
) -> dict[str, Any]:
    if not table:
        raise HTTPException(status_code=400, detail="Select a mart first")

    guardrail_response = _guardrail_or_none(message)
    response = guardrail_response or _generate_llm_response(
        dataset_id=dataset_id,
        table=table,
        message=message,
        state=state,
    )

    if isinstance(response, ChatChartResponse):
        normalized_spec = _coerce_chart_spec(dataset_id, table, response.chart_spec)
        executed = _execute_chart_spec(dataset_id, normalized_spec, db, narrative=response.narrative)
        return executed.model_dump(mode="json")

    if response.response_type == "chart_patch":
        state = state or {}
        last_raw = state.get("last_chart_spec")
        if not last_raw:
            clarify = _build_clarify(
                "I need an existing chart to apply that update.",
                questions=["Start with a chart request, then ask for a refinement."],
            )
            return clarify.model_dump(mode="json")

        try:
            last_spec = ChartSpecV1.model_validate(last_raw)
            patched = apply_patch(last_spec, response.patch)
            patched = _coerce_chart_spec(dataset_id, table, patched)
        except (ValidationError, HTTPException) as exc:
            detail = exc.detail if isinstance(exc, HTTPException) else str(exc)
            clarify = _build_clarify(f"Patch could not be applied safely: {detail}")
            return clarify.model_dump(mode="json")

        executed = _execute_chart_spec(dataset_id, patched, db, narrative=response.narrative)
        return executed.model_dump(mode="json")

    if response.response_type == "explain":
        grounded = _ground_explanation(dataset_id=dataset_id, table=table, message=message, db=db)
        return grounded.model_dump(mode="json")

    if response.response_type in {"clarify", "refuse"}:
        fallback_spec = _build_rule_based_chart_spec(dataset_id, table, message)
        if fallback_spec is not None:
            executed = _execute_chart_spec(
                dataset_id,
                _coerce_chart_spec(dataset_id, table, fallback_spec),
                db,
                narrative="Generated from the requested metric-by-breakdown pattern.",
            )
            return executed.model_dump(mode="json")
        return response.model_dump(mode="json")

    fallback = _build_clarify("Please rephrase your analytics request with metric and grouping.")
    return fallback.model_dump(mode="json")


def response_chart_spec_hash(response_payload: dict[str, Any]) -> str | None:
    raw_spec = response_payload.get("chart_spec")
    if not isinstance(raw_spec, dict):
        return None
    try:
        spec = ChartSpecV1.model_validate(raw_spec)
    except ValidationError:
        return None
    return _chart_spec_hash(spec)
