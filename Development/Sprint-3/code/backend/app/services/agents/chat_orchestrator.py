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
    ChatSelections,
    ChatState,
    ClarifyOptions,
    create_clarify_id,
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


def _normalize_text(value: str) -> str:
    cleaned = value.lower().replace("_", " ")
    return " ".join(cleaned.split())


def _contains_any(text: str, needles: list[str]) -> bool:
    return any(needle in text for needle in needles)


def _pick_matching_field(message: str, fields: list[str]) -> str | None:
    normalized_message = _normalize_text(message)
    for field in fields:
        normalized_field = _normalize_text(field)
        if normalized_field and normalized_field in normalized_message:
            return field
    return None


def _options_from_context(context: dict[str, Any]) -> ClarifyOptions:
    metrics, dimensions, temporals = _extract_fields(context)
    return ClarifyOptions(
        metrics=metrics[:6],
        dimensions=dimensions[:6],
        temporals=temporals[:6],
    )


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


def _missing_from_selections(selections: ChatSelections) -> list[str]:
    missing: list[str] = []
    if not selections.metric:
        missing.append("metric")
    if not selections.dimension and not selections.temporal:
        missing.append("dimension")
    return missing


def _question_for_missing(missing: list[str]) -> str:
    missing_set = set(missing)
    if missing_set == {"metric", "dimension"}:
        return "Which metric and breakdown should I use for this chart?"
    if missing_set == {"metric"}:
        return "Which metric should I use?"
    if "dimension" in missing_set:
        return "Which breakdown (dimension or temporal field) should I use?"
    return "What should I adjust next?"


def _default_clarify(
    question: str,
    context: dict[str, Any],
    *,
    clarify_id: str | None = None,
    missing: list[str] | None = None,
) -> ChatClarifyResponse:
    return ChatClarifyResponse(
        response_type="clarify",
        clarify_id=clarify_id or create_clarify_id(),
        question=question,
        missing=missing or [],
        options=_options_from_context(context),
        meta={},
    )


def _parse_state(raw_state: ChatState | dict[str, Any] | None) -> ChatState:
    if raw_state is None:
        return ChatState()
    if isinstance(raw_state, ChatState):
        return raw_state
    try:
        return ChatState.model_validate(raw_state)
    except ValidationError:
        return ChatState()


def _sanitize_selections(context: dict[str, Any], selections: ChatSelections) -> ChatSelections:
    metrics, dimensions, temporals = _extract_fields(context)
    metric_set = set(metrics)
    dimension_set = set(dimensions)
    temporal_set = set(temporals)

    metric = selections.metric if selections.metric in metric_set else None
    dimension = selections.dimension if selections.dimension in dimension_set else None
    temporal = selections.temporal if selections.temporal in temporal_set else None

    if not temporal and selections.dimension in temporal_set:
        temporal = selections.dimension
    if not dimension and selections.temporal in dimension_set:
        dimension = selections.temporal

    return ChatSelections(
        metric=metric,
        dimension=dimension,
        temporal=temporal,
        time_grain=selections.time_grain,
        aggregation=selections.aggregation,
        limit=selections.limit,
    )


