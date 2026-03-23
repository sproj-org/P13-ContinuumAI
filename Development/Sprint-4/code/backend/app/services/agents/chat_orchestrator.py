"""LLM-led single-mart chat orchestration with strict execution guardrails."""

from __future__ import annotations

import logging
import hashlib
import json
import re
from uuid import uuid4
from typing import Any, Literal

from fastapi import HTTPException
from pydantic import TypeAdapter, ValidationError
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.services.agents.chat_models import (
    ChatChartResponse,
    ChatClarifyResponse,
    ChatExplainResponse,
    ChatHistoryTurn,
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
    MissingField,
    QuerySpec,
    QuerySpecFilter,
    create_clarify_id,
)
from app.services.agents.mart_context import build_compact_mart_context
from app.services.agents.spec_patch import apply_patch
from app.services.charts.models import ChartSpecV1
from app.services.charts.spec_resolver import execute_chart_preview
from app.services.llm.openai_client import OpenAIClient, OpenAIJSONError
from app.services.llm.openai_diagnostics import (
    OpenAIDiagnostics,
    classify_openai_exception,
    log_openai_failure,
)
from app.services.strategy.kpi_registry import list_kpis
from app.services.strategy.errors import StrategyNotFoundError, StrategyValidationError
from app.services.strategy.store import get_strategy_store

_PLAN_ADAPTER = TypeAdapter(ChatPlanUnion)
logger = logging.getLogger(__name__)

_TIME_INTENT_TOKENS = [
    "trend",
    "over time",
    "time",
    "date",
    "daily",
    "weekly",
    "monthly",
    "quarterly",
    "yearly",
    "day",
    "week",
    "month",
    "quarter",
    "year",
]

_GRAIN_BY_TOKEN = {
    "daily": "day",
    "day": "day",
    "weekly": "week",
    "week": "week",
    "monthly": "month",
    "month": "month",
    "quarterly": "quarter",
    "quarter": "quarter",
    "yearly": "year",
    "year": "year",
}

_ANALYTICS_HINT_TOKENS = [
    "show",
    "chart",
    "plot",
    "trend",
    "breakdown",
    "compare",
    "top",
    "count",
    "sum",
    "average",
    "avg",
    "min",
    "max",
    "total",
    "kpi",
    "metric",
    "distribution",
    "by",
]

_OFF_TOPIC_TOKENS = ["poem", "song", "lyrics", "novel", "haiku", "joke", "recipe"]
_STOP_WORDS = {
    "show",
    "please",
    "for",
    "from",
    "with",
    "the",
    "and",
    "what",
    "how",
    "does",
    "this",
    "that",
    "about",
    "using",
    "into",
    "onto",
    "have",
    "has",
    "are",
    "was",
    "were",
    "can",
    "could",
    "should",
    "would",
    "trend",
    "performance",
}


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


def _tokenize(value: str) -> set[str]:
    tokens = re.split(r"[^a-zA-Z0-9]+", _normalize_text(value))
    return {token for token in tokens if len(token) >= 3 and not token.isdigit() and token not in _STOP_WORDS}


def _field_token_index(context: dict[str, Any]) -> set[str]:
    metrics, dimensions, temporals = _extract_fields(context)
    tokens: set[str] = set()
    for field in [*metrics, *dimensions, *temporals]:
        tokens.update(_tokenize(field))
    return tokens


def _is_obviously_off_topic(message: str) -> bool:
    text = _normalize_text(message)
    return _contains_any(text, _OFF_TOPIC_TOKENS)


def _is_probable_analytics_request(message: str, context: dict[str, Any]) -> bool:
    if _is_obviously_off_topic(message):
        return False
    text = _normalize_text(message)
    if _contains_any(text, _ANALYTICS_HINT_TOKENS):
        return True

    metrics, dimensions, temporals = _extract_fields(context)
    return bool(_pick_matching_field(message, [*metrics, *dimensions, *temporals]))


def _is_mart_mismatch_request(message: str, context: dict[str, Any]) -> bool:
    if not _is_probable_analytics_request(message, context):
        return False

    metrics, dimensions, temporals = _extract_fields(context)
    if _pick_matching_field(message, [*metrics, *dimensions, *temporals]):
        return False

    message_tokens = _tokenize(message)
    if len(message_tokens) < 2:
        return False
    return len(message_tokens.intersection(_field_token_index(context))) == 0


def _has_time_intent(message: str) -> bool:
    return _contains_any(_normalize_text(message), _TIME_INTENT_TOKENS)


def _requested_time_grain(message: str) -> str | None:
    normalized = _normalize_text(message)
    for token, grain in _GRAIN_BY_TOKEN.items():
        if token in normalized:
            return grain
    return None


def _missing_from_selections(selections: ChatSelections, *, intent_message: str) -> list[MissingField]:
    if not selections.metric:
        return ["metric"]

    if not selections.dimension and not selections.temporal:
        return ["x_axis"]

    if selections.temporal and not selections.time_grain and _requested_time_grain(intent_message):
        return ["time_grain"]
    return []


def _build_stage_options(
    stage: MissingField,
    context: dict[str, Any],
    *,
    prefer_temporal: bool = False,
    requested_grain: str | None = None,
) -> ClarifyOptions:
    metrics, dimensions, temporals = _extract_fields(context)
    if stage == "metric":
        return ClarifyOptions(metrics=metrics[:5], dimensions=[], temporals=[], time_grains=[])
    if stage == "x_axis":
        dims = dimensions[:5]
        temps = temporals[:5]
        if prefer_temporal:
            dims = dims[:3]
        else:
            temps = temps[:3]
        return ClarifyOptions(metrics=[], dimensions=dims, temporals=temps, time_grains=[])
    if stage == "time_grain":
        grains = ["day", "week", "month", "quarter", "year"]
        if requested_grain and requested_grain in grains:
            grains = [requested_grain, *[item for item in grains if item != requested_grain]]
        return ClarifyOptions(metrics=[], dimensions=[], temporals=[], time_grains=grains[:5])
    return ClarifyOptions(metrics=[], dimensions=[], temporals=[], time_grains=[])


def _sanitize_options(
    options: ClarifyOptions,
    context: dict[str, Any],
    *,
    stage: MissingField | None = None,
    prefer_temporal: bool = False,
    requested_grain: str | None = None,
) -> ClarifyOptions:
    metrics, dimensions, temporals = _extract_fields(context)
    metric_set = set(metrics)
    dimension_set = set(dimensions)
    temporal_set = set(temporals)
    clean_metrics = [item for item in options.metrics if item in metric_set][:5]
    clean_dimensions = [item for item in options.dimensions if item in dimension_set][:5]
    clean_temporals = [item for item in options.temporals if item in temporal_set][:5]
    clean_grains = [item for item in options.time_grains if item in {"day", "week", "month", "quarter", "year"}][:5]

    if stage is None:
        return ClarifyOptions(
            metrics=clean_metrics,
            dimensions=clean_dimensions,
            temporals=clean_temporals,
            time_grains=clean_grains,
        )

    fallback = _build_stage_options(
        stage,
        context,
        prefer_temporal=prefer_temporal,
        requested_grain=requested_grain,
    )
    if stage == "metric":
        return ClarifyOptions(
            metrics=clean_metrics or fallback.metrics,
            dimensions=[],
            temporals=[],
            time_grains=[],
        )
    if stage == "x_axis":
        return ClarifyOptions(
            metrics=[],
            dimensions=clean_dimensions or fallback.dimensions,
            temporals=clean_temporals or fallback.temporals,
            time_grains=[],
        )
    if stage == "time_grain":
        return ClarifyOptions(
            metrics=[],
            dimensions=[],
            temporals=[],
            time_grains=clean_grains or fallback.time_grains,
        )
    return fallback


def _question_for_stage(stage: MissingField, *, mismatch: bool = False) -> str:
    if stage == "metric":
        if mismatch:
            return "That concept is not available in this mart. Which metric should I use instead?"
        return "Which metric should I use?"
    if stage == "x_axis":
        if mismatch:
            return "That concept does not exist in this mart. What should I group or trend by?"
        return "What should I group or trend by?"
    if stage == "time_grain":
        return "Which time grain?"
    return "Select a mart to proceed."


