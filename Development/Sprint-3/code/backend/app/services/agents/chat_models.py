"""Typed chat request/response contracts for orchestrator + API."""

from __future__ import annotations

from typing import Annotated, Any, Literal, Union

from pydantic import BaseModel, Field, field_validator

from app.services.charts.models import ChartSpecV1


class ChatRequest(BaseModel):
    message: str
    table: str | None = None
    state: dict[str, Any] | None = None

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
    message: str
    questions: list[str] = Field(default_factory=list)
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
