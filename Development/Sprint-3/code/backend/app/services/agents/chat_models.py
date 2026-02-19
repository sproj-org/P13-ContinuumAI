"""Typed chat request/response contracts for orchestrator + API."""

from __future__ import annotations

from uuid import uuid4
from typing import Annotated, Any, Literal, Union

from pydantic import BaseModel, Field, field_validator

from app.services.charts.models import ChartSpecV1

ChatMode = Literal["auto", "chart", "explain"]
TimeGrain = Literal["day", "week", "month", "quarter", "year"]
MetricAggregation = Literal["sum", "avg", "count", "min", "max"]


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


class ChatRequest(BaseModel):
    message: str
    table: str | None = None
    mode: ChatMode = "auto"
    state: ChatState | None = None
    debug: bool = False

    @field_validator("message")
    @classmethod
    def validate_message(cls, value: str) -> str:
        trimmed = value.strip()
        if not trimmed:
            raise ValueError("message is required")
        return trimmed


class ChartSpecPatch(BaseModel):
    set: dict[str, Any] = Field(default_factory=dict)
    unset: list[str] = Field(default_factory=list)
    add: dict[str, Any] = Field(default_factory=dict)


class ClarifyOptions(BaseModel):
    metrics: list[str] = Field(default_factory=list)
    dimensions: list[str] = Field(default_factory=list)
    temporals: list[str] = Field(default_factory=list)

    @field_validator("metrics", "dimensions", "temporals", mode="before")
    @classmethod
    def normalize_string_arrays(cls, value: Any) -> list[str]:
        if not isinstance(value, list):
            return []
        return [item for item in value if isinstance(item, str)]


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
    missing: list[str] = Field(default_factory=list)
    options: ClarifyOptions = Field(default_factory=ClarifyOptions)

    @field_validator("missing", mode="before")
    @classmethod
    def normalize_missing(cls, value: Any) -> list[str]:
        if not isinstance(value, list):
            return []
        return [item.strip() for item in value if isinstance(item, str) and item.strip()]


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


class ChatPatchResponse(BaseModel):
    response_type: Literal["chart_patch"] = "chart_patch"
    patch: ChartSpecPatch
    narrative: str | None = None
    meta: dict[str, Any] = Field(default_factory=dict)


class ChatExplainResponse(BaseModel):
    response_type: Literal["explain"] = "explain"
    message: str
    citations: list[str] = Field(default_factory=list)
    meta: dict[str, Any] = Field(default_factory=dict)


class ChatClarifyResponse(BaseModel):
    response_type: Literal["clarify"] = "clarify"
    clarify_id: str = Field(default_factory=create_clarify_id)
    question: str
    missing: list[str] = Field(default_factory=list)
    options: ClarifyOptions = Field(default_factory=ClarifyOptions)
    meta: dict[str, Any] = Field(default_factory=dict)

    @field_validator("missing", mode="before")
    @classmethod
    def normalize_missing(cls, value: Any) -> list[str]:
        if not isinstance(value, list):
            return []
        return [item.strip() for item in value if isinstance(item, str) and item.strip()]


class ChatRefuseResponse(BaseModel):
    response_type: Literal["refuse"] = "refuse"
    message: str
    meta: dict[str, Any] = Field(default_factory=dict)


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