def _default_clarify(
    question: str,
    context: dict[str, Any],
    *,
    clarify_id: str | None = None,
    missing: list[MissingField] | None = None,
    intent_message: str = "",
) -> ChatClarifyResponse:
    stage: MissingField = missing[0] if missing else "metric"
    return ChatClarifyResponse(
        response_type="clarify",
        clarify_id=clarify_id or create_clarify_id(),
        question=question or _question_for_stage(stage),
        missing=[stage],
        options=_build_stage_options(
            stage,
            context,
            prefer_temporal=_has_time_intent(intent_message),
            requested_grain=_requested_time_grain(intent_message),
        ),
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


_RESPONSE_TYPE_ALIASES = {
    "answer": "explain",
    "analysis": "explain",
    "ask": "clarify",
    "chart": "chart",
    "chart_patch": "chart_patch",
    "clarify": "clarify",
    "edit_chart": "chart_patch",
    "explain": "explain",
    "patch": "chart_patch",
    "plot": "chart",
    "question": "clarify",
    "refuse": "refuse",
    "reject": "refuse",
    "text": "explain",
    "update_chart": "chart_patch",
    "visualization": "chart",
}

_CHART_TYPE_ALIASES = {
    "area": "line",
    "column": "bar",
    "distribution": "histogram",
    "donut": "pie",
    "time_series": "line",
    "timeseries": "line",
}

_FILTER_OP_ALIASES = {
    "eq": "=",
    "equals": "=",
    "greater_than": ">",
    "greater_than_or_equal": ">=",
    "gt": ">",
    "gte": ">=",
    "in": "in",
    "less_than": "<",
    "less_than_or_equal": "<=",
    "lt": "<",
    "lte": "<=",
    "ne": "!=",
    "neq": "!=",
    "not_equals": "!=",
}

_ALLOWED_RESPONSE_TYPES = set(_RESPONSE_TYPE_ALIASES.values())
_ALLOWED_CHART_TYPES = {"bar", "line", "pie", "histogram", "kpi"}
_ALLOWED_FILTER_OPS = {"=", "!=", "in", "between", ">", ">=", "<", "<="}
_PLAN_WRAPPER_KEYS = ("response", "data", "payload", "result", "output", "content", "body")


def _first_non_empty_string(*values: Any) -> str | None:
    for value in values:
        if isinstance(value, str):
            trimmed = value.strip()
            if trimmed:
                return trimmed
    return None


def _first_present(*values: Any) -> Any | None:
    for value in values:
        if value is not None:
            return value
    return None


def _strip_json_fence(value: str) -> str:
    trimmed = value.strip()
    match = re.match(r"^```(?:json)?\s*(.*?)\s*```$", trimmed, flags=re.DOTALL | re.IGNORECASE)
    if match:
        return match.group(1).strip()
    return trimmed


def _try_parse_json_candidate(value: Any) -> Any | None:
    if not isinstance(value, str):
        return None

    candidate = _strip_json_fence(value)
    if not candidate:
        return None

    decoder = json.JSONDecoder()
    attempts = [candidate]
    first_object = min((idx for idx in (candidate.find("{"), candidate.find("[")) if idx >= 0), default=-1)
    if first_object > 0:
        attempts.append(candidate[first_object:])

    for item in attempts:
        try:
            parsed, end = decoder.raw_decode(item)
        except json.JSONDecodeError:
            continue
        if not item[end:].strip():
            return parsed
    return None


def _looks_like_plan_candidate(value: Any) -> bool:
    if isinstance(value, dict):
        if _coerce_response_type(value):
            return True
        if any(key in value for key in _PLAN_WRAPPER_KEYS):
            return True
        if len(value) == 1:
            return any(_looks_like_plan_candidate(item) for item in value.values())
        return False
    if isinstance(value, list):
        return any(_looks_like_plan_candidate(item) for item in value[:3])
    if isinstance(value, str):
        parsed = _try_parse_json_candidate(value)
        return _looks_like_plan_candidate(parsed) if parsed is not None else False
    return False


def _merge_wrapped_payload(container: dict[str, Any], key: str, wrapped_value: Any) -> Any:
    if not isinstance(wrapped_value, dict):
        return wrapped_value
    passthrough = {name: value for name, value in container.items() if name != key}
    return {**passthrough, **wrapped_value}


def _coerce_payload_object(raw_payload: Any) -> tuple[dict[str, Any] | None, list[str]]:
    current = raw_payload
    trace: list[str] = []

    for _ in range(8):
        if isinstance(current, str):
            parsed = _try_parse_json_candidate(current)
            if parsed is None:
                break
            trace.append("parsed JSON from text")
            current = parsed
            continue

        if isinstance(current, list):
            if not current:
                break
            candidate = next((item for item in current if _looks_like_plan_candidate(item)), current[0])
            trace.append("selected payload from array")
            current = candidate
            continue

        if isinstance(current, dict):
            wrapper_key = next(
                (
                    key
                    for key in _PLAN_WRAPPER_KEYS
                    if key in current and _looks_like_plan_candidate(current.get(key))
                ),
                None,
            )
            if wrapper_key is None and len(current) == 1:
                only_key, only_value = next(iter(current.items()))
                if _looks_like_plan_candidate(only_value):
                    wrapper_key = only_key
            if wrapper_key is None:
                break
            trace.append(f"unwrapped {wrapper_key}")
            current = _merge_wrapped_payload(current, wrapper_key, current.get(wrapper_key))
            continue

        break

    if isinstance(current, dict):
        return dict(current), trace
    return None, trace


def _normalize_string_options(value: Any) -> list[str]:
    raw_items = value if isinstance(value, list) else [value]
    output: list[str] = []
    for item in raw_items:
        resolved = None
        if isinstance(item, str):
            resolved = item.strip()
        elif isinstance(item, dict):
            resolved = _first_non_empty_string(
                item.get("value"),
                item.get("label"),
                item.get("name"),
                item.get("field"),
                item.get("id"),
            )
        if resolved and resolved not in output:
            output.append(resolved)
    return output


def _normalize_time_grain_options(value: Any) -> list[TimeGrain]:
    raw_items = _normalize_string_options(value)
    output: list[TimeGrain] = []
    for item in raw_items:
        normalized = _GRAIN_BY_TOKEN.get(item.strip().lower())
        if normalized and normalized not in output:
            output.append(normalized)  # type: ignore[arg-type]
    return output


def _coerce_response_type(payload: dict[str, Any]) -> str | None:
    raw = _first_non_empty_string(
        payload.get("response_type"),
        payload.get("responseType"),
        payload.get("type"),
        payload.get("kind"),
        payload.get("action"),
        payload.get("mode"),
        payload.get("responseKind"),
    )
    if raw:
        normalized = _RESPONSE_TYPE_ALIASES.get(_normalize_text(raw).replace(" ", "_"))
        if normalized in _ALLOWED_RESPONSE_TYPES:
            return normalized

    if any(
        key in payload
        for key in (
            "chart_spec",
            "chartSpec",
            "encoding",
            "x",
            "y",
            "chart",
            "metric",
            "measure",
            "metrics",
            "measures",
            "group_by",
            "groupBy",
            "dimension",
            "query_spec",
            "querySpec",
        )
    ):
        return "chart"
    if any(key in payload for key in ("patch", "chart_patch", "changes", "set", "unset", "add", "operations", "ops", "edits")):
        return "chart_patch"
    if any(
        key in payload
        for key in ("question", "missing", "options", "stage", "needs", "prompt", "follow_up", "followUp", "questions", "choices", "candidates")
    ):
        return "clarify"
    if payload.get("refusal") or payload.get("safe_alternative") or payload.get("safeAlternative") or payload.get("refusal_message"):
        return "refuse"
    if _first_non_empty_string(
        payload.get("message"),
        payload.get("answer"),
        payload.get("text"),
        payload.get("narrative"),
        payload.get("explanation"),
        payload.get("summary"),
        payload.get("analysis"),
    ):
        return "explain"
    return None


def _normalize_chart_type(value: Any, *, default: str = "bar") -> str:
    if not isinstance(value, str):
        return default
    normalized = _normalize_text(value).replace(" ", "_")
    normalized = _CHART_TYPE_ALIASES.get(normalized, normalized)
    if normalized in _ALLOWED_CHART_TYPES:
        return normalized
    return default


def _normalize_filter_operator(value: Any) -> str:
    if not isinstance(value, str):
        return "="
    normalized = _normalize_text(value).replace(" ", "_")
    mapped = _FILTER_OP_ALIASES.get(normalized, value.strip())
    if mapped in _ALLOWED_FILTER_OPS:
        return mapped
    return "="


def _normalize_sort_direction(value: Any) -> str:
    if not isinstance(value, str):
        return "desc"
    normalized = _normalize_text(value)
    if normalized in {"ascending", "asc"}:
        return "asc"
    if normalized in {"descending", "desc"}:
        return "desc"
    return "desc"


def _normalize_chart_spec_payload(
    raw_spec: Any,
    *,
    dataset_id: str,
    table: str,
) -> dict[str, Any]:
    candidate, _ = _coerce_payload_object(raw_spec)
    if candidate is None and isinstance(raw_spec, dict):
        candidate = raw_spec
    candidate = candidate or {}
    normalized = dict(candidate)

    nested_chart_spec = _first_present(normalized.get("chart_spec"), normalized.get("chartSpec"))
    if isinstance(nested_chart_spec, dict):
        normalized = {**normalized, **nested_chart_spec}

    query_spec = _first_present(normalized.get("query_spec"), normalized.get("querySpec"))
    if isinstance(query_spec, dict):
        if normalized.get("chart_type") is None:
            normalized["chart_type"] = _first_present(query_spec.get("chart_type"), query_spec.get("chartType"))
        if normalized.get("group_by") is None and normalized.get("x") is None:
            normalized["group_by"] = _first_present(
                query_spec.get("time_field"),
                query_spec.get("timeField"),
                query_spec.get("dimensions", [None])[0] if isinstance(query_spec.get("dimensions"), list) else None,
            )
        if normalized.get("metric") is None and normalized.get("y") is None:
            normalized["metric"] = (
                query_spec.get("measures", [None])[0] if isinstance(query_spec.get("measures"), list) else None
            )
        if normalized.get("aggregation") is None:
            normalized["aggregation"] = query_spec.get("aggregation")
        if normalized.get("filters") is None:
            normalized["filters"] = query_spec.get("filters")
        if normalized.get("sort") is None:
            normalized["sort"] = query_spec.get("sort")
        if normalized.get("limit") is None:
            normalized["limit"] = query_spec.get("limit")

    chart_block = normalized.get("chart")
    if isinstance(chart_block, dict):
        if normalized.get("encoding") is None and isinstance(chart_block.get("encoding"), dict):
            normalized["encoding"] = chart_block.get("encoding")
        if normalized.get("x") is None:
            normalized["x"] = chart_block.get("x")
        if normalized.get("y") is None:
            normalized["y"] = chart_block.get("y")
    chart_type = _first_non_empty_string(
        chart_block.get("type") if isinstance(chart_block, dict) else None,
        chart_block.get("chart_type") if isinstance(chart_block, dict) else None,
        chart_block if isinstance(chart_block, str) else None,
        normalized.get("chart_type"),
        normalized.get("chartType"),
        normalized.get("visualization"),
        normalized.get("visualization_type"),
        normalized.get("visualizationType"),
        normalized.get("mark"),
        normalized.get("type") if normalized.get("type") != "chart" else None,
    )
    normalized["chart"] = {"type": _normalize_chart_type(chart_type)}

    encoding = normalized.get("encoding")
    encoding = dict(encoding) if isinstance(encoding, dict) else {}

    x_candidate = encoding.get("x", normalized.get("x"))
    if x_candidate is None:
        x_candidate = (
            normalized.get("x_axis")
            or normalized.get("xAxis")
            or normalized.get("group_by")
            or normalized.get("groupBy")
            or normalized.get("dimension")
            or normalized.get("category")
            or normalized.get("time_field")
            or normalized.get("timeField")
        )
    if isinstance(x_candidate, list):
        x_candidate = x_candidate[0] if x_candidate else None
    if isinstance(x_candidate, str):
        x_payload: dict[str, Any] = {"field": x_candidate}
    elif isinstance(x_candidate, dict):
        x_payload = {
            "field": _first_non_empty_string(
                x_candidate.get("field"),
                x_candidate.get("name"),
                x_candidate.get("column"),
                x_candidate.get("dimension"),
                x_candidate.get("value"),
            )
        }
    else:
        x_payload = {}

    y_candidate = encoding.get("y", normalized.get("y"))
    if y_candidate is None:
        y_candidate = (
            normalized.get("measure")
            or normalized.get("metric")
            or normalized.get("metrics")
            or normalized.get("measures")
            or normalized.get("values")
            or normalized.get("y_axis")
            or normalized.get("yAxis")
        )

    def _normalize_y_item(item: Any) -> dict[str, Any]:
        if isinstance(item, str):
            return {
                "field": item,
                "aggregation": _first_non_empty_string(normalized.get("aggregation"), normalized.get("agg"), "sum"),
            }
        if isinstance(item, dict):
            return {
                "field": _first_non_empty_string(
                    item.get("field"),
                    item.get("column"),
                    item.get("name"),
                    item.get("metric"),
                    item.get("measure"),
                ),
                "aggregation": _first_non_empty_string(item.get("aggregation"), item.get("agg"), normalized.get("aggregation"), "sum"),
                "alias": _first_non_empty_string(item.get("alias"), item.get("label"), item.get("name")),
            }
        return {}

    if isinstance(y_candidate, list):
        y_payload = [_normalize_y_item(item) for item in y_candidate[:1]]
    else:
        y_payload = [_normalize_y_item(y_candidate)]

    filters_raw = _first_present(normalized.get("filters"), normalized.get("where"), query_spec.get("filters") if isinstance(query_spec, dict) else None)
    if isinstance(filters_raw, dict):
        if any(key in filters_raw for key in ("field", "column", "name")):
            filters_raw = [filters_raw]
        else:
            filters_raw = [{"field": field, "value": value} for field, value in filters_raw.items()]
    filters: list[dict[str, Any]] = []
    if isinstance(filters_raw, list):
        for item in filters_raw:
            if not isinstance(item, dict):
                continue
            field = _first_non_empty_string(item.get("field"), item.get("column"), item.get("name"))
            if not field:
                continue
            filter_value = item.get("value")
            if filter_value is None:
                filter_value = _first_present(item.get("values"), item.get("range"), item.get("selected"))
            filters.append(
                {
                    "field": field,
                    "op": _normalize_filter_operator(_first_present(item.get("op"), item.get("operator"))),
                    "value": filter_value,
                }
            )

    sort_raw = _first_present(
        normalized.get("sort"),
        normalized.get("order_by"),
        normalized.get("orderBy"),
        query_spec.get("sort") if isinstance(query_spec, dict) else None,
    )
    if isinstance(sort_raw, dict):
        if any(key in sort_raw for key in ("field", "column", "name")):
            sort_raw = [sort_raw]
        else:
            sort_raw = [
                {"field": field, "direction": direction}
                for field, direction in sort_raw.items()
                if isinstance(direction, str)
            ]
    elif isinstance(sort_raw, str):
        sort_raw = [{"field": sort_raw, "direction": _first_present(normalized.get("sort_direction"), normalized.get("direction"), "desc")}]
    sort: list[dict[str, Any]] = []
    if isinstance(sort_raw, list):
        for item in sort_raw:
            if isinstance(item, str):
                sort.append({"field": item, "direction": "desc"})
                continue
            if not isinstance(item, dict):
                continue
            field = _first_non_empty_string(item.get("field"), item.get("column"), item.get("name"))
            if not field:
                continue
            sort.append(
                {
                    "field": field,
                    "direction": _normalize_sort_direction(_first_present(item.get("direction"), item.get("order"))),
                }
            )

    limit_value = _first_present(normalized.get("limit"), normalized.get("top_n"), normalized.get("topN"), normalized.get("row_limit"))
    if isinstance(limit_value, str):
        try:
            limit_value = int(limit_value)
        except ValueError:
            limit_value = 20
    if not isinstance(limit_value, int) or limit_value < 1:
        limit_value = 20

    return {
        "version": "v1",
        "dataset_id": dataset_id,
        "table": table,
        "chart": normalized["chart"],
        "encoding": {"x": x_payload, "y": y_payload},
        "filters": filters,
        "sort": sort,
        "limit": limit_value,
    }


def _normalize_chart_patch_payload(payload: dict[str, Any]) -> dict[str, Any]:
    normalized = dict(payload)
    patch_payload = normalized.get("patch")
    if not isinstance(patch_payload, dict):
        patch_payload = normalized.get("chart_patch")
    if not isinstance(patch_payload, dict):
        patch_payload = normalized.get("changes")
    if not isinstance(patch_payload, dict):
        patch_payload = normalized.get("edits")
    if not isinstance(patch_payload, dict):
        patch_payload = normalized.get("ops")
    if not isinstance(patch_payload, dict):
        operations = normalized.get("operations")
        if isinstance(operations, list):
            set_payload: dict[str, Any] = {}
            unset_payload: list[str] = []
            add_payload: dict[str, Any] = {}
            for item in operations:
                if not isinstance(item, dict):
                    continue
                operation = _normalize_text(_first_non_empty_string(item.get("op"), item.get("action"), item.get("type")) or "")
                path = _first_non_empty_string(item.get("path"), item.get("target"), item.get("field"), item.get("key"))
                if not operation or not path:
                    continue
                if operation in {"set", "replace", "update"}:
                    set_payload[path] = item.get("value")
                elif operation in {"unset", "remove", "delete"}:
                    unset_payload.append(path)
                elif operation in {"add", "append", "push"}:
                    add_payload[path] = item.get("value")
            if set_payload or unset_payload or add_payload:
                patch_payload = {
                    "set": set_payload,
                    "unset": unset_payload,
                    "add": add_payload,
                }
    if not isinstance(patch_payload, dict) and any(key in normalized for key in ("set", "unset", "add")):
        patch_payload = normalized
    if not isinstance(patch_payload, dict):
        patch_payload = {}

    if not any(key in patch_payload for key in ("set", "unset", "add")):
        patch_payload = {"set": patch_payload, "unset": [], "add": {}}

    unset_raw = patch_payload.get("unset")
    if isinstance(unset_raw, str):
        unset = [unset_raw]
    elif isinstance(unset_raw, list):
        unset = [item for item in unset_raw if isinstance(item, str)]
    else:
        unset = []

    normalized["patch"] = {
        "set": patch_payload.get("set") if isinstance(patch_payload.get("set"), dict) else {},
        "unset": unset,
        "add": patch_payload.get("add") if isinstance(patch_payload.get("add"), dict) else {},
    }
    return normalized


def _normalize_missing_fields(value: Any, *, fallback: MissingField = "metric") -> list[MissingField]:
    raw_items = value if isinstance(value, list) else [value]
    output: list[MissingField] = []
    legacy_map = {"dimension": "x_axis", "temporal": "x_axis"}
    for item in raw_items:
        if not isinstance(item, str):
            continue
        normalized = legacy_map.get(item.strip().lower(), item.strip().lower())
        if normalized in {"metric", "x_axis", "time_grain", "table"} and normalized not in output:
            output.append(normalized)  # type: ignore[arg-type]
    return output or [fallback]


def _normalize_clarify_plan_payload(payload: dict[str, Any], context: dict[str, Any], *, message: str) -> dict[str, Any]:
    response_type = payload.get("response_type")
    if response_type != "clarify":
        return payload

    normalized = dict(payload)
    clarify_id = normalized.get("clarify_id")
    if not isinstance(clarify_id, str) or not clarify_id.strip():
        normalized["clarify_id"] = create_clarify_id()

    fallback_stage = "metric"
    stage_hint = _first_non_empty_string(normalized.get("stage"), normalized.get("missing_field"), normalized.get("needs"))
    if stage_hint:
        fallback_stage = _normalize_missing_fields(stage_hint)[0]
    normalized["missing"] = _normalize_missing_fields(normalized.get("missing"), fallback=fallback_stage)
    stage = normalized["missing"][0]

    options = normalized.get("options")
    question = _first_non_empty_string(
        normalized.get("question"),
        normalized.get("message"),
        normalized.get("prompt"),
        normalized.get("follow_up"),
        normalized.get("followUp"),
        normalized.get("clarification"),
        normalized.get("questions", [None])[0] if isinstance(normalized.get("questions"), list) else None,
    )
    normalized["question"] = question or _question_for_stage(stage)
    option_payload = dict(options) if isinstance(options, dict) else {}
    fallback_option_values = _normalize_string_options(
        _first_present(
            option_payload.get("choices"),
            option_payload.get("candidates"),
            option_payload.get("options"),
            options,
            normalized.get("choices"),
            normalized.get("candidates"),
        )
    )
    if not option_payload:
        option_payload = {
            "metrics": _first_present(normalized.get("metrics"), normalized.get("measures")),
            "dimensions": normalized.get("dimensions"),
            "temporals": _first_present(normalized.get("temporals"), normalized.get("time_fields"), normalized.get("temporals")),
            "time_grains": _first_present(normalized.get("time_grains"), normalized.get("grains")),
        }
    normalized_options = {
        "metrics": _normalize_string_options(_first_present(option_payload.get("metrics"), option_payload.get("measures"))),
        "dimensions": _normalize_string_options(option_payload.get("dimensions")),
        "temporals": _normalize_string_options(
            _first_present(option_payload.get("temporals"), option_payload.get("time_fields"), option_payload.get("temporal_fields"))
        ),
        "time_grains": _normalize_time_grain_options(_first_present(option_payload.get("time_grains"), option_payload.get("grains"))),
    }
    if stage == "metric" and not normalized_options["metrics"]:
        normalized_options["metrics"] = fallback_option_values
    if stage == "x_axis":
        if not normalized_options["dimensions"]:
            normalized_options["dimensions"] = fallback_option_values
        if not normalized_options["temporals"]:
            normalized_options["temporals"] = fallback_option_values
    if stage == "time_grain" and not normalized_options["time_grains"]:
        normalized_options["time_grains"] = _normalize_time_grain_options(fallback_option_values)
    try:
        parsed_options = ClarifyOptions.model_validate(normalized_options)
    except ValidationError:
        parsed_options = ClarifyOptions()
    normalized["options"] = _sanitize_options(
        parsed_options,
        context,
        stage=stage,
        prefer_temporal=_has_time_intent(message),
        requested_grain=_requested_time_grain(message),
    ).model_dump(mode="json")
    return normalized


def _normalize_plan_payload(
    payload: Any,
    context: dict[str, Any],
    *,
    dataset_id: str,
    table: str,
    message: str,
) -> tuple[dict[str, Any] | None, list[str]]:
    normalized, trace = _coerce_payload_object(payload)
    if normalized is None and isinstance(payload, dict):
        normalized = dict(payload)
    if normalized is None:
        return None, trace

    response_type = _coerce_response_type(normalized)
    if response_type:
        normalized["response_type"] = response_type

    if response_type == "chart":
        raw_spec = normalized.get("chart_spec")
        if not isinstance(raw_spec, dict):
            raw_spec = normalized.get("chartSpec")
        if not isinstance(raw_spec, dict):
            raw_spec = normalized
        normalized["chart_spec"] = _normalize_chart_spec_payload(raw_spec, dataset_id=dataset_id, table=table)
        style = _first_non_empty_string(normalized.get("narrative_style"), normalized.get("style"))
        if style in {"brief", "standard"}:
            normalized["narrative_style"] = style
        return normalized, trace

    if response_type == "chart_patch":
        return _normalize_chart_patch_payload(normalized), trace

    if response_type == "explain":
        normalized["message"] = _first_non_empty_string(
            normalized.get("message"),
            normalized.get("answer"),
            normalized.get("text"),
            normalized.get("narrative"),
            normalized.get("explanation"),
            normalized.get("summary"),
            normalized.get("analysis"),
        )
        optional_chart_spec = normalized.get("optional_chart_spec")
        if not isinstance(optional_chart_spec, dict):
            optional_chart_spec = normalized.get("optionalChartSpec")
        if not isinstance(optional_chart_spec, dict):
            optional_chart_spec = normalized.get("chart_spec")
        if isinstance(optional_chart_spec, dict):
            normalized["optional_chart_spec"] = _normalize_chart_spec_payload(
                optional_chart_spec,
                dataset_id=dataset_id,
                table=table,
            )
        return normalized, trace

    if response_type == "refuse":
        normalized["message"] = _first_non_empty_string(
            normalized.get("message"),
            normalized.get("answer"),
            normalized.get("text"),
            normalized.get("reason"),
            normalized.get("refusal"),
            normalized.get("refusal_message"),
            normalized.get("safe_alternative"),
            normalized.get("safeAlternative"),
        )
        return normalized, trace

    if response_type == "clarify":
        return _normalize_clarify_plan_payload(normalized, context, message=message), trace

    return normalized, trace


def _summarize_plan_validation_error(exc: ValidationError, *, recovery_trace: list[str] | None = None) -> str:
    fragments: list[str] = []
    for error in exc.errors()[:3]:
        loc = ".".join(str(item) for item in error.get("loc", ()))
        message = str(error.get("msg") or "invalid value")
        fragments.append(f"{loc}: {message}" if loc else message)
    base = "Schema mismatch: " + "; ".join(fragments) if fragments else "OpenAI response schema mismatch"
    if recovery_trace:
        return f"{base} (recovery: {' -> '.join(recovery_trace[:3])})"
    return base


def _state_driven_plan(
    *,
    table: str,
    mode: ChatMode,
    context: dict[str, Any],
    state: ChatState,
    message: str,
) -> ChatPlanUnion | None:
    intent_message = state.original_user_intent or message
    selections = _sanitize_selections(context, state.selections)
    has_selection = bool(selections.metric or selections.dimension or selections.temporal or selections.time_grain)
    if not state.clarify_id and not has_selection:
        return None

    missing = _missing_from_selections(selections, intent_message=intent_message)
    if missing:
        stage = missing[0]
        return ChatPlanClarify(
            response_type="clarify",
            clarify_id=state.clarify_id or create_clarify_id(),
            question=_question_for_stage(stage),
            missing=[stage],
            options=_build_stage_options(
                stage,
                context,
                prefer_temporal=_has_time_intent(intent_message),
                requested_grain=_requested_time_grain(intent_message),
            ),
        )

    x_field = selections.temporal or selections.dimension
    if not x_field or not selections.metric:
        return ChatPlanClarify(
            response_type="clarify",
            clarify_id=state.clarify_id or create_clarify_id(),
            question=_question_for_stage("metric"),
            missing=["metric"],
            options=_build_stage_options("metric", context),
        )

    metrics, _, temporals = _extract_fields(context)
    if selections.metric not in set(metrics):
        return ChatPlanClarify(
            response_type="clarify",
            clarify_id=state.clarify_id or create_clarify_id(),
            question=_question_for_stage("metric", mismatch=True),
            missing=["metric"],
            options=_build_stage_options("metric", context),
        )

    chart_type = _recommended_chart_type(intent_message, x_field=x_field, temporals=temporals)
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
                        "aggregation": selections.aggregation or _aggregation_from_message(intent_message),
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


def _recommended_chart_type(message: str, *, x_field: str, temporals: list[str]) -> str:
    normalized = _normalize_text(message)
    if x_field in set(temporals):
        return "line"
    if _contains_any(normalized, ["share", "composition", "mix", "split", "contribution", "portion"]):
        return "pie"
    return "bar"


def _suggest_alternative_questions(context: dict[str, Any]) -> list[str]:
    metrics, dimensions, temporals = _extract_fields(context)
    suggestions: list[str] = []
    if metrics and dimensions:
        suggestions.append(f"Show {metrics[0]} by {dimensions[0]}")
    if metrics and temporals:
        suggestions.append(f"Trend of {metrics[0]} by {temporals[0]}")
    if len(metrics) > 1 and dimensions:
        suggestions.append(f"Compare {metrics[1]} across {dimensions[0]}")
    return suggestions[:3]


def _fallback_plan_from_context(
    *,
    message: str,
    mode: ChatMode,
    table: str,
    context: dict[str, Any],
) -> ChatPlanUnion:
    if mode == "explain":
        return ChatPlanExplain(
            response_type="explain",
            message=_context_explain_message(context=context, table=table, user_message=message),
        )

    if _is_obviously_off_topic(message):
        return ChatPlanRefuse(
            response_type="refuse",
            message="I can help with analytics for the selected mart. Ask about metrics, trends, filters, or breakdowns.",
        )

    if mode == "auto" and _contains_any(_normalize_text(message), ["explain", "what is", "what does", "why"]):
        return ChatPlanExplain(
            response_type="explain",
            message=_context_explain_message(context=context, table=table, user_message=message),
        )

    if _is_mart_mismatch_request(message, context):
        alternatives = _suggest_alternative_questions(context)
        suggestions = " "
        if alternatives:
            suggestions = " Try one of these: " + " | ".join(alternatives) + "."
        return ChatPlanClarify(
            response_type="clarify",
            clarify_id=create_clarify_id(),
            question=(
                "That concept is not represented in this mart. "
                "Would you like to use one of the available metrics instead?"
                f"{suggestions}"
            ),
            missing=["metric"],
            options=_build_stage_options("metric", context),
        )

    metrics, dimensions, temporals = _extract_fields(context)
    metric = _pick_matching_field(message, metrics)
    x_field = _pick_matching_field(message, [*dimensions, *temporals])
    time_intent = _has_time_intent(message)
    analytics_request = _is_probable_analytics_request(message, context)

    if not analytics_request:
        return ChatPlanClarify(
            response_type="clarify",
            clarify_id=create_clarify_id(),
            question="What business metric should I analyze?",
            missing=["metric"],
            options=_build_stage_options("metric", context),
        )

    if not metric and metrics:
        metric = metrics[0]

    if not x_field:
        if time_intent and temporals:
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
                chart={"type": _recommended_chart_type(message, x_field=x_field, temporals=temporals)},
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

    if not metrics:
        return ChatPlanClarify(
            response_type="clarify",
            clarify_id=create_clarify_id(),
            question="This mart has no usable measure fields for charting. What else would you like to explore?",
            missing=["metric"],
            options=_build_stage_options("metric", context),
        )

    if not (dimensions or temporals):
        return ChatPlanClarify(
            response_type="clarify",
            clarify_id=create_clarify_id(),
            question="This mart has no usable grouping fields. What metric should I summarize instead?",
            missing=["metric"],
            options=_build_stage_options("metric", context),
        )

    return ChatPlanClarify(
        response_type="clarify",
        clarify_id=create_clarify_id(),
        question=_question_for_stage("x_axis"),
        missing=["x_axis"],
        options=_build_stage_options("x_axis", context, prefer_temporal=time_intent),
    )


def _coerce_chart_spec(dataset_id: str, table: str, candidate: ChartSpecV1) -> ChartSpecV1:
    return candidate.model_copy(
        update={
            "version": "v1",
            "dataset_id": dataset_id,
            "table": table,
        }
    )


def _query_spec_from_chart_spec(
    *,
    dataset_id: str,
    chart_spec: ChartSpecV1,
    context: dict[str, Any],
    intent_message: str,
) -> QuerySpec:
    _, _, temporals = _extract_fields(context)
    x_field = chart_spec.encoding.x.field
    y_metric = chart_spec.encoding.y[0]
    time_field = x_field if x_field in set(temporals) else None
    dimensions: list[str] = []
    if chart_spec.chart.type != "histogram" and x_field not in dimensions:
        dimensions.append(x_field)
    elif chart_spec.chart.type == "histogram" and time_field is not None:
        dimensions.append(x_field)

    return QuerySpec(
        dataset_id=dataset_id,
        table=chart_spec.table,
        chart_type=chart_spec.chart.type,
        measures=[y_metric.field],
        dimensions=dimensions,
        time_field=time_field,
        aggregation=y_metric.aggregation,
        time_grain=_requested_time_grain(intent_message) if time_field else None,
        filters=[
            QuerySpecFilter(field=item.field, op=item.op, value=item.value)
            for item in (chart_spec.filters or [])
        ],
        limit=chart_spec.limit,
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
    metric_name = str(metric_info.get("field", metric_output))
    metric_aggregation = str(metric_info.get("aggregation", "value"))

    if chart_spec.chart.type == "histogram":
        values = [
            float(row[metric_output])
            for row in rows
            if isinstance(row, dict) and row.get(metric_output) is not None
        ]
        if not values:
            return f"No numeric values were available to plot the distribution of {metric_name}."
        sample_size = len(values)
        lower = min(values)
        upper = max(values)
        if style == "brief":
            return f"Distribution of {metric_name} across {sample_size} filtered records. Range {lower:,.2f} to {upper:,.2f}."
        return (
            f"Built a histogram for {metric_name} using {sample_size} filtered records. "
            f"Observed range: {lower:,.2f} to {upper:,.2f}."
        )

    metric_label = f"{metric_aggregation}({metric_name})"

    top_row = rows[0]
    top_x = top_row.get(x_field)
    top_metric = top_row.get(metric_output)
    if style == "brief":
        return f"Top {x_field}: '{top_x}' with {metric_label}={_format_metric_value(top_metric)}."
    return (
        f"Computed {len(rows)} grouped rows. "
        f"Top {x_field} is '{top_x}' with {metric_label} = {_format_metric_value(top_metric)}."
    )


def _next_stage_from_invalid_chart(chart_spec: ChartSpecV1, context: dict[str, Any], *, intent_message: str) -> MissingField:
    metrics, dimensions, temporals = _extract_fields(context)
    metric_set = set(metrics)
    x_set = set([*dimensions, *temporals])
    y_field = chart_spec.encoding.y[0].field
    x_field = chart_spec.encoding.x.field
    if y_field not in metric_set:
        return "metric"
    if x_field not in x_set:
        return "x_axis"
    if x_field in set(temporals) and _requested_time_grain(intent_message):
        return "time_grain"
    return "x_axis"


def _execute_chart(
    *,
    dataset_id: str,
    table: str,
    chart_spec: ChartSpecV1,
    db: Session,
    context: dict[str, Any],
    intent_message: str,
    style: str = "standard",
    debug: bool = False,
) -> ChatChartResponse | ChatClarifyResponse:
    normalized = _coerce_chart_spec(dataset_id=dataset_id, table=table, candidate=chart_spec)
    try:
        try:
            preview_payload = execute_chart_preview(dataset_id=dataset_id, chart_spec=normalized, db=db, debug=debug)
        except TypeError:
            preview_payload = execute_chart_preview(dataset_id=dataset_id, chart_spec=normalized, db=db)
    except HTTPException:
        stage = _next_stage_from_invalid_chart(normalized, context, intent_message=intent_message)
        return ChatClarifyResponse(
            response_type="clarify",
            clarify_id=create_clarify_id(),
            question=_question_for_stage(stage, mismatch=True),
            missing=[stage],
            options=_build_stage_options(
                stage,
                context,
                prefer_temporal=_has_time_intent(intent_message),
                requested_grain=_requested_time_grain(intent_message),
            ),
            meta={},
        )

    return ChatChartResponse(
        response_type="chart",
        chart_spec=normalized,
        columns=list(preview_payload.get("columns", [])),
        rows=list(preview_payload.get("rows", [])),
        narrative=_chart_narrative(normalized, preview_payload, style=style),
        meta=dict(preview_payload.get("meta", {})),
        query_spec=_query_spec_from_chart_spec(
            dataset_id=dataset_id,
            chart_spec=normalized,
            context=context,
            intent_message=intent_message,
        ),
    )


def _load_strategy_runtime(dataset_id: str) -> tuple[dict[str, Any], str | None, str | None]:
    store = get_strategy_store()
    try:
        digest = store.get_digest(dataset_id)
        strategy_hash = store.strategy_hash(dataset_id)
        return digest, strategy_hash, None
    except StrategyNotFoundError:
        return {"status": "missing"}, None, "No strategy layer configured for this dataset."
    except StrategyValidationError:
        return {"status": "invalid"}, None, "No strategy layer configured for this dataset."


def _infer_strategy_pillars_used(message: str, strategy_digest: dict[str, Any]) -> list[str]:
    normalized_message = _normalize_text(message)
    pillars = strategy_digest.get("pillars", [])
    if not isinstance(pillars, list):
        return []

    used: list[str] = []
    for item in pillars:
        if not isinstance(item, dict):
            continue
        pillar_id = item.get("id")
        pillar_name = item.get("name")
        if not isinstance(pillar_id, str) or not pillar_id.strip():
            continue
        if isinstance(pillar_name, str) and _normalize_text(pillar_name) in normalized_message:
            used.append(pillar_id)
            continue
        if _normalize_text(pillar_id) in normalized_message:
            used.append(pillar_id)
    return used


def _with_strategy_meta(
    payload: dict[str, Any],
    *,
    strategy_hash: str | None,
    strategy_pillars_used: list[str],
) -> dict[str, Any]:
    out = dict(payload)
    meta = out.get("meta")
    if not isinstance(meta, dict):
        meta = {}
    meta["strategy_hash"] = strategy_hash
    if strategy_pillars_used:
        meta["strategy_pillars_used"] = strategy_pillars_used
    out["meta"] = meta
    return out


def _with_chat_debug_meta(
    payload: dict[str, Any],
    *,
    used_fallback: bool,
    openai_configured: bool,
    fallback_reason: Literal["missing_key", "openai_error"] | None = None,
    openai_error_type: str | None = None,
    openai_status_code: int | None = None,
    openai_error_hint: str | None = None,
) -> dict[str, Any]:
    out = dict(payload)
    out["used_fallback"] = used_fallback
    out["openai_configured"] = openai_configured
    if used_fallback and fallback_reason:
        out["fallback_reason"] = fallback_reason
    if used_fallback and fallback_reason == "openai_error":
        out["openai_error_type"] = openai_error_type or "unknown"
        out["openai_status_code"] = openai_status_code
        out["openai_error_hint"] = openai_error_hint
    return out


def _log_chat_fallback(
    *,
    fallback_reason: Literal["missing_key", "openai_error"],
    exception_class_name: str | None,
) -> None:
    correlation_id = uuid4().hex[:12]
    logger.warning(
        "chat_fallback correlation_id=%s fallback_reason=%s exception_class=%s",
        correlation_id,
        fallback_reason,
        exception_class_name or "-",
    )


def _ensure_strategy_alignment_text(message: str, strategy_digest: dict[str, Any]) -> str:
    north_star = strategy_digest.get("north_star", {})
    north_star_name = north_star.get("name") if isinstance(north_star, dict) else None
    if not isinstance(north_star_name, str) or not north_star_name.strip():
        return message

    normalized_message = _normalize_text(message)
    if _normalize_text(north_star_name) in normalized_message:
        return message

    pillar_names: list[str] = []
    pillars = strategy_digest.get("pillars", [])
    if isinstance(pillars, list):
        for item in pillars:
            if isinstance(item, dict) and isinstance(item.get("name"), str) and item["name"].strip():
                pillar_names.append(item["name"])
            if len(pillar_names) >= 3:
                break

    suffix = f" Strategy north star: {north_star_name}."
    if pillar_names:
        suffix += f" Supporting pillars: {', '.join(pillar_names)}."
    return f"{message.rstrip()} {suffix}".strip()


def _build_system_prompt(mode: ChatMode, *, strategy_digest: dict[str, Any], strategy_notice: str | None) -> str:
    mode_clause = {
        "auto": "Mode is auto. Choose chart, explain, clarify, or refuse based on user intent.",
        "chart": "Mode is chart. Return chart when possible; use clarify only if execution is blocked.",
        "explain": "Mode is explain. Return explain only.",
    }[mode]
    strategy_section = json.dumps(strategy_digest, ensure_ascii=True)
    strategy_notice_line = strategy_notice or "Strategy layer loaded."
    return (
        "You are ContinuumAI analytics assistant for one selected mart. "
        "You can request chart execution through the preview pipeline, so do not claim data is unavailable. "
        "Never output SQL. Never fabricate numbers. Never return markdown. "
        "Prefer returning a chart for reasonable analytics prompts even if details are omitted. "
        "Clarify only when ambiguity truly blocks execution. "
        "When clarifying, ask one short question and provide only stage-relevant options for metric, x_axis, or time_grain. "
        "If request is not expressible for this mart, return clarify with one-sentence mismatch guidance and 2-3 alternative questions using available fields. "
        "Align recommendations and explanations with strategy north star and pillars when relevant. "
        "Prefer KPI names from strategy; map business terms to closest KPI names when possible. "
        "If a request conflicts with strategy decision rules, do not execute unsafe guidance directly; return explain or clarify with safer alternatives. "
        "Refuse only when the request is truly non-analytics. "
        "Do NOT repeatedly ask for the same missing info after the user has selected it. Converge within 1 clarify round whenever possible. "
        f"STRATEGY LAYER (authoritative): {strategy_section}. "
        f"Strategy status: {strategy_notice_line} "
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
    history: list[ChatHistoryTurn] | None,
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
            "message": "plain-language answer specific to the user question",
            "optional_chart_spec": "ChartSpecV1 | omitted",
        },
        "clarify": {
            "response_type": "clarify",
            "clarify_id": "string",
            "question": "single short question",
            "missing": ["metric|x_axis|time_grain"],
            "options": {"metrics": [], "dimensions": [], "temporals": [], "time_grains": []},
        },
        "refuse": {"response_type": "refuse", "message": "string"},
    }

    chartspec_summary = {
        "version": "v1",
        "required": ["version", "table", "chart", "encoding"],
        "chart_type": ["bar", "line", "pie", "histogram", "kpi"],
        "x_rule": "encoding.x.field must be dimension|temporal",
        "y_rule": "sum|avg|min|max require measure; count can use any valid field",
        "histogram_rule": "histogram bins raw values from encoding.y[0].field after filters",
        "filters": "=, !=, in, between, >, >=, <, <=",
    }

    explain_instructions = (
        "For explain responses: answer the user's specific question in plain language, "
        "include what this mart is good for, what it does not contain, "
        "and provide 3-5 example prompts split between chart and explain styles."
    )

    compact_history = [
        {
            "role": item.role,
            "message": item.message,
            "response_type": item.response_type,
        }
        for item in (history or [])
    ][-8:]

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
        f"Recent chat history: {json.dumps(compact_history, ensure_ascii=True)}\n\n"
        f"ChartSpec summary: {json.dumps(chartspec_summary, ensure_ascii=True)}\n"
        f"Allowed response schema: {json.dumps(response_schema, ensure_ascii=True)}\n\n"
        f"Additional explain instructions: {explain_instructions}\n\n"
        "Instruction: choose best available fields from context, do not copy templates verbatim, and avoid unnecessary clarify."
    )


