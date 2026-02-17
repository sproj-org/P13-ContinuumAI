"""
ChartSpec and Aggregate query schemas.

ChartSpec is the canonical, machine-readable description of a chart request.
It is the shared language between:
  - the LLM/agents (who propose analyses)
  - the backend execution engine (which runs safe aggregates)
  - the frontend renderer (which visualizes results)
"""

from typing import Any, Optional, Literal
from pydantic import BaseModel, field_validator, model_validator


# ============================================
# ChartSpec v1 Models (Frontend → Backend)
# ============================================


class EncodingField(BaseModel):
    """A single encoding axis field (used for x-axis)."""

    field: str
    role: Optional[Literal["dimension", "temporal"]] = None


class MetricField(BaseModel):
    """A metric encoding field (used for y-axis entries)."""

    field: str
    agg: Literal["sum", "avg", "count", "min", "max"]
    alias: Optional[str] = None


class ChartEncoding(BaseModel):
    """Encoding specification mapping data fields to visual channels."""

    x: EncodingField
    y: list[MetricField]


class ChartType(BaseModel):
    """Chart type specification."""

    type: Literal["bar", "line", "pie", "histogram", "scatter", "kpi"]


class FilterSpec(BaseModel):
    """A single filter condition."""

    field: str
    op: Literal["=", "!=", "<", ">", "<=", ">=", "in", "between", "contains"]
    value: Any

    @field_validator("field")
    @classmethod
    def validate_field_name(cls, v: str) -> str:
        import re

        if not re.match(r"^[a-zA-Z_][a-zA-Z0-9_]*$", v):
            raise ValueError(f"Invalid field name: {v}")
        return v


class SortSpec(BaseModel):
    """A single sort directive."""

    field: str
    dir: Literal["asc", "desc"] = "desc"


class ChartSpec(BaseModel):
    """
    ChartSpec v1 — canonical chart request.

    Example:
    {
      "version": "1.0",
      "dataset_id": "silkroute",
      "table": "mart_sales",
      "chart": { "type": "bar" },
      "encoding": {
        "x": { "field": "store_name", "role": "dimension" },
        "y": [{ "field": "revenue", "agg": "sum", "alias": "sum_revenue" }]
      },
      "filters": [],
      "sort": [{ "field": "sum_revenue", "dir": "desc" }],
      "limit": 50
    }
    """

    version: str = "1.0"
    dataset_id: str
    table: str
    chart: ChartType
    encoding: ChartEncoding
    filters: list[FilterSpec] = []
    sort: list[SortSpec] = []
    limit: int = 50

    @field_validator("limit")
    @classmethod
    def validate_limit(cls, v: int) -> int:
        if v < 1:
            raise ValueError("Limit must be at least 1")
        if v > 500:
            raise ValueError("Limit cannot exceed 500")
        return v

    @field_validator("table")
    @classmethod
    def validate_table_name(cls, v: str) -> str:
        import re

        if not re.match(r"^[a-zA-Z_][a-zA-Z0-9_]*$", v):
            raise ValueError(f"Invalid table name: {v}")
        return v


# ============================================
# AggregateRequest Models (Internal Engine)
# ============================================


class Metric(BaseModel):
    """A single aggregation metric for the query engine."""

    field: str
    aggregation: Literal["sum", "avg", "count", "min", "max"]
    alias: Optional[str] = None


class Filter(BaseModel):
    """A single filter for the query engine."""

    field: str
    op: Literal["=", "!=", "<", ">", "<=", ">=", "in", "between", "contains"]
    value: Any


