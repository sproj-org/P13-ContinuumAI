"""Typed chat request/response contracts for orchestrator + API."""

from __future__ import annotations

from typing import Annotated, Any, Literal, Union

from pydantic import BaseModel, Field, field_validator

from app.services.charts.models import ChartSpecV1

ChatMode = Literal["auto", "chart", "explain"]


class ChatRequest(BaseModel):
    message: str
    table: str | None = None
    mode: ChatMode = "auto"
    state: dict[str, Any] | None = None
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
    question: str
    options: ClarifyOptions = Field(default_factory=ClarifyOptions)


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
    question: str
    options: ClarifyOptions = Field(default_factory=ClarifyOptions)
    meta: dict[str, Any] = Field(default_factory=dict)


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