def _generate_plan(
    *,
    dataset_id: str,
    table: str,
    message: str,
    mode: ChatMode,
    context: dict[str, Any],
    strategy_digest: dict[str, Any],
    strategy_notice: str | None,
    state: ChatState,
    history: list[ChatHistoryTurn] | None,
) -> tuple[
    ChatPlanUnion | None,
    Literal["missing_key", "openai_error"] | None,
    OpenAIDiagnostics | None,
    str | None,
]:
    settings = get_settings()
    openai_key = (settings.OPENAI_API_KEY or "").strip()
    if not openai_key:
        return None, "missing_key", None, None

    try:
        client = OpenAIClient(
            api_key=openai_key,
            model=settings.OPENAI_MODEL,
            temperature=0.2,
        )
    except OpenAIJSONError as exc:
        return None, "openai_error", classify_openai_exception(exc), type(exc).__name__

    system_prompt = _build_system_prompt(mode, strategy_digest=strategy_digest, strategy_notice=strategy_notice)
    user_prompt = _build_user_prompt(
        dataset_id=dataset_id,
        table=table,
        message=message,
        mode=mode,
        context=context,
        state=state,
        history=history,
    )

    corrective_prompt: str | None = None
    for attempt in range(2):
        try:
            payload = client.generate_json(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                corrective_prompt=corrective_prompt,
            )
        except OpenAIJSONError as exc:
            if attempt == 0:
                corrective_prompt = "Your previous output was invalid JSON. Return one valid JSON object only."
                continue
            return None, "openai_error", classify_openai_exception(exc), type(exc).__name__
        except Exception as exc:
            return None, "openai_error", classify_openai_exception(exc), type(exc).__name__

        normalized_payload, recovery_trace = _normalize_plan_payload(
            payload,
            context,
            dataset_id=dataset_id,
            table=table,
            message=message,
        )
        if normalized_payload is None:
            recovery_hint = "OpenAI returned a payload that could not be recovered into a structured response"
            if recovery_trace:
                recovery_hint = f"{recovery_hint} (recovery: {' -> '.join(recovery_trace[:3])})"
            if attempt == 0:
                corrective_prompt = (
                    "Return one JSON object only with response_type in [chart,chart_patch,explain,clarify,refuse]. "
                    "Do not wrap it in arrays or nested envelopes."
                )
                continue
            return (
                None,
                "openai_error",
                {
                    "openai_error_type": "unknown",
                    "openai_status_code": None,
                    "openai_error_hint": recovery_hint,
                },
                None,
            )
        try:
            return _PLAN_ADAPTER.validate_python(normalized_payload), None, None, None
        except ValidationError as exc:
            validation_hint = _summarize_plan_validation_error(exc, recovery_trace=recovery_trace)
            if attempt == 0:
                corrective_prompt = (
                    f"Your previous response did not match schema ({validation_hint}). "
                    "Return one JSON object with response_type in [chart,chart_patch,explain,clarify,refuse]."
                )
                continue
            return (
                None,
                "openai_error",
                {
                    "openai_error_type": "unknown",
                    "openai_status_code": None,
                    "openai_error_hint": validation_hint,
                },
                "ValidationError",
            )
    return (
        None,
        "openai_error",
        {
            "openai_error_type": "unknown",
            "openai_status_code": None,
            "openai_error_hint": "OpenAI request failed",
        },
        None,
    )


