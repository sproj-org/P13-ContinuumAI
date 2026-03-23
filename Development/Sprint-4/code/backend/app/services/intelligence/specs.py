"""Shared structured specs for orchestration, prediction, segmentation, and insights."""

from __future__ import annotations

from typing import Any, Literal
from uuid import uuid4

from pydantic import BaseModel, Field, field_validator, model_validator

from app.services.charts.models import ChartSpecV1

ChartType = Literal["bar", "line", "pie", "histogram", "kpi"]
MetricAggregation = Literal["sum", "avg", "count", "min", "max"]
TimeGrain = Literal["day", "week", "month", "quarter", "year"]
TaskType = Literal["query", "insight", "profile", "forecast", "anomaly", "segment", "strategy_risk"]
AgentRole = Literal["viz_agent", "profiling_agent", "strategy_agent", "insight_agent", "ml_agent"]
RiskBand = Literal["low", "medium", "high", "unknown"]

_FILTER_OP_ALIASES = {
    "=": "=",
    "eq": "=",
    "equals": "=",
    "!=": "!=",
    "ne": "!=",
    "neq": "!=",
    "not_equals": "!=",
    "in": "in",
    "between": "between",
    ">": ">",
    "gt": ">",
    ">=": ">=",
    "gte": ">=",
    "<": "<",
    "lt": "<",
    "<=": "<=",
    "lte": "<=",
}


def _clean_optional(value: str | None) -> str | None:
    if value is None:
        return None
    trimmed = value.strip()
    return trimmed or None


class SpecFilter(BaseModel):
    field: str
    op: Literal["=", "!=", "in", "between", ">", ">=", "<", "<="] = "="
    value: Any = None

    @field_validator("field")
    @classmethod
    def validate_field(cls, value: str) -> str:
        trimmed = value.strip()
        if not trimmed:
            raise ValueError("field is required")
        return trimmed

    @field_validator("op", mode="before")
    @classmethod
    def normalize_op(cls, value: Any) -> str:
        normalized = _FILTER_OP_ALIASES.get(str(value or "").strip().lower())
        if normalized is None:
            raise ValueError("unsupported filter operator")
        return normalized


class QuerySpec(BaseModel):
    dataset_id: str | None = None
    table: str | None = None
    chart_type: ChartType | None = None
    measures: list[str] = Field(default_factory=list)
    dimensions: list[str] = Field(default_factory=list)
    time_field: str | None = None
    aggregation: MetricAggregation | None = None
    time_grain: TimeGrain | None = None
    filters: list[SpecFilter] = Field(default_factory=list)
    limit: int | None = None
    kpi_id: str | None = None
    semantic_family: str | None = None
    drill_dimensions: list[str] = Field(default_factory=list)
    recommendation_source: str | None = None

    @field_validator("dataset_id", "table", "time_field", "kpi_id", "semantic_family", "recommendation_source")
    @classmethod
    def trim_optional_strings(cls, value: str | None) -> str | None:
        return _clean_optional(value)

    @field_validator("measures", "dimensions", "drill_dimensions")
    @classmethod
    def normalize_string_arrays(cls, value: list[str]) -> list[str]:
        output: list[str] = []
        for item in value:
            trimmed = item.strip()
            if trimmed and trimmed not in output:
                output.append(trimmed)
        return output

    @field_validator("limit")
    @classmethod
    def validate_limit(cls, value: int | None) -> int | None:
        if value is None:
            return None
        return max(1, min(5000, value))


class InsightSpec(BaseModel):
    focus: str | None = None
    source_task: TaskType | None = None
    kpi_id: str | None = None
    narrative_style: Literal["brief", "standard"] = "standard"

    @field_validator("focus", "kpi_id")
    @classmethod
    def trim_strings(cls, value: str | None) -> str | None:
        return _clean_optional(value)


