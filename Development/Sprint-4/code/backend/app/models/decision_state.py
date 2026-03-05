"""Task-2 Decision State models."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class DecisionReadiness(BaseModel):
    model_config = ConfigDict(extra="forbid")

    overall_score: float
    kpi_coverage: float
    rule_readiness: float
    hierarchy_readiness: float
    data_readiness: float
    explanation: str | None = None


class ReadinessFlags(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kpis_defined: bool
    placeholders: list[str] = Field(default_factory=list)


class CoverageGapItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kpi_id: str
    reason: str
    details: dict[str, Any] | None = None


class DecisionStatePayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    revision: str
    generated_at: datetime
    strategy_bundle: dict[str, Any]
    kpi_registry: dict[str, Any]
    readiness: DecisionReadiness
    readiness_flags: ReadinessFlags | None = None
    coverage_gaps: list[CoverageGapItem] = Field(default_factory=list)
    summaries: dict[str, Any] | None = None
