"""Task-2 KPI Registry models."""

from __future__ import annotations

from functools import lru_cache

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.core.mart_registry import get_mart_ids, supported_dataset_ids


@lru_cache(maxsize=1)
def _all_known_marts() -> set[str]:
    marts: set[str] = set()
    for dataset_id in supported_dataset_ids():
        marts.update(get_mart_ids(dataset_id))
    return marts


class KPIRegistryEntry(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    description: str
    formula: str
    marts: list[str] = Field(default_factory=list)
    required_columns: list[str] = Field(default_factory=list)
    dimensions: list[str] = Field(default_factory=list)
    default_grain: str | None = None
    pillar_id: str | None = None
    owner: str | None = None
    display_name: str | None = None
    semantic_family: str | None = None
    metric_aliases: list[str] = Field(default_factory=list)
    preferred_drill_path: list[str] = Field(default_factory=list)
    terminal_dimensions: list[str] = Field(default_factory=list)
    disallowed_drill_dimensions: list[str] = Field(default_factory=list)
    preferred_chart_types: list[str] = Field(default_factory=list)
    derived_metrics: dict[str, str] = Field(default_factory=dict)

    @field_validator("id")
    @classmethod
    def validate_id(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("id is required")
        return normalized

    @field_validator("marts")
    @classmethod
    def validate_marts(cls, value: list[str]) -> list[str]:
        known = _all_known_marts()
        unknown = [item for item in value if item not in known]
        if unknown:
            unknown_rendered = ", ".join(sorted(set(unknown)))
            raise ValueError(f"Unknown mart ids: {unknown_rendered}")
        return value

    @field_validator("required_columns", "dimensions", "metric_aliases", "preferred_drill_path", "terminal_dimensions", "disallowed_drill_dimensions")
    @classmethod
    def normalize_string_arrays(cls, value: list[str]) -> list[str]:
        output: list[str] = []
        for item in value:
            trimmed = item.strip()
            if trimmed:
                output.append(trimmed)
        return output

    @field_validator("preferred_chart_types")
    @classmethod
    def normalize_chart_type_arrays(cls, value: list[str]) -> list[str]:
        allowed = {"bar", "line", "pie", "histogram", "kpi"}
        output: list[str] = []
        for item in value:
            trimmed = item.strip().lower()
            if trimmed in allowed and trimmed not in output:
                output.append(trimmed)
        return output

    @field_validator("derived_metrics")
    @classmethod
    def normalize_derived_metrics(cls, value: dict[str, str]) -> dict[str, str]:
        normalized: dict[str, str] = {}
        for key, metric_formula in value.items():
            key_trimmed = key.strip()
            formula_trimmed = metric_formula.strip()
            if key_trimmed and formula_trimmed:
                normalized[key_trimmed] = formula_trimmed
        return normalized

    @field_validator("pillar_id", "owner", "display_name", "semantic_family")
    @classmethod
    def normalize_optional_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        trimmed = value.strip()
        return trimmed or None


class KPIRegistry(BaseModel):
    """Merged KPI Registry for Task-2 decision state."""

    model_config = ConfigDict(extra="forbid")

    schema_version: int = 1
    version: str
    kpis: list[KPIRegistryEntry] = Field(default_factory=list)
    aliases: dict[str, str] = Field(default_factory=dict)
    derived_metrics: dict[str, str] = Field(default_factory=dict)

    @field_validator("schema_version")
    @classmethod
    def validate_schema_version(cls, value: int) -> int:
        if value < 1:
            raise ValueError("schema_version must be >= 1")
        return value