def _normalize_clarify_plan_payload(payload: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
    response_type = payload.get("response_type")
    if response_type != "clarify":
        return payload

    normalized = dict(payload)
    clarify_id = normalized.get("clarify_id")
    if not isinstance(clarify_id, str) or not clarify_id.strip():
        normalized["clarify_id"] = create_clarify_id()

    missing = normalized.get("missing")
    if not isinstance(missing, list):
        normalized["missing"] = []

    options = normalized.get("options")
    if not isinstance(options, dict):
        normalized["options"] = _options_from_context(context).model_dump(mode="json")
    return normalized


def _state_driven_plan(
    *,
    table: str,
    mode: ChatMode,
    context: dict[str, Any],
    state: ChatState,
) -> ChatPlanUnion | None:
    selections = _sanitize_selections(context, state.selections)
    has_selection = bool(selections.metric or selections.dimension or selections.temporal)
    if not state.clarify_id and not has_selection:
        return None

    missing = _missing_from_selections(selections)
    if missing:
        return ChatPlanClarify(
            response_type="clarify",
            clarify_id=state.clarify_id or create_clarify_id(),
            question=_question_for_missing(missing),
            missing=missing,
            options=_options_from_context(context),
        )

    x_field = selections.temporal or selections.dimension
    if not x_field or not selections.metric:
        return ChatPlanClarify(
            response_type="clarify",
            clarify_id=state.clarify_id or create_clarify_id(),
            question="Which metric and breakdown should I use for this chart?",
            missing=["metric", "dimension"],
            options=_options_from_context(context),
        )

    metrics, _, temporals = _extract_fields(context)
    if selections.metric not in set(metrics):
        return ChatPlanClarify(
            response_type="clarify",
            clarify_id=state.clarify_id or create_clarify_id(),
            question="Pick a valid metric from this mart.",
            missing=["metric"],
            options=_options_from_context(context),
        )

    chart_type = "line" if x_field in set(temporals) else "bar"
    return ChatPlanChart(
        response_type="chart",
        chart_spec=ChartSpecV1(
            version="v1",
            table=table,
            chart={"type": chart_type},
            encoding={
                "x": {"field": x_field},
                "y": [
                    {
                        "field": selections.metric,
                        "aggregation": selections.aggregation or "sum",
                        "alias": "metric_value",
                    }
                ],
            },
            filters=[],
            sort=[{"field": "metric_value", "direction": "desc"}],
            limit=selections.limit or 20,
        ),
        narrative_style="standard" if mode != "explain" else "brief",
    )


def _aggregation_from_message(message: str) -> str:
    text = _normalize_text(message)
    if _contains_any(text, ["average", "avg", "mean"]):
        return "avg"
    if _contains_any(text, ["count", "how many", "number of"]):
        return "count"
    if _contains_any(text, ["minimum", "lowest", "min"]):
        return "min"
    if _contains_any(text, ["maximum", "highest", "max"]):
        return "max"
    return "sum"


def _is_obviously_off_topic(message: str) -> bool:
    text = _normalize_text(message)
    return _contains_any(text, ["poem", "song", "lyrics", "novel", "haiku", "joke", "recipe"])


def _fallback_plan_from_context(
    *,
    message: str,
    mode: ChatMode,
    table: str,
    context: dict[str, Any],
) -> ChatPlanUnion:
    metrics, dimensions, temporals = _extract_fields(context)
    metric = _pick_matching_field(message, metrics)
    x_field = _pick_matching_field(message, [*dimensions, *temporals])

    if mode == "explain":
        return ChatPlanExplain(
            response_type="explain",
            message=f"Explanation for {table} based on mart metadata and available fields.",
        )

    normalized = _normalize_text(message)
    if _is_obviously_off_topic(message):
        return ChatPlanRefuse(
            response_type="refuse",
            message="I can help with analytics for the selected mart. Ask about metrics, trends, filters, or breakdowns.",
        )

    if not metric and mode == "chart" and metrics:
        metric = metrics[0]
    if not x_field and mode == "chart":
        if temporals and _contains_any(normalized, ["trend", "month", "day", "date", "time"]):
            x_field = temporals[0]
        elif dimensions:
            x_field = dimensions[0]
        elif temporals:
            x_field = temporals[0]

    if mode == "auto":
        if _contains_any(normalized, ["explain", "what is", "what does", "why"]):
            return ChatPlanExplain(
                response_type="explain",
                message=f"Explanation for {table} based on mart metadata and available fields.",
            )
        if metric and not x_field:
            if temporals and _contains_any(normalized, ["trend", "month", "day", "date", "time"]):
                x_field = temporals[0]
            elif dimensions:
                x_field = dimensions[0]
            elif temporals:
                x_field = temporals[0]

    if metric and x_field:
        return ChatPlanChart(
            response_type="chart",
            chart_spec=ChartSpecV1(
                version="v1",
                table=table,
                chart={"type": "line" if x_field in set(temporals) else "bar"},
                encoding={
                    "x": {"field": x_field},
                    "y": [{"field": metric, "aggregation": _aggregation_from_message(message), "alias": "metric_value"}],
                },
                filters=[],
                sort=[{"field": "metric_value", "direction": "desc"}],
                limit=20,
            ),
            narrative_style="standard",
        )

    if mode == "chart":
        return ChatPlanClarify(
            response_type="clarify",
            clarify_id=create_clarify_id(),
            question="Which metric and breakdown should I chart?",
            missing=["metric", "dimension"],
            options=_options_from_context(context),
        )

    return ChatPlanClarify(
        response_type="clarify",
        clarify_id=create_clarify_id(),
        question="I can chart this quickly. Which metric and breakdown should I use?",
        missing=["metric", "dimension"],
        options=_options_from_context(context),
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
            clarify_id=create_clarify_id(),
            question=f"That request is invalid for this mart: {exc.detail}",
            missing=[],
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
        "auto": "Mode is auto. Choose the best response type.",
        "chart": "Mode is chart. Return chart or clarify only.",
        "explain": "Mode is explain. Return explain only.",
    }[mode]
    return (
        "You are ContinuumAI analytics assistant for one selected mart. "
        "You can request chart execution through the preview pipeline, so do not claim data is unavailable. "
        "Never output SQL. Never fabricate numbers. Never return markdown. "
        "Clarify only when ambiguity blocks execution; ask at most one question. "
        "For clarify responses, include clarify_id, missing, and options arrays. "
        "If off-topic, return refuse. "
        f"{mode_clause} "
        "Return JSON only as one object."
    )


def _build_user_prompt(
    *,
    dataset_id: str,
    table: str,
    message: str,
    mode: ChatMode,
    context: dict[str, Any],
    state: ChatState,
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

    metrics, dimensions, temporals = _extract_fields(context)
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
            "clarify_id": "string",
            "question": "single question",
            "missing": ["metric", "dimension"],
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
        f"User message:\n{message}\n\n"
        f"Mode: {mode}\n"
        f"Dataset: {dataset_id}\n"
        f"Table: {table}\n\n"
        "Candidate fields by role:\n"
        f"- measures: {json.dumps(metrics[:25], ensure_ascii=True)}\n"
        f"- dimensions: {json.dumps(dimensions[:25], ensure_ascii=True)}\n"
        f"- temporals: {json.dumps(temporals[:25], ensure_ascii=True)}\n\n"
        f"Compact mart context: {json.dumps(context, ensure_ascii=True)}\n"
        f"KPI hints: {json.dumps(compact_kpis, ensure_ascii=True)}\n"
        f"Conversation state: {json.dumps(state.model_dump(mode='json', exclude_none=True), ensure_ascii=True)}\n\n"
        f"ChartSpec summary: {json.dumps(chartspec_summary, ensure_ascii=True)}\n"
        f"Allowed response schema: {json.dumps(response_schema, ensure_ascii=True)}\n\n"
        "Instruction: choose best available fields from context and do not copy template structures blindly."
    )


def _generate_plan(
    *,
    dataset_id: str,
    table: str,
    message: str,
    mode: ChatMode,
    context: dict[str, Any],
    state: ChatState,
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

        if not isinstance(payload, dict):
            if attempt == 0:
                corrective_prompt = "Return a single JSON object only."
                continue
            return None

        normalized_payload = _normalize_clarify_plan_payload(payload, context)
        try:
            return _PLAN_ADAPTER.validate_python(normalized_payload)
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
            clarify_id=create_clarify_id(),
            question="Which metric and breakdown should I chart?",
            missing=["metric", "dimension"],
            options=_options_from_context(context),
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
    state: ChatState | dict[str, Any] | None,
    db: Session,
    debug: bool = False,
) -> dict[str, Any]:
    if not table:
        return ChatClarifyResponse(
            response_type="clarify",
            clarify_id=create_clarify_id(),
            question="Select a mart to proceed.",
            missing=["table"],
            options=ClarifyOptions(),
            meta={},
        ).model_dump(mode="json")

    parsed_state = _parse_state(state)
    context = build_compact_mart_context(dataset_id=dataset_id, table=table)

    state_plan = _state_driven_plan(table=table, mode=mode, context=context, state=parsed_state)
    if isinstance(state_plan, ChatPlanChart):
        chart_response = _execute_chart(
            dataset_id=dataset_id,
            table=table,
            chart_spec=state_plan.chart_spec,
            db=db,
            style=state_plan.narrative_style,
            debug=debug,
        )
        return chart_response.model_dump(mode="json")
    if isinstance(state_plan, ChatPlanClarify):
        return ChatClarifyResponse(
            response_type="clarify",
            clarify_id=state_plan.clarify_id,
            question=state_plan.question,
            missing=state_plan.missing,
            options=_sanitize_options(state_plan.options, context),
            meta={},
        ).model_dump(mode="json")

    plan = _generate_plan(
        dataset_id=dataset_id,
        table=table,
        message=message,
        mode=mode,
        context=context,
        state=parsed_state,
    )
    if plan is None:
        plan = _fallback_plan_from_context(message=message, mode=mode, table=table, context=context)

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
        last_raw = parsed_state.last_chart_spec
        if not last_raw:
            return _default_clarify(
                "I need an existing chart first. What should we chart?",
                context,
                missing=["metric", "dimension"],
            ).model_dump(mode="json")
        try:
            base = last_raw if isinstance(last_raw, ChartSpecV1) else ChartSpecV1.model_validate(last_raw)
            patched = apply_patch(base, plan.patch)
        except (ValidationError, HTTPException):
            return _default_clarify(
                "I could not apply that update safely. Choose a metric or dimension.",
                context,
                missing=["metric", "dimension"],
            ).model_dump(mode="json")

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
        missing = plan.missing if plan.missing else ["metric", "dimension"]
        return ChatClarifyResponse(
            response_type="clarify",
            clarify_id=plan.clarify_id,
            question=plan.question.strip() or _question_for_missing(missing),
            missing=missing,
            options=_sanitize_options(plan.options, context),
            meta={},
        ).model_dump(mode="json")

    if isinstance(plan, ChatPlanRefuse):
        return ChatRefuseResponse(
            response_type="refuse",
            message=plan.message.strip() or "I can only help with analytics for the selected mart.",
            meta={},
        ).model_dump(mode="json")

    return _default_clarify(
        "Please rephrase your analytics request with a metric and breakdown.",
        context,
        missing=["metric", "dimension"],
    ).model_dump(mode="json")


def response_chart_spec_hash(response_payload: dict[str, Any]) -> str | None:
    raw_spec = response_payload.get("chart_spec")
    if not isinstance(raw_spec, dict):
        return None
    try:
        spec = ChartSpecV1.model_validate(raw_spec)
    except ValidationError:
        return None
    return _chart_spec_hash(spec)
