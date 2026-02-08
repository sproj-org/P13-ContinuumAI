from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Literal, Optional, Union

from pydantic import BaseModel, ConfigDict, Field, model_validator


class PhysicalType(str, Enum):
    STRING = "string"
    INT = "int"
    FLOAT = "float"
    BOOLEAN = "boolean"
    DATE = "date"
    DATETIME = "datetime"
    UNKNOWN = "unknown"


class LogicalType(str, Enum):
    NUMERIC = "numeric"
    CATEGORICAL = "categorical"
    DATETIME = "datetime"
    BOOLEAN = "boolean"
    TEXT = "text"


class Role(str, Enum):
    ID = "id"
    DIMENSION = "dimension"
    MEASURE = "measure"
    DATETIME = "datetime"
    BOOLEAN = "boolean"
    TEXT = "text"


class CardinalityBucket(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class TopKItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    value: str
    count: int = Field(ge=0)
    percent: float = Field(ge=0.0, le=1.0)


class NumericStats(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: Literal["numeric"] = Field(default="numeric")
    null_count: int = Field(ge=0)
    min: Optional[float] = None
    max: Optional[float] = None
    mean: Optional[float] = None
    stddev: Optional[float] = None
    p05: Optional[float] = None
    p50: Optional[float] = None
    p95: Optional[float] = None
    zero_count: int = Field(ge=0)


class CategoricalStats(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: Literal["categorical"] = Field(default="categorical")
    null_count: int = Field(ge=0)
    distinct_count: int = Field(ge=0)
    top_k: List[TopKItem] = Field(default_factory=list)


class DatetimeStats(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: Literal["datetime"] = Field(default="datetime")
    null_count: int = Field(ge=0)
    min: Optional[str] = None
    max: Optional[str] = None
    distinct_days: Optional[int] = Field(default=None, ge=0)


class BooleanStats(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: Literal["boolean"] = Field(default="boolean")
    true_count: int = Field(ge=0)
    false_count: int = Field(ge=0)
    null_count: int = Field(ge=0)


class TextStats(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: Literal["text"] = Field(default="text")
    min_len: Optional[int] = Field(default=None, ge=0)
    max_len: Optional[int] = Field(default=None, ge=0)
    avg_len: Optional[float] = Field(default=None, ge=0)
    sample_values: List[str] = Field(default_factory=list)
    top_k: List[TopKItem] = Field(default_factory=list)


StatsUnion = Union[NumericStats, CategoricalStats, DatetimeStats, BooleanStats, TextStats]


class ColumnProfile(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    physical_type: PhysicalType
    logical_type: LogicalType
    base_role: Role
    effective_role: Role

    row_count: int = Field(ge=0)
    distinct_count: int = Field(ge=0)
    null_count: int = Field(ge=0)
    null_fraction: float = Field(ge=0.0, le=1.0)
    cardinality_bucket: CardinalityBucket
    sample_values: List[str] = Field(default_factory=list)

    stats: Optional[StatsUnion] = None

    is_unique: bool
    base_needs_review: bool = False
    base_issues: List[str] = Field(default_factory=list)

    agent_meta: Dict[str, Any] = Field(default_factory=dict)
    llm_meta: Dict[str, Any] = Field(default_factory=dict)
    effective_meta: Dict[str, Any] = Field(default_factory=dict)


class DatasetProfile(BaseModel):
    model_config = ConfigDict(extra="forbid")

    dataset_name: str
    schema_name: Optional[str] = None
    table_name: Optional[str] = None
    row_count: int = Field(ge=0)
    column_count: int = Field(ge=0)
    profiled_at: datetime
    columns: List[ColumnProfile] = Field(default_factory=list)

    dataset_meta: Dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_column_count(self) -> "DatasetProfile":
        if self.column_count != len(self.columns):
            raise ValueError("column_count must match len(columns)")
        return self
