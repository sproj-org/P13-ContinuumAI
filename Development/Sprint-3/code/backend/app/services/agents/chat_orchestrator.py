"""Single-mart chat orchestration for ChartSpec generation + execution."""

from __future__ import annotations

from typing import Any

from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.services.agents.context_builder import build_chat_prompts
from app.services.charts.models import ChartSpecV1
from app.services.charts.spec_resolver import execute_chart_preview
from app.services.llm.openai_client import OpenAIClient, OpenAIJSONError


def _format_metric_value(value: Any) -> str:
    if isinstance(value, (int, float)):
        return f"{value:,.2f}"
    return str(value)


def _build_narrative(preview_payload: dict[str, Any]) -> str:
    rows = preview_payload.get("rows", [])
    if not isinstance(rows, list) or not rows:
        return "No rows were returned for this chart request."

    chart_spec = preview_payload.get("chart_spec", {})
    meta = preview_payload.get("meta", {})
    x_field = chart_spec.get("encoding", {}).get("x", {}).get("field", "x")
    metric_info = meta.get("metric", {})
    metric_column = metric_info.get("output_column", "agg_value")
    metric_label = f"{metric_info.get('aggregation', 'value')}({metric_info.get('field', metric_column)})"

    top_row = rows[0]
    top_x = top_row.get(x_field)
    top_metric = top_row.get(metric_column)
    row_count = len(rows)

    return (
        f"Computed {row_count} grouped rows. "
        f"Top {x_field} is '{top_x}' with {metric_label} = {_format_metric_value(top_metric)}."
    )


def _generate_chart_spec(
    *,
    dataset_id: str,
    table: str,
    message: str,
    state: dict[str, Any] | None,
) -> ChartSpecV1:
    settings = get_settings()
    if not settings.OPENAI_API_KEY:
        raise HTTPException(status_code=503, detail="OPENAI_API_KEY is not configured")

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
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    corrective_prompt: str | None = None
    last_error = ""
    for attempt in range(2):
        try:
            payload = client.generate_json(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                corrective_prompt=corrective_prompt,
            )
        except OpenAIJSONError as exc:
            last_error = str(exc)
            if attempt == 0:
                corrective_prompt = (
                    "Your prior output was invalid JSON. "
                    "Return exactly one JSON object that matches ChartSpec v1."
                )
                continue
            raise HTTPException(status_code=400, detail="Chat model returned invalid JSON.") from exc

        try:
            spec = ChartSpecV1.model_validate(payload)
        except ValidationError as exc:
            last_error = str(exc)
            if attempt == 0:
                corrective_prompt = (
                    "Your prior JSON did not match ChartSpec v1 schema. "
                    "Return a valid ChartSpec v1 JSON only, using the provided table and columns."
                )
                continue
            raise HTTPException(status_code=400, detail="Chat model returned invalid chart specification.") from exc

        return spec

    raise HTTPException(status_code=400, detail=f"Unable to generate valid chart specification: {last_error}")


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

    generated_spec = _generate_chart_spec(
        dataset_id=dataset_id,
        table=table,
        message=message,
        state=state,
    )
    normalized_spec = generated_spec.model_copy(
        update={
            "dataset_id": dataset_id,
            "table": table,
            "version": "v1",
        }
    )
    preview_payload = execute_chart_preview(dataset_id=dataset_id, chart_spec=normalized_spec, db=db)
    narrative = _build_narrative(preview_payload)

    response_meta = dict(preview_payload.get("meta", {}))
    response_meta["chat"] = {
        "model": get_settings().OPENAI_MODEL,
        "table": table,
    }

    return {
        "response_type": "chart",
        "chart_spec": preview_payload.get("chart_spec"),
        "columns": preview_payload.get("columns"),
        "rows": preview_payload.get("rows"),
        "narrative": narrative,
        "meta": response_meta,
    }
