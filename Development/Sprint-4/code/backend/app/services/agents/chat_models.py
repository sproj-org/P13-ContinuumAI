"""Typed chat request/response contracts for orchestrator + API."""

from __future__ import annotations

from uuid import uuid4
from typing import Annotated, Any, Literal, Union

from pydantic import BaseModel, Field, field_validator

from app.services.charts.models import ChartSpecV1
from app.services.intelligence.specs import (
    AnalysisContextSpec,
    AnalysisResponse,
    PlanSpec,
    QuerySpec,
    SpecFilter as QuerySpecFilter,
)

ChatMode = Literal["auto", "chart", "explain"]
TimeGrain = Literal["day", "week", "month", "quarter", "year"]
MetricAggregation = Literal["sum", "avg", "count", "min", "max"]
MissingField = Literal["metric", "x_axis", "time_grain", "table"]
ChatRole = Literal["user", "assistant"]
ChatResponseType = Literal["chart", "chart_patch", "explain", "clarify", "refuse"]
ChatFallbackReason = Literal["missing_key", "openai_error"]
ChartType = Literal["bar", "line", "pie", "histogram", "kpi"]
ChatFocusType = Literal["chart", "dashboard", "kpi", "analysis_result", "drill_state"]
ChatPromptKind = Literal["ask", "task", "chart_edit", "follow_up", "compare", "drill"]
ChatPromptRoute = Literal["explain", "analysis", "chart", "chart_patch", "guidance"]
ChatPromptArtifactAction = Literal[
    "explain_chart",
    "explain_kpi",
    "next_step",
    "drill_next",
    "chart_change",
    "forecast_drivers",
    "forecast_target_gap",
    "anomaly_driver",
    "anomaly_scope",
    "segment_differentiators",
    "segment_compare_extremes",
    "segment_drill_priority",
    "risk_driver",
    "risk_slice",
    "risk_next_step",
]


def create_clarify_id() -> str:
    return uuid4().hex[:12]


class ChatSelections(BaseModel):
    metric: str | None = None
    dimension: str | None = None
    temporal: str | None = None
    time_grain: TimeGrain | None = None
    aggregation: MetricAggregation | None = None
    limit: int | None = None

    @field_validator("metric", "dimension", "temporal")
    @classmethod
    def validate_identifiers(cls, value: str | None) -> str | None:
        if value is None:
            return value
        trimmed = value.strip()
        return trimmed or None

    @field_validator("limit")
    @classmethod
    def validate_limit(cls, value: int | None) -> int | None:
        if value is None:
            return value
        if value < 1:
            return 1
        if value > 5000:
            return 5000
        return value


class ChatState(BaseModel):
    last_chart_spec: ChartSpecV1 | dict[str, Any] | None = None
    clarify_id: str | None = None
    selections: ChatSelections = Field(default_factory=ChatSelections)
    original_user_intent: str | None = None

    @field_validator("clarify_id", "original_user_intent")
    @classmethod
    def trim_optional_strings(cls, value: str | None) -> str | None:
        if value is None:
            return None
        trimmed = value.strip()
        return trimmed or None


class ChatHistoryTurn(BaseModel):
    role: ChatRole
    message: str
    response_type: ChatResponseType | None = None

    @field_validator("message")
    @classmethod
    def validate_message(cls, value: str) -> str:
        trimmed = value.strip()
        if not trimmed:
            raise ValueError("message is required")
        return trimmed


class ChatFocusContext(BaseModel):
    focus_type: ChatFocusType
    title: str | None = None
    table: str | None = None
    kpi_id: str | None = None
    chart_spec: ChartSpecV1 | None = None
    chart_rows: list[dict[str, Any]] = Field(default_factory=list)
    analysis_context: AnalysisContextSpec | None = None
    semantic_context: dict[str, Any] | None = None
    active_task: str | None = None
    analysis_result: AnalysisResponse | None = None
    summary: str | None = None
    breadcrumbs: list[str] = Field(default_factory=list)

    @field_validator("title", "table", "kpi_id", "active_task", "summary")
    @classmethod
    def trim_optional_strings(cls, value: str | None) -> str | None:
        if value is None:
            return None
        trimmed = value.strip()
        return trimmed or None

    @field_validator("breadcrumbs", mode="before")
    @classmethod
    def normalize_breadcrumbs(cls, value: Any) -> list[str]:
        if not isinstance(value, list):
            return []
        return [item.strip() for item in value if isinstance(item, str) and item.strip()]