def _enforce_mode(
    plan: ChatPlanUnion,
    mode: ChatMode,
    context: dict[str, Any],
    *,
    table: str,
    message: str,
) -> ChatPlanUnion:
    if mode == "chart" and plan.response_type not in {"chart", "chart_patch", "clarify"}:
        return ChatPlanClarify(
            response_type="clarify",
            clarify_id=create_clarify_id(),
            question=_question_for_stage("metric"),
            missing=["metric"],
            options=_build_stage_options("metric", context),
        )

    if mode == "explain" and plan.response_type != "explain":
        return ChatPlanExplain(
            response_type="explain",
            message=_context_explain_message(context=context, table=table, user_message=message),
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
    topic = " ".join(user_message.strip().split())

    def _take(items: list[str], limit: int) -> list[str]:
        return [item for item in items if isinstance(item, str) and item][:limit]

    def _join(items: list[str]) -> str:
        return ", ".join(items)

    normalized_message = _normalize_text(user_message)
    asks_missing = _contains_any(
        normalized_message,
        [
            "not include",
            "not contain",
            "missing",
            "not covered",
            "not available",
            "doesn't include",
            "doesnt include",
        ],
    )

    good_for: list[str] = []
    if metrics and dimensions:
        good_for.append(f"comparing {metrics[0]} by {dimensions[0]}")
    if metrics and temporals:
        good_for.append(f"tracking {metrics[0]} over {temporals[0]}")
    if len(metrics) > 1:
        good_for.append(f"monitoring {metrics[1]}")

    missing_capabilities: list[str] = []
    if not temporals:
        missing_capabilities.append("no clear time field for trend analysis")
    if not dimensions:
        missing_capabilities.append("limited categorical breakdowns")
    if not metrics:
        missing_capabilities.append("no numeric measures to aggregate")

    chart_examples: list[str] = []
    explain_examples: list[str] = [f"Explain what {table} represents"]
    if metrics and dimensions:
        chart_examples.append(f"Show {metrics[0]} by {dimensions[0]}")
    if metrics and temporals:
        chart_examples.append(f"Trend of {metrics[0]} by {temporals[0]}")
    if metrics:
        chart_examples.append(f"Top 10 groups by {metrics[0]}")
        explain_examples.append(f"What does {metrics[0]} mean?")
    explain_examples.append("What questions is this mart best suited to answer?")

    metric_hint = _join(_take(metrics, 2))
    dimension_hint = _join(_take(dimensions, 2))
    temporal_hint = _join(_take(temporals, 2))

    if asks_missing:
        missing_summary = _join(_take(missing_capabilities, 2)) or "concepts outside its listed fields"
        available_summary = "; ".join(
            item
            for item in [
                f"metrics: {metric_hint}" if metric_hint else None,
                f"dimensions: {dimension_hint}" if dimension_hint else None,
                f"time: {temporal_hint}" if temporal_hint else None,
            ]
            if item
        )
        return (
            f"For '{topic}', here is a quick summary:\n"
            f"1) Mart: {table} represents {description}.\n"
            f"2) Missing or weak coverage: {missing_summary}.\n"
            f"3) Available signals: {available_summary or 'see the field list for details'}."
        )

    return (
        f"For '{topic}', here is a quick summary:\n"
        f"1) Mart: {table} represents {description}.\n"
        f"2) Best for: {', '.join(_take(good_for, 2)) if good_for else 'summary analytics using its available fields'}.\n"
        f"3) Key fields: {metric_hint or 'measures'}; {dimension_hint or 'dimensions'}; {temporal_hint or 'time fields'}.\n"
        f"4) Chart ideas: {' | '.join(_take(chart_examples, 2)) if chart_examples else 'Show a metric by a breakdown field'}.\n"
        f"5) Explain ideas: {' | '.join(_take(explain_examples, 2))}."
    )


def run_chat_orchestration(
    *,
    dataset_id: str,
    message: str,
    table: str | None,
    mode: ChatMode = "auto",
    state: ChatState | dict[str, Any] | None,
    history: list[ChatHistoryTurn] | None = None,
    db: Session,
    debug: bool = False,
) -> dict[str, Any]:
    settings = get_settings()
    openai_configured = bool((settings.OPENAI_API_KEY or "").strip())
    used_fallback = False
    fallback_reason: Literal["missing_key", "openai_error"] | None = None
    openai_error_type: str | None = None
    openai_status_code: int | None = None
    openai_error_hint: str | None = None

    strategy_digest, strategy_hash, strategy_notice = _load_strategy_runtime(dataset_id)
    strategy_pillars_used = _infer_strategy_pillars_used(message, strategy_digest)

    def finalize(payload: dict[str, Any]) -> dict[str, Any]:
        payload_with_strategy = _with_strategy_meta(
            payload,
            strategy_hash=strategy_hash,
            strategy_pillars_used=strategy_pillars_used,
        )
        return _with_chat_debug_meta(
            payload_with_strategy,
            used_fallback=used_fallback,
            openai_configured=openai_configured,
            fallback_reason=fallback_reason,
            openai_error_type=openai_error_type,
            openai_status_code=openai_status_code,
            openai_error_hint=openai_error_hint,
        )

    if not table:
        return finalize(
            ChatClarifyResponse(
                response_type="clarify",
                clarify_id=create_clarify_id(),
                question="Select a mart to proceed.",
                missing=["table"],
                options=ClarifyOptions(),
                meta={},
            ).model_dump(mode="json")
        )

    parsed_state = _parse_state(state)
    context = build_compact_mart_context(dataset_id=dataset_id, table=table)
    intent_message = parsed_state.original_user_intent or message

    state_plan = _state_driven_plan(table=table, mode=mode, context=context, state=parsed_state, message=message)
    if isinstance(state_plan, ChatPlanChart):
        chart_response = _execute_chart(
            dataset_id=dataset_id,
            table=table,
            chart_spec=state_plan.chart_spec,
            db=db,
            context=context,
            intent_message=intent_message,
            style=state_plan.narrative_style,
            debug=debug,
        )
        if isinstance(chart_response, ChatChartResponse):
            selections = _sanitize_selections(context, parsed_state.selections)
            if selections.temporal and selections.time_grain:
                chart_response.narrative = (
                    f"{chart_response.narrative} "
                    "Requested time grain noted; current execution groups by the raw temporal field."
                )
        return finalize(chart_response.model_dump(mode="json"))
    if isinstance(state_plan, ChatPlanClarify):
        stage = state_plan.missing[0] if state_plan.missing else "metric"
        return finalize(
            ChatClarifyResponse(
                response_type="clarify",
                clarify_id=state_plan.clarify_id,
                question=state_plan.question,
                missing=[stage],
                options=_sanitize_options(
                    state_plan.options,
                    context,
                    stage=stage,
                    prefer_temporal=_has_time_intent(intent_message),
                    requested_grain=_requested_time_grain(intent_message),
                ),
                meta={},
            ).model_dump(mode="json")
        )

    plan, generation_fallback_reason, generation_openai_diag, generation_exception_class = _generate_plan(
        dataset_id=dataset_id,
        table=table,
        message=message,
        mode=mode,
        context=context,
        strategy_digest=strategy_digest,
        strategy_notice=strategy_notice,
        state=parsed_state,
        history=history,
    )
    if plan is None:
        used_fallback = True
        fallback_reason = generation_fallback_reason or ("missing_key" if not openai_configured else "openai_error")
        if fallback_reason == "openai_error":
            diagnostics: OpenAIDiagnostics = generation_openai_diag or {
                "openai_error_type": "unknown",
                "openai_status_code": None,
                "openai_error_hint": "OpenAI request failed",
            }
            openai_error_type = diagnostics.get("openai_error_type")
            openai_status_code = diagnostics.get("openai_status_code")
            openai_error_hint = diagnostics.get("openai_error_hint")
            correlation_id = uuid4().hex[:12]
            log_openai_failure(
                logger,
                correlation_id,
                diagnostics,
                exception_class_name=generation_exception_class,
            )
        else:
            _log_chat_fallback(
                fallback_reason=fallback_reason,
                exception_class_name=generation_exception_class,
            )
        plan = _fallback_plan_from_context(message=message, mode=mode, table=table, context=context)

    plan = _enforce_mode(plan=plan, mode=mode, context=context, table=table, message=message)

    if isinstance(plan, ChatPlanChart):
        chart_response = _execute_chart(
            dataset_id=dataset_id,
            table=table,
            chart_spec=plan.chart_spec,
            db=db,
            context=context,
            intent_message=intent_message,
            style=plan.narrative_style,
            debug=debug,
        )
        return finalize(chart_response.model_dump(mode="json"))

    if isinstance(plan, ChatPlanPatch):
        last_raw = parsed_state.last_chart_spec
        if not last_raw:
            return finalize(
                _default_clarify(
                    "I need an existing chart first. What metric should we chart?",
                    context,
                    missing=["metric"],
                    intent_message=intent_message,
                ).model_dump(mode="json")
            )
        try:
            base = last_raw if isinstance(last_raw, ChartSpecV1) else ChartSpecV1.model_validate(last_raw)
            patched = apply_patch(base, plan.patch)
        except (ValidationError, HTTPException):
            return finalize(
                _default_clarify(
                    "I could not apply that update safely. Which metric should I use?",
                    context,
                    missing=["metric"],
                    intent_message=intent_message,
                ).model_dump(mode="json")
            )

        chart_response = _execute_chart(
            dataset_id=dataset_id,
            table=table,
            chart_spec=patched,
            db=db,
            context=context,
            intent_message=intent_message,
            style=plan.narrative_style,
            debug=debug,
        )
        return finalize(chart_response.model_dump(mode="json"))

    if isinstance(plan, ChatPlanExplain):
        if plan.optional_chart_spec:
            chart_response = _execute_chart(
                dataset_id=dataset_id,
                table=table,
                chart_spec=plan.optional_chart_spec,
                db=db,
                context=context,
                intent_message=intent_message,
                style="brief",
                debug=debug,
            )
            if isinstance(chart_response, ChatChartResponse):
                explain_message = _ensure_strategy_alignment_text(
                    f"{plan.message} {chart_response.narrative}",
                    strategy_digest,
                )
                return finalize(
                    ChatExplainResponse(
                        response_type="explain",
                        message=explain_message.strip(),
                        citations=["charts_preview"],
                        meta={"from_chart_preview": True, "chart_spec": chart_response.chart_spec.model_dump(mode="json")},
                    ).model_dump(mode="json")
                )

        explain_message = plan.message.strip() or _context_explain_message(context=context, table=table, user_message=message)
        explain_message = _ensure_strategy_alignment_text(explain_message, strategy_digest)
        return finalize(
            ChatExplainResponse(
                response_type="explain",
                message=explain_message,
                citations=[f"profile:{table}"],
                meta={},
            ).model_dump(mode="json")
        )

    if isinstance(plan, ChatPlanClarify):
        stage = plan.missing[0] if plan.missing else "metric"
        return finalize(
            ChatClarifyResponse(
                response_type="clarify",
                clarify_id=plan.clarify_id,
                question=plan.question.strip() or _question_for_stage(stage),
                missing=[stage],
                options=_sanitize_options(
                    plan.options,
                    context,
                    stage=stage,
                    prefer_temporal=_has_time_intent(intent_message),
                    requested_grain=_requested_time_grain(intent_message),
                ),
                meta={},
            ).model_dump(mode="json")
        )

    if isinstance(plan, ChatPlanRefuse):
        return finalize(
            ChatRefuseResponse(
                response_type="refuse",
                message=plan.message.strip() or "I can only help with analytics for the selected mart.",
                meta={},
            ).model_dump(mode="json")
        )

    return finalize(
        _default_clarify(
            "Please rephrase your analytics request with a metric and grouping field.",
            context,
            missing=["metric"],
            intent_message=intent_message,
        ).model_dump(mode="json")
    )


def response_chart_spec_hash(response_payload: dict[str, Any]) -> str | None:
    raw_spec = response_payload.get("chart_spec")
    if not isinstance(raw_spec, dict):
        return None
    try:
        spec = ChartSpecV1.model_validate(raw_spec)
    except ValidationError:
        return None
    return _chart_spec_hash(spec)