class AggregateRequest(BaseModel):
    """
    Internal aggregate request — produced by the ChartSpec resolver.
    This is what the query builder consumes.
    """

    table: str
    dimensions: list[str] = []
    metrics: list[Metric]
    filters: list[Filter] = []
    limit: int = 50
    sort: list[SortSpec] = []

    @field_validator("table")
    @classmethod
    def validate_table_registered(cls, v: str) -> str:
        """Validate table exists in mart registry."""
        from app.services.profile_service import is_table_registered

        if not is_table_registered(v):
            raise ValueError(f"Table '{v}' is not in the mart registry.")
        return v

    @field_validator("limit")
    @classmethod
    def validate_limit_range(cls, v: int) -> int:
        """Validate limit is within allowed range."""
        if v < 1:
            raise ValueError("Limit must be at least 1.")
        if v > 500:
            raise ValueError(f"Limit {v} exceeds maximum of 500.")
        return v

    @model_validator(mode="after")
    def validate_profile_constraints(self) -> "AggregateRequest":
        """Validate all fields against profile metadata."""
        from app.services.profile_service import (
            get_column_profile_info,
            get_all_column_names,
        )

        # Role and type constants
        DIMENSION_ROLES = {"dimension", "temporal", "datetime", "id", "boolean", "text"}
        MEASURE_ROLE = "measure"
        NUMERIC_TYPES = {
            "int",
            "float",
            "decimal",
            "numeric",
            "double",
            "real",
            "bigint",
            "smallint",
        }

        errors: list[str] = []
        known_columns = get_all_column_names(self.table)

        # Validate dimensions
        for dim in self.dimensions:
            col_profile = get_column_profile_info(self.table, dim)
            if col_profile is None:
                errors.append(
                    f"Dimension field '{dim}' does not exist in table '{self.table}'."
                )
                continue

            effective_role = col_profile.get(
                "effective_role", col_profile.get("base_role", "")
            )
            if effective_role not in DIMENSION_ROLES:
                errors.append(
                    f"Field '{dim}' has role '{effective_role}' — "
                    f"it cannot be used as a dimension. "
                    f"Allowed roles: {', '.join(sorted(DIMENSION_ROLES))}."
                )

        # Validate metrics
        for metric in self.metrics:
            col_profile = get_column_profile_info(self.table, metric.field)
            if col_profile is None:
                errors.append(
                    f"Metric field '{metric.field}' does not exist in table '{self.table}'."
                )
                continue

            effective_role = col_profile.get(
                "effective_role", col_profile.get("base_role", "")
            )
            physical_type = col_profile.get("physical_type", "string")

            # COUNT is allowed on any column
            if metric.aggregation == "count":
                continue

            # SUM / AVG require measure role and numeric type
            if metric.aggregation in ("sum", "avg"):
                if effective_role != MEASURE_ROLE:
                    errors.append(
                        f"Cannot apply {metric.aggregation.upper()} to '{metric.field}' — "
                        f"it has role '{effective_role}', not 'measure'. "
                        f"Try COUNT instead, or pick a numeric column."
                    )
                elif not any(nt in physical_type.lower() for nt in NUMERIC_TYPES):
                    errors.append(
                        f"Cannot apply {metric.aggregation.upper()} to '{metric.field}' — "
                        f"physical type '{physical_type}' is not numeric."
                    )

        # Validate filter fields exist
        for filt in self.filters:
            if filt.field not in known_columns:
                errors.append(
                    f"Filter field '{filt.field}' does not exist in table '{self.table}'."
                )

        # Validate sort fields exist (can reference aliases or column names)
        metric_aliases = {m.alias for m in self.metrics if m.alias}
        valid_sort_fields = set(known_columns) | metric_aliases | set(self.dimensions)
        for s in self.sort:
            if s.field not in valid_sort_fields:
                errors.append(
                    f"Sort field '{s.field}' is not a known column or metric alias."
                )

        if errors:
            raise ValueError("; ".join(errors))

        return self


# ============================================
# AggregateResponse Models (Backend → Frontend)
# ============================================


class CacheMeta(BaseModel):
    """Cache metadata for the response."""

    hit: bool = False
    key: Optional[str] = None
    ttl_seconds: Optional[int] = None


class ResponseMeta(BaseModel):
    """Response metadata."""

    query_ms: Optional[float] = None
    cache: Optional[CacheMeta] = None


class AggregateResponse(BaseModel):
    """
    Response from the aggregate endpoint.

    Example:
    {
      "columns": ["store_name", "sum_revenue"],
      "rows": [["Store A", 123000], ["Store B", 98000]],
      "meta": { "query_ms": 42.5 }
    }
    """

    columns: list[str]
    rows: list[list[Any]]
    meta: ResponseMeta = ResponseMeta()