class PredictionSpec(BaseModel):
    mode: Literal["forecast", "anomaly", "risk"] = "forecast"
    dataset_id: str | None = None
    table: str
    metric: str
    aggregation: MetricAggregation = "sum"
    time_field: str
    time_grain: TimeGrain = "month"
    filters: list[SpecFilter] = Field(default_factory=list)
    group_by: list[str] = Field(default_factory=list)
    horizon: int = 6
    kpi_id: str | None = None
    target_value: float | None = None
    target_direction: Literal["up", "down"] | None = None
    sensitivity: float = 2.5

    @field_validator("dataset_id", "table", "metric", "time_field", "kpi_id")
    @classmethod
    def trim_required_strings(cls, value: str | None) -> str | None:
        return _clean_optional(value)

    @field_validator("group_by")
    @classmethod
    def normalize_group_by(cls, value: list[str]) -> list[str]:
        output: list[str] = []
        for item in value:
            trimmed = item.strip()
            if trimmed and trimmed not in output:
                output.append(trimmed)
        return output

    @field_validator("horizon")
    @classmethod
    def validate_horizon(cls, value: int) -> int:
        return max(1, min(24, value))

    @field_validator("sensitivity")
    @classmethod
    def validate_sensitivity(cls, value: float) -> float:
        return min(max(float(value), 1.0), 5.0)


class SegmentSpec(BaseModel):
    dataset_id: str | None = None
    table: str
    entity_field: str
    features: list[str] = Field(default_factory=list)
    filters: list[SpecFilter] = Field(default_factory=list)
    cluster_count: int = 4
    metric_focus: str | None = None

    @field_validator("dataset_id", "table", "entity_field", "metric_focus")
    @classmethod
    def trim_strings(cls, value: str | None) -> str | None:
        return _clean_optional(value)

    @field_validator("features")
    @classmethod
    def normalize_features(cls, value: list[str]) -> list[str]:
        output: list[str] = []
        for item in value:
            trimmed = item.strip()
            if trimmed and trimmed not in output:
                output.append(trimmed)
        return output

    @field_validator("cluster_count")
    @classmethod
    def validate_cluster_count(cls, value: int) -> int:
        return max(2, min(8, value))


class StrategySpec(BaseModel):
    dataset_id: str | None = None
    kpi_id: str
    table: str | None = None
    target_value: float | None = None
    direction: Literal["up", "down"] | None = None
    time_grain: TimeGrain = "month"
    horizon: int = 6
    filters: list[SpecFilter] = Field(default_factory=list)

    @field_validator("dataset_id", "kpi_id", "table")
    @classmethod
    def trim_strings(cls, value: str | None) -> str | None:
        return _clean_optional(value)

    @field_validator("horizon")
    @classmethod
    def validate_horizon(cls, value: int) -> int:
        return max(1, min(24, value))


class AgentTaskSpec(BaseModel):
    task_id: str = Field(default_factory=lambda: uuid4().hex[:12])
    task_type: TaskType
    agent_role: AgentRole
    title: str
    priority: int = 1
    query_spec: QuerySpec | None = None
    insight_spec: InsightSpec | None = None
    prediction_spec: PredictionSpec | None = None
    segment_spec: SegmentSpec | None = None
    strategy_spec: StrategySpec | None = None

    @field_validator("title")
    @classmethod
    def validate_title(cls, value: str) -> str:
        trimmed = value.strip()
        if not trimmed:
            raise ValueError("title is required")
        return trimmed

    @model_validator(mode="after")
    def validate_payload(self) -> "AgentTaskSpec":
        payloads = [
            self.query_spec,
            self.insight_spec,
            self.prediction_spec,
            self.segment_spec,
            self.strategy_spec,
        ]
        if all(item is None for item in payloads):
            raise ValueError("task requires at least one concrete spec")
        return self


class PlanSpec(BaseModel):
    plan_id: str = Field(default_factory=lambda: uuid4().hex[:12])
    dataset_id: str
    table: str | None = None
    user_message: str
    primary_task: TaskType
    route_reason: str
    matched_kpi_id: str | None = None
    matched_kpi_label: str | None = None
    tasks: list[AgentTaskSpec] = Field(default_factory=list)
    suggested_follow_ups: list[str] = Field(default_factory=list)