class ChatRequest(BaseModel):
    message: str
    table: str | None = None
    mode: ChatMode = "auto"
    state: ChatState | None = None
    history: list[ChatHistoryTurn] | None = None
    focus: ChatFocusContext | None = None
    quick_prompt: "ChatQuickPrompt | None" = None
    debug: bool = False

    @field_validator("message")
    @classmethod
    def validate_message(cls, value: str) -> str:
        trimmed = value.strip()
        if not trimmed:
            raise ValueError("message is required")
        return trimmed


class ChatQuickPrompt(BaseModel):
    label: str
    prompt_text: str
    prompt_kind: ChatPromptKind
    preferred_route: ChatPromptRoute
    focus_type: ChatFocusType | None = None
    analysis_result_type: str | None = None
    artifact_action: ChatPromptArtifactAction | None = None
    task_type: str | None = None

    @field_validator("label", "prompt_text", "analysis_result_type", "task_type")
    @classmethod
    def trim_prompt_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        trimmed = value.strip()
        return trimmed or None


class ChartSpecPatch(BaseModel):
    set: dict[str, Any] = Field(default_factory=dict)
    unset: list[str] = Field(default_factory=list)
    add: dict[str, Any] = Field(default_factory=dict)


class ClarifyOptions(BaseModel):
    metrics: list[str] = Field(default_factory=list)
    dimensions: list[str] = Field(default_factory=list)
    temporals: list[str] = Field(default_factory=list)
    time_grains: list[TimeGrain] = Field(default_factory=list)

    @field_validator("metrics", "dimensions", "temporals", mode="before")
    @classmethod
    def normalize_string_arrays(cls, value: Any) -> list[str]:
        if not isinstance(value, list):
            return []
        return [item for item in value if isinstance(item, str)]

    @field_validator("time_grains", mode="before")
    @classmethod
    def normalize_time_grains(cls, value: Any) -> list[TimeGrain]:
        allowed = {"day", "week", "month", "quarter", "year"}
        if not isinstance(value, list):
            return []
        output: list[TimeGrain] = []
        for item in value:
            if isinstance(item, str):
                normalized = item.strip().lower()
                if normalized in allowed and normalized not in output:
                    output.append(normalized)  # type: ignore[arg-type]
        return output


class ChatPlanChart(BaseModel):
    response_type: Literal["chart"] = "chart"
    chart_spec: ChartSpecV1
    narrative_style: Literal["brief", "standard"] = "standard"


class ChatPlanPatch(BaseModel):
    response_type: Literal["chart_patch"] = "chart_patch"
    patch: ChartSpecPatch
    narrative_style: Literal["brief", "standard"] = "standard"


class ChatPlanExplain(BaseModel):
    response_type: Literal["explain"] = "explain"
    message: str
    optional_chart_spec: ChartSpecV1 | None = None


class ChatPlanClarify(BaseModel):
    response_type: Literal["clarify"] = "clarify"
    clarify_id: str = Field(default_factory=create_clarify_id)
    question: str
    missing: list[MissingField] = Field(default_factory=list)
    options: ClarifyOptions = Field(default_factory=ClarifyOptions)

    @field_validator("missing", mode="before")
    @classmethod
    def normalize_missing(cls, value: Any) -> list[MissingField]:
        legacy_map = {"dimension": "x_axis", "temporal": "x_axis"}
        allowed = {"metric", "x_axis", "time_grain", "table"}
        if not isinstance(value, list):
            return []
        output: list[MissingField] = []
        for item in value:
            if not isinstance(item, str):
                continue
            normalized = legacy_map.get(item.strip().lower(), item.strip().lower())
            if normalized in allowed and normalized not in output:
                output.append(normalized)  # type: ignore[arg-type]
        return output


class ChatPlanRefuse(BaseModel):
    response_type: Literal["refuse"] = "refuse"
    message: str


