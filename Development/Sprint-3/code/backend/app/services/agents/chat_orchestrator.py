"""LLM-led single-mart chat orchestration with strict execution guardrails."""

from __future__ import annotations

import hashlib
import json
from typing import Any

from fastapi import HTTPException
from pydantic import TypeAdapter, ValidationError
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.services.agents.chat_models import (
    ChatChartResponse,
    ChatClarifyResponse,
    ChatExplainResponse,
    ChatMode,
    ChatPlanChart,
    ChatPlanClarify,
    ChatPlanExplain,
    ChatPlanPatch,
    ChatPlanRefuse,
    ChatPlanUnion,
    ChatRefuseResponse,
    ChatResponseUnion,
    ClarifyOptions,
)
from app.services.agents.mart_context import build_compact_mart_context
from app.services.agents.spec_patch import apply_patch
from app.services.charts.models import ChartSpecV1
from app.services.charts.spec_resolver import execute_chart_preview
from app.services.llm.openai_client import OpenAIClient, OpenAIJSONError
from app.services.strategy.kpi_registry import list_kpis

_PLAN_ADAPTER = TypeAdapter(ChatPlanUnion)


def _chart_spec_hash(chart_spec: ChartSpecV1) -> str:
    canonical = json.dumps(chart_spec.model_dump(mode="json"), sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _format_metric_value(value: Any) -> str:
    if isinstance(value, (int, float)):
        return f"{value:,.2f}"
    return str(value)


def _extract_fields(context: dict[str, Any]) -> tuple[list[str], list[str], list[str]]:
    metrics = [item["name"] for item in context.get("measures", []) if isinstance(item, dict) and isinstance(item.get("name"), str)]
    dimensions = [
        item["name"] for item in context.get("dimensions", []) if isinstance(item, dict) and isinstance(item.get("name"), str)
    ]
    temporals = [item["name"] for item in context.get("temporals", []) if isinstance(item, dict) and isinstance(item.get("name"), str)]
    return metrics, dimensions, temporals


def _sanitize_options(options: ClarifyOptions, context: dict[str, Any]) -> ClarifyOptions:
    metrics, dimensions, temporals = _extract_fields(context)
    metric_set = set(metrics)
    dimension_set = set(dimensions)
    temporal_set = set(temporals)

    return ClarifyOptions(
        metrics=[item for item in options.metrics if item in metric_set][:6],
        dimensions=[item for item in options.dimensions if item in dimension_set][:6],
        temporals=[item for item in options.temporals if item in temporal_set][:6],
    )


def _default_clarify(question: str, context: dict[str, Any]) -> ChatClarifyResponse:
    metrics, dimensions, temporals = _extract_fields(context)
    return ChatClarifyResponse(
        response_type="clarify",
        question=question,
        options=ClarifyOptions(
            metrics=metrics[:4],
            dimensions=dimensions[:4],
            temporals=temporals[:3],
        ),
        meta={},
    )


def _coerce_chart_spec(dataset_id: str, table: str, candidate: ChartSpecV1) -> ChartSpecV1:
    return candidate.model_copy(
        update={
            "version": "v1",
            "dataset_id": dataset_id,
            "table": table,
        }
    )


def _chart_narrative(
    chart_spec: ChartSpecV1,
    preview_payload: dict[str, Any],
    *,
    style: str = "standard",
) -> str:
    rows = preview_payload.get("rows", [])
    if not isinstance(rows, list) or not rows:
        return "No rows were returned for this request."

    metric_info = preview_payload.get("meta", {}).get("metric", {})
    x_field = chart_spec.encoding.x.field
    metric_output = str(metric_info.get("output_column", "agg_value"))
    metric_label = f"{metric_info.get('aggregation', 'value')}({metric_info.get('field', metric_output)})"

    top_row = rows[0]
    top_x = top_row.get(x_field)
    top_metric = top_row.get(metric_output)
    if style == "brief":
        return f"Top {x_field}: '{top_x}' with {metric_label}={_format_metric_value(top_metric)}."
    return (
        f"Computed {len(rows)} grouped rows. "
        f"Top {x_field} is '{top_x}' with {metric_label} = {_format_metric_value(top_metric)}."
    )


def _execute_chart(
    *,
    dataset_id: str,
    table: str,
    chart_spec: ChartSpecV1,
    db: Session,
    style: str = "standard",
    debug: bool = False,
) -> ChatChartResponse | ChatClarifyResponse:
    normalized = _coerce_chart_spec(dataset_id=dataset_id, table=table, candidate=chart_spec)
    try:
        try:
            preview_payload = execute_chart_preview(dataset_id=dataset_id, chart_spec=normalized, db=db, debug=debug)
        except TypeError:
            preview_payload = execute_chart_preview(dataset_id=dataset_id, chart_spec=normalized, db=db)
    except HTTPException as exc:
        return ChatClarifyResponse(
            response_type="clarify",
            question=f"That request is invalid for this mart: {exc.detail}",
            options=ClarifyOptions(),
            meta={},
        )

    return ChatChartResponse(
        response_type="chart",
        chart_spec=normalized,
        columns=list(preview_payload.get("columns", [])),
        rows=list(preview_payload.get("rows", [])),
        narrative=_chart_narrative(normalized, preview_payload, style=style),
        meta=dict(preview_payload.get("meta", {})),
    )


def _build_system_prompt(mode: ChatMode) -> str:
    mode_clause = {
        "auto": "In auto mode choose the best response type based on intent.",
        "chart": "Mode is chart. You must return chart or clarify.",
        "explain": "Mode is explain. You must return explain.",
    }[mode]
    return (
        "You are ContinuumAI analytics assistant for one selected mart. "
        "Never output SQL. Never fabricate values. "
        "Prefer chart/chart_patch when the user asks for numeric comparison or breakdown. "
        "Clarify only if ambiguity blocks execution, and ask only one question with practical options. "
        "If user is off-topic, return refuse. "
        f"{mode_clause} "
        "Return JSON only, exactly one object, no markdown and no backticks."
    )


def _build_user_prompt(
    *,
    dataset_id: str,
    table: str,
    message: str,
    mode: ChatMode,
    context: dict[str, Any],
    state: dict[str, Any],
) -> str:
    compact_kpis = [
        {
            "id": item.get("id"),
            "label": item.get("label"),
            "default_metric": item.get("default_metric"),
            "default_dimension": item.get("default_dimension"),
        }
        for item in list_kpis(dataset_id)
        if item.get("table") == table
    ][:8]

    response_schema = {
        "chart": {"response_type": "chart", "chart_spec": "ChartSpecV1", "narrative_style": "brief|standard"},
        "chart_patch": {"response_type": "chart_patch", "patch": {"set": {}, "unset": [], "add": {}}},
        "explain": {
            "response_type": "explain",
            "message": "string",
            "optional_chart_spec": "ChartSpecV1 | omitted",
        },
        "clarify": {
            "response_type": "clarify",
            "question": "single question",
            "options": {"metrics": [], "dimensions": [], "temporals": []},
        },
        "refuse": {"response_type": "refuse", "message": "string"},
    }

    chartspec_summary = {
        "version": "v1",
        "required": ["version", "table", "chart", "encoding"],
        "chart_type": ["bar", "line", "pie", "histogram", "kpi"],
        "x_rule": "encoding.x.field must be dimension|temporal",
        "y_rule": "encoding.y[0].field must be measure, aggregation in sum|avg|count|min|max",
        "filters": "=, !=, in, between, >, >=, <, <=",
    }

    return (
        f"User message: {message}\n"
        f"Mode: {mode}\n\n"
        f"Dataset: {dataset_id}\n"
        f"Table: {table}\n"
        f"Compact mart context: {json.dumps(context, ensure_ascii=True)}\n\n"
        f"Available KPI hints: {json.dumps(compact_kpis, ensure_ascii=True)}\n"
        f"Last chart spec state: {json.dumps(state.get('last_chart_spec'), ensure_ascii=True)}\n\n"
        f"ChartSpec summary: {json.dumps(chartspec_summary, ensure_ascii=True)}\n"
        f"Allowed response schema: {json.dumps(response_schema, ensure_ascii=True)}\n"
        "Important: choose best available fields from context; avoid unnecessary clarify."
    )


def _generate_plan(
    *,
    dataset_id: str,
    table: str,
    message: str,
    mode: ChatMode,
    context: dict[str, Any],
    state: dict[str, Any],
) -> ChatPlanUnion | None:
    settings = get_settings()
    if not settings.OPENAI_API_KEY:
        return None

    try:
        client = OpenAIClient(
            api_key=settings.OPENAI_API_KEY,
            model=settings.OPENAI_MODEL,
            temperature=0.2,
        )
    except OpenAIJSONError:
        return None

    system_prompt = _build_system_prompt(mode)
    user_prompt = _build_user_prompt(
        dataset_id=dataset_id,
        table=table,
        message=message,
        mode=mode,
        context=context,
        state=state,
    )

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
                corrective_prompt = "Your previous output was invalid JSON. Return one valid JSON object only."
                continue
            return None
        except Exception:
            return None

        try:
            return _PLAN_ADAPTER.validate_python(payload)
        except ValidationError:
            if attempt == 0:
                corrective_prompt = (
                    "Your previous response did not match schema. "
                    "Return one JSON object with response_type in [chart,chart_patch,explain,clarify,refuse]."
                )
                continue
            return None
    return None


def _enforce_mode(plan: ChatPlanUnion, mode: ChatMode, context: dict[str, Any]) -> ChatPlanUnion:
    if mode == "chart" and plan.response_type not in {"chart", "chart_patch", "clarify"}:
        return ChatPlanClarify(
            response_type="clarify",
            question="Which metric and breakdown should I chart?",
            options=ClarifyOptions(
                metrics=_extract_fields(context)[0][:4],
                dimensions=_extract_fields(context)[1][:4],
                temporals=_extract_fields(context)[2][:3],
            ),
        )

    if mode == "explain" and plan.response_type != "explain":
        return ChatPlanExplain(
            response_type="explain",
            message="I will explain the selected mart based on its schema and available metrics.",
        )
    return plan


def _context_explain_message(
    *,
    context: dict[str, Any],
    table: str,
    user_message: str,
) -> str:
    description = context.get("description") or "an analytics mart"
    metrics, dimensions, temporals = _extract_fields(context)
    metric_preview = ", ".join(metrics[:4]) if metrics else "none"
    dim_preview = ", ".join(dimensions[:4]) if dimensions else "none"
    temporal_preview = ", ".join(temporals[:3]) if temporals else "none"
    topic = " ".join(user_message.strip().split())
    return (
        f"For '{topic}', {table} represents {description}. "
        f"Measures include: {metric_preview}. "
        f"Dimensions include: {dim_preview}. "
        f"Temporal fields include: {temporal_preview}."
    )


def run_chat_orchestration(
    *,
    dataset_id: str,
    message: str,
    table: str | None,
    mode: ChatMode = "auto",
    state: dict[str, Any] | None,
    db: Session,
    debug: bool = False,
) -> dict[str, Any]:
    if not table:
        return ChatClarifyResponse(
            response_type="clarify",
            question="Select a mart to proceed.",
            options=ClarifyOptions(),
            meta={},
        ).model_dump(mode="json")

    state = state or {}
    context = build_compact_mart_context(dataset_id=dataset_id, table=table)
    plan = _generate_plan(
        dataset_id=dataset_id,
        table=table,
        message=message,
        mode=mode,
        context=context,
        state=state,
    )
    if plan is None:
        return _default_clarify("Please rephrase your request with a metric and breakdown.", context).model_dump(mode="json")

    plan = _enforce_mode(plan=plan, mode=mode, context=context)

    if isinstance(plan, ChatPlanChart):
        chart_response = _execute_chart(
            dataset_id=dataset_id,
            table=table,
            chart_spec=plan.chart_spec,
            db=db,
            style=plan.narrative_style,
            debug=debug,
        )
        return chart_response.model_dump(mode="json")

    if isinstance(plan, ChatPlanPatch):
        last_raw = state.get("last_chart_spec")
        if not last_raw:
            return _default_clarify("I need an existing chart first. What should we chart?", context).model_dump(mode="json")
        try:
            base = ChartSpecV1.model_validate(last_raw)
            patched = apply_patch(base, plan.patch)
        except (ValidationError, HTTPException):
            return _default_clarify("I could not apply that update safely. Choose a metric or dimension.", context).model_dump(mode="json")

        chart_response = _execute_chart(
            dataset_id=dataset_id,
            table=table,
            chart_spec=patched,
            db=db,
            style=plan.narrative_style,
            debug=debug,
        )
        return chart_response.model_dump(mode="json")

    if isinstance(plan, ChatPlanExplain):
        if plan.optional_chart_spec:
            chart_response = _execute_chart(
                dataset_id=dataset_id,
                table=table,
                chart_spec=plan.optional_chart_spec,
                db=db,
                style="brief",
                debug=debug,
            )
            if isinstance(chart_response, ChatChartResponse):
                explain_message = f"{plan.message} {chart_response.narrative}"
                return ChatExplainResponse(
                    response_type="explain",
                    message=explain_message.strip(),
                    citations=["charts_preview"],
                    meta={"from_chart_preview": True, "chart_spec": chart_response.chart_spec.model_dump(mode="json")},
                ).model_dump(mode="json")

        explain_message = _context_explain_message(context=context, table=table, user_message=message)
        return ChatExplainResponse(
            response_type="explain",
            message=explain_message,
            citations=[f"profile:{table}"],
            meta={},
        ).model_dump(mode="json")

    if isinstance(plan, ChatPlanClarify):
        return ChatClarifyResponse(
            response_type="clarify",
            question=plan.question.strip() or "What metric and breakdown should I use?",
            options=_sanitize_options(plan.options, context),
            meta={},
        ).model_dump(mode="json")

    if isinstance(plan, ChatPlanRefuse):
        return ChatRefuseResponse(
            response_type="refuse",
            message=plan.message.strip() or "I can only help with analytics for the selected mart.",
            meta={},
        ).model_dump(mode="json")

    return _default_clarify("Please rephrase your analytics request.", context).model_dump(mode="json")


def response_chart_spec_hash(response_payload: dict[str, Any]) -> str | None:
    raw_spec = response_payload.get("chart_spec")
    if not isinstance(raw_spec, dict):
        return None
    try:
        spec = ChartSpecV1.model_validate(raw_spec)
    except ValidationError:
        return None
    return _chart_spec_hash(spec)
