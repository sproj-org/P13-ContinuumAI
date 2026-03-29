"""Pydantic models for dataset strategy layer YAML bundles."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

ThresholdValue = str | int | float | bool
RuleSeverity = Literal["info", "warn", "block"]


class StrategicContext(BaseModel):
    model_config = ConfigDict(extra="allow")

    strengths: list[str] = Field(default_factory=list)
    weaknesses: list[str] = Field(default_factory=list)
    opportunities: list[str] = Field(default_factory=list)
    threats: list[str] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)
    thresholds: dict[str, ThresholdValue] = Field(default_factory=dict)

    @field_validator("strengths", "weaknesses", "opportunities", "threats", "assumptions", mode="before")
    @classmethod
    def _normalize_string_list(cls, value: Any) -> list[str]:
        if not isinstance(value, list):
            return []
        return [item for item in value if isinstance(item, str) and item.strip()]

    @field_validator("thresholds", mode="before")
    @classmethod
    def _normalize_thresholds(cls, value: Any) -> dict[str, ThresholdValue]:
        if not isinstance(value, dict):
            return {}
        output: dict[str, ThresholdValue] = {}
        for key, item in value.items():
            if not isinstance(key, str):
                continue
            if isinstance(item, (str, int, float, bool)):
                output[key] = item
        return output


class NorthStar(BaseModel):
    model_config = ConfigDict(extra="allow")

    id: str | None = None
    name: str
    description: str | None = None
    metric: str | None = None
    formula: str | None = None


class StrategyPillar(BaseModel):
    model_config = ConfigDict(extra="allow")

    id: str
    name: str
    description: str | None = None
    objectives: list[str] = Field(default_factory=list)
    priority_weight: float | None = None

    @field_validator("objectives", mode="before")
    @classmethod
    def _normalize_objectives(cls, value: Any) -> list[str]:
        if not isinstance(value, list):
            return []
        return [item for item in value if isinstance(item, str) and item.strip()]


class StrategyTargets(BaseModel):
    model_config = ConfigDict(extra="allow")

    company: str | None = None
    horizon: str | None = None
    north_star: NorthStar
    pillars: list[StrategyPillar] = Field(default_factory=list)


class KPIEntry(BaseModel):
    model_config = ConfigDict(extra="allow")

    id: str
    name: str
    description: str | None = None
    formula: str | None = None
    direction: Literal["up", "down"] | None = None
    owner: str | None = None
    tags: list[str] = Field(default_factory=list)
    related_fields: list[str] = Field(default_factory=list)
    category: str | None = None
    logic: str | None = None

    @field_validator("tags", "related_fields", mode="before")
    @classmethod
    def _normalize_array(cls, value: Any) -> list[str]:
        if not isinstance(value, list):
            return []
        return [item for item in value if isinstance(item, str) and item.strip()]


class KPIHierarchy(BaseModel):
    model_config = ConfigDict(extra="allow")

    north_star: KPIEntry | None = None
    kpis: list[KPIEntry] = Field(default_factory=list)
    hierarchy: dict[str, Any] = Field(default_factory=dict)


class DecisionRule(BaseModel):
    model_config = ConfigDict(extra="allow")

    id: str
    name: str
    description: str
    severity: RuleSeverity
    condition: str | None = None
    guidance: str | None = None
    applies_to: list[str] = Field(default_factory=list)
    action: str | None = None

    @field_validator("applies_to", mode="before")
    @classmethod
    def _normalize_applies_to(cls, value: Any) -> list[str]:
        if not isinstance(value, list):
            return []
        return [item for item in value if isinstance(item, str) and item.strip()]


class DecisionRules(BaseModel):
    model_config = ConfigDict(extra="allow")

    rules: list[DecisionRule] = Field(default_factory=list)


class ScoringWeight(BaseModel):
    model_config = ConfigDict(extra="allow")

    id: str
    name: str
    weight: float
    description: str | None = None


class ScoringGuardrail(BaseModel):
    model_config = ConfigDict(extra="allow")

    id: str
    name: str
    rule: str
    severity: RuleSeverity = "warn"


class StrategyScoring(BaseModel):
    model_config = ConfigDict(extra="allow")

    scoring_model_type: str | None = None
    weights: list[ScoringWeight] = Field(default_factory=list)
    guardrails: list[ScoringGuardrail] = Field(default_factory=list)


class StrategyBundle(BaseModel):
    context: StrategicContext
    targets: StrategyTargets
    kpis: KPIHierarchy
    rules: DecisionRules
    scoring: StrategyScoring