ChatPlanUnion = Annotated[
    Union[
        ChatPlanChart,
        ChatPlanPatch,
        ChatPlanExplain,
        ChatPlanClarify,
        ChatPlanRefuse,
    ],
    Field(discriminator="response_type"),
]


class ChatChartResponse(BaseModel):
    response_type: Literal["chart"] = "chart"
    chart_spec: ChartSpecV1
    columns: list[str]
    rows: list[dict[str, Any]]
    narrative: str
    meta: dict[str, Any] = Field(default_factory=dict)
    query_spec: QuerySpec | None = None
    plan_spec: PlanSpec | None = None
    analysis: AnalysisResponse | None = None
    used_fallback: bool | None = None
    openai_configured: bool | None = None
    fallback_reason: ChatFallbackReason | None = None
    openai_error_type: str | None = None
    openai_status_code: int | None = None
    openai_error_hint: str | None = None


class ChatPatchResponse(BaseModel):
    response_type: Literal["chart_patch"] = "chart_patch"
    patch: ChartSpecPatch
    narrative: str | None = None
    meta: dict[str, Any] = Field(default_factory=dict)
    query_spec: QuerySpec | None = None
    plan_spec: PlanSpec | None = None
    analysis: AnalysisResponse | None = None
    used_fallback: bool | None = None
    openai_configured: bool | None = None
    fallback_reason: ChatFallbackReason | None = None
    openai_error_type: str | None = None
    openai_status_code: int | None = None
    openai_error_hint: str | None = None


class ChatExplainResponse(BaseModel):
    response_type: Literal["explain"] = "explain"
    message: str
    citations: list[str] = Field(default_factory=list)
    meta: dict[str, Any] = Field(default_factory=dict)
    query_spec: QuerySpec | None = None
    plan_spec: PlanSpec | None = None
    analysis: AnalysisResponse | None = None
    used_fallback: bool | None = None
    openai_configured: bool | None = None
    fallback_reason: ChatFallbackReason | None = None
    openai_error_type: str | None = None
    openai_status_code: int | None = None
    openai_error_hint: str | None = None


class ChatClarifyResponse(BaseModel):
    response_type: Literal["clarify"] = "clarify"
    clarify_id: str = Field(default_factory=create_clarify_id)
    question: str
    missing: list[MissingField] = Field(default_factory=list)
    options: ClarifyOptions = Field(default_factory=ClarifyOptions)
    meta: dict[str, Any] = Field(default_factory=dict)
    query_spec: QuerySpec | None = None
    plan_spec: PlanSpec | None = None
    analysis: AnalysisResponse | None = None
    used_fallback: bool | None = None
    openai_configured: bool | None = None
    fallback_reason: ChatFallbackReason | None = None
    openai_error_type: str | None = None
    openai_status_code: int | None = None
    openai_error_hint: str | None = None

    @field_validator("missing", mode="before")
    @classmethod
    def normalize_missing(cls, value: Any) -> list[MissingField]:
        legacy_map = {"dimension": "x_axis", "temporal": "x_axis"}
        allowed = {"metric", "x_axis", "time_grain", "table"}
        if not isinstance(value, list):
            return []
        output: list[MissingField] = []
        for item in value:
            if not isinstance(item, str):
                continue
            normalized = legacy_map.get(item.strip().lower(), item.strip().lower())
            if normalized in allowed and normalized not in output:
                output.append(normalized)  # type: ignore[arg-type]
        return output


class ChatRefuseResponse(BaseModel):
    response_type: Literal["refuse"] = "refuse"
    message: str
    meta: dict[str, Any] = Field(default_factory=dict)
    query_spec: QuerySpec | None = None
    plan_spec: PlanSpec | None = None
    analysis: AnalysisResponse | None = None
    used_fallback: bool | None = None
    openai_configured: bool | None = None
    fallback_reason: ChatFallbackReason | None = None
    openai_error_type: str | None = None
    openai_status_code: int | None = None
    openai_error_hint: str | None = None


ChatResponseUnion = Annotated[
    Union[
        ChatChartResponse,
        ChatPatchResponse,
        ChatExplainResponse,
        ChatClarifyResponse,
        ChatRefuseResponse,
    ],
    Field(discriminator="response_type"),
]
