"""ChartSpec v1 request/response models."""

from __future__ import annotations

import re
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator, model_validator

IDENTIFIER_RE = re.compile(r"^[a-zA-Z_][a-zA-Z0-9_]*$")
DATASET_ID_RE = re.compile(r"^[a-zA-Z0-9_-]+$")


def _validate_identifier(value: str, field_name: str) -> str:
    if not IDENTIFIER_RE.match(value):
        raise ValueError(f"Invalid {field_name}: {value}")
    return value


class ChartVisualSpec(BaseModel):
    type: Literal["bar", "line", "pie", "histogram", "kpi"] = "bar"


class XEncodingSpec(BaseModel):
    field: str

    @field_validator("field")
    @classmethod
    def validate_field(cls, value: str) -> str:
        return _validate_identifier(value, "x field")


class YMetricSpec(BaseModel):
    field: str
    aggregation: Literal["sum", "avg", "count", "min", "max"] = "sum"
    alias: str | None = None

    @field_validator("field")
    @classmethod
    def validate_field(cls, value: str) -> str:
        return _validate_identifier(value, "metric field")

    @field_validator("alias")
    @classmethod
    def validate_alias(cls, value: str | None) -> str | None:
        if value is None:
            return value
        return _validate_identifier(value, "metric alias")


class ChartEncodingSpec(BaseModel):
    x: XEncodingSpec
    y: list[YMetricSpec] = Field(default_factory=list, min_length=1, max_length=1)


class FilterSpec(BaseModel):
    field: str
    op: Literal["=", "!=", "in", "between", ">", ">=", "<", "<="] = "="
    value: Any

    @field_validator("field")
    @classmethod
    def validate_field(cls, value: str) -> str:
        return _validate_identifier(value, "filter field")

    @model_validator(mode="after")
    def validate_shape(self) -> "FilterSpec":
        if self.op == "in":
            if not isinstance(self.value, list) or len(self.value) == 0:
                raise ValueError("Filter operator 'in' requires a non-empty list value")
        if self.op == "between":
            if not isinstance(self.value, list) or len(self.value) != 2:
                raise ValueError("Filter operator 'between' requires exactly two values")
        return self


class SortSpec(BaseModel):
    field: str
    direction: Literal["asc", "desc"] = "desc"

    @field_validator("field")
    @classmethod
    def validate_field(cls, value: str) -> str:
        return _validate_identifier(value, "sort field")


class ChartSpecV1(BaseModel):
    version: Literal["v1"] = "v1"
    dataset_id: str | None = None
    table: str
    chart: ChartVisualSpec = Field(default_factory=ChartVisualSpec)
    encoding: ChartEncodingSpec
    filters: list[FilterSpec] = Field(default_factory=list)
    sort: list[SortSpec] = Field(default_factory=list)
    limit: int = 20

    @field_validator("dataset_id")
    @classmethod
    def validate_dataset_id(cls, value: str | None) -> str | None:
        if value is None:
            return value
        if not DATASET_ID_RE.match(value):
            raise ValueError(f"Invalid dataset_id: {value}")
        return value

    @field_validator("table")
    @classmethod
    def validate_table(cls, value: str) -> str:
        return _validate_identifier(value, "table name")

    @field_validator("limit")
    @classmethod
    def validate_limit(cls, value: int) -> int:
        if value < 1:
            raise ValueError("limit must be >= 1")
        if value > 5000:
            raise ValueError("limit must be <= 5000")
        return value


class ChartPreviewRequest(BaseModel):
    chart_spec: ChartSpecV1
    debug: bool = False


class ChartPreviewResponse(BaseModel):
    chart_spec: ChartSpecV1
    columns: list[str]
    rows: list[dict[str, Any]]
    meta: dict[str, Any]
