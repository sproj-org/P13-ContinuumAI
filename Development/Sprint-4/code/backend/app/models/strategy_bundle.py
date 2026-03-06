"""Task-2 Strategy Bundle models."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class StrategicContext(BaseModel):
    model_config = ConfigDict(extra="forbid")

    company: str
    horizon: str
    north_star_metric: str
    narrative: str | None = None


class StrategyPillar(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    description: str
    owner: str | None = None


class SWOTBlock(BaseModel):
    model_config = ConfigDict(extra="forbid")

    strengths: list[str] = Field(default_factory=list)
    weaknesses: list[str] = Field(default_factory=list)
    opportunities: list[str] = Field(default_factory=list)
    threats: list[str] = Field(default_factory=list)


class TargetThreshold(BaseModel):
    model_config = ConfigDict(extra="forbid")

    target: float
    red_threshold: float | None = None
    yellow_threshold: float | None = None
    direction: Literal["up", "down"] = "up"
    owner: str | None = None
    horizon: str | None = None


class DecisionRule(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    condition: str
    action: str
    severity: Literal["info", "warn", "block"]
    rationale: str | None = None


class StrategyScoringWeights(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kpi_coverage: float = 0.4
    rule_readiness: float = 0.2
    hierarchy_readiness: float = 0.2
    data_readiness: float = 0.2

    @model_validator(mode="after")
    def validate_weights(self) -> "StrategyScoringWeights":
        values = [
            self.kpi_coverage,
            self.rule_readiness,
            self.hierarchy_readiness,
            self.data_readiness,
        ]
        if any(value < 0 for value in values):
            raise ValueError("Scoring weights must be non-negative.")
        if sum(values) <= 0:
            raise ValueError("At least one scoring weight must be greater than zero.")
        return self


class StrategyScoringModel(BaseModel):
    model_config = ConfigDict(extra="forbid")

    weights: StrategyScoringWeights


class StrategyBundle(BaseModel):
    """Merged Strategy Bundle for Task-2 decision state."""

    model_config = ConfigDict(extra="forbid")

    schema_version: int = 1
    version: str
    strategic_context: StrategicContext
    pillars: list[StrategyPillar] = Field(default_factory=list)
    swot: SWOTBlock | None = None
    targets: dict[str, TargetThreshold] = Field(default_factory=dict)
    decision_rules: list[DecisionRule] = Field(default_factory=list)
    scoring_model: StrategyScoringModel

    @field_validator("schema_version")
    @classmethod
    def validate_schema_version(cls, value: int) -> int:
        if value < 1:
            raise ValueError("schema_version must be >= 1")
        return value