class InsightCard(BaseModel):
    title: str
    summary: str
    severity: Literal["info", "warn", "critical"] = "info"
    source: AgentRole = "insight_agent"
    recommended_action: str | None = None
    evidence: list[str] = Field(default_factory=list)


class PredictionPoint(BaseModel):
    label: str
    actual: float | None = None
    forecast: float | None = None
    lower: float | None = None
    upper: float | None = None
    anomaly_score: float | None = None
    anomaly_flag: bool = False
    is_forecast: bool = False
    target_value: float | None = None


class PredictionAnomaly(BaseModel):
    label: str
    value: float
    deviation: float
    severity: Literal["low", "medium", "high"] = "medium"


class PredictionSummary(BaseModel):
    mode: Literal["forecast", "anomaly", "risk"]
    metric: str
    time_field: str
    time_grain: TimeGrain
    horizon: int
    points: list[PredictionPoint] = Field(default_factory=list)
    anomalies: list[PredictionAnomaly] = Field(default_factory=list)
    projected_change_pct: float | None = None
    risk_band: RiskBand | None = None
    target_value: float | None = None
    target_direction: Literal["up", "down"] | None = None
    explanation: str | None = None


class SegmentAssignment(BaseModel):
    entity_id: str
    cluster_id: int
    projection_x: float | None = None
    projection_y: float | None = None
    feature_values: dict[str, float] = Field(default_factory=dict)


class SegmentProfile(BaseModel):
    cluster_id: int
    label: str
    entity_count: int
    centroid: dict[str, float] = Field(default_factory=dict)
    metric_highlights: list[str] = Field(default_factory=list)


class SegmentSummary(BaseModel):
    entity_field: str
    cluster_count: int
    features: list[str] = Field(default_factory=list)
    assignments: list[SegmentAssignment] = Field(default_factory=list)
    profiles: list[SegmentProfile] = Field(default_factory=list)
    silhouette_hint: float | None = None


class StrategyRiskSummary(BaseModel):
    kpi_id: str
    target_value: float | None = None
    current_value: float | None = None
    projected_value: float | None = None
    variance_to_target: float | None = None
    direction: Literal["up", "down"] | None = None
    risk_band: RiskBand = "unknown"
    explanation: str | None = None


class SuggestedAction(BaseModel):
    action_type: Literal["forecast", "anomaly", "segment", "drill", "strategy_risk", "open_chart_builder"]
    label: str
    description: str | None = None
    payload: dict[str, Any] = Field(default_factory=dict)


class NormalizedDataView(BaseModel):
    chart_spec: ChartSpecV1 | None = None
    columns: list[str] = Field(default_factory=list)
    rows: list[dict[str, Any]] = Field(default_factory=list)
    summary: str | None = None


class AnalysisRequest(BaseModel):
    message: str | None = None
    task_type: Literal["auto", "query", "insight", "profile", "forecast", "anomaly", "segment", "strategy_risk"] = "auto"
    table: str | None = None
    chart_spec: ChartSpecV1 | None = None
    chart_rows: list[dict[str, Any]] = Field(default_factory=list)
    query_spec: QuerySpec | None = None
    prediction_spec: PredictionSpec | None = None
    segment_spec: SegmentSpec | None = None
    strategy_spec: StrategySpec | None = None
    kpi_id: str | None = None
    metric: str | None = None
    time_field: str | None = None
    time_grain: TimeGrain | None = None
    horizon: int | None = None
    entity_field: str | None = None
    features: list[str] = Field(default_factory=list)
    filters: list[SpecFilter] = Field(default_factory=list)
    cluster_count: int | None = None


class AnalysisResponse(BaseModel):
    task_type: TaskType
    agent_role: AgentRole
    plan_spec: PlanSpec
    query_spec: QuerySpec | None = None
    primary_view: NormalizedDataView | None = None
    insight_cards: list[InsightCard] = Field(default_factory=list)
    prediction: PredictionSummary | None = None
    segmentation: SegmentSummary | None = None
    strategy: StrategyRiskSummary | None = None
    suggested_actions: list[SuggestedAction] = Field(default_factory=list)
    meta: dict[str, Any] = Field(default_factory=dict)
