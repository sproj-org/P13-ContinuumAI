"""Core profiling utilities for reflected metadata and batched core metrics."""

from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List, Tuple
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from sqlalchemy import MetaData, Table, case, create_engine, func, select, text
from sqlalchemy import types as satypes
from sqlalchemy.engine import Engine
from sqlalchemy.exc import NoSuchModuleError

from services.profiling.profile_schema import CardinalityBucket, LogicalType, PhysicalType, Role

KNOWN_ID_COLUMNS = {
    "line_id",
    "transaction_id",
    "customer_id",
    "store_id",
    "sku_id",
    "product_id",
    "salesperson_id",
    "promo_id",
    "return_id",
}

MEASURE_KEYWORDS = (
    "amount",
    "sales",
    "revenue",
    "price",
    "cost",
    "margin",
    "qty",
    "quantity",
    "units",
    "discount",
    "refund",
    "rate",
    "pct",
    "percent",
    "total",
    "avg",
    "order",
    "orders",
    "count",
    "counts",
    "num",
    "number",
    "day",
    "days",
    "customer",
    "customers",
    "item",
    "items",
    "line_items",
    "lines",
    "session",
    "sessions",
    "tenure",
    "recency",
    "visit",
    "visits",
)

SMALL_TABLE_THRESHOLD = 500
NUMERIC_DIMENSION_HINTS = ("code", "tier", "level", "bucket", "flag")


def normalize_database_url(raw_url: str) -> str:
    """Normalize DB URL to psycopg driver and enforce sslmode=require."""
    db_url = (raw_url or "").strip()
    if not db_url:
        raise ValueError("DATABASE_URL is required")

    if db_url.startswith("postgresql://"):
        db_url = db_url.replace("postgresql://", "postgresql+psycopg://", 1)

    parsed = urlsplit(db_url)
    query_params = dict(parse_qsl(parsed.query, keep_blank_values=True))
    if "sslmode" not in query_params:
        query_params["sslmode"] = "require"

    normalized_query = urlencode(query_params)
    return urlunsplit((parsed.scheme, parsed.netloc, parsed.path, normalized_query, parsed.fragment))


def create_db_engine(database_url: str | None = None) -> Engine:
    """Create SQLAlchemy engine from DATABASE_URL with resilient driver fallback."""
    raw = database_url or os.getenv("DATABASE_URL", "")
    normalized = normalize_database_url(raw)

    try:
        return create_engine(normalized, future=True, pool_pre_ping=True)
    except (NoSuchModuleError, ModuleNotFoundError):
        # Environment fallback for setups that still ship psycopg2 only.
        if normalized.startswith("postgresql+psycopg://"):
            fallback = normalized.replace("postgresql+psycopg://", "postgresql+psycopg2://", 1)
            return create_engine(fallback, future=True, pool_pre_ping=True)
        raise


def reflect_table(engine: Engine, schema: str = "marts", table_name: str = "mart_sales") -> Table:
    """Reflect target table with explicit schema."""
    metadata = MetaData()
    return Table(table_name, metadata, schema=schema, autoload_with=engine)


def map_physical_type(sqlalchemy_type: Any) -> PhysicalType:
    """Map SQLAlchemy reflected type to simplified physical type enum."""
    if isinstance(sqlalchemy_type, (satypes.DateTime, satypes.TIMESTAMP)):
        return PhysicalType.DATETIME
    if isinstance(sqlalchemy_type, satypes.Date):
        return PhysicalType.DATE
    if isinstance(sqlalchemy_type, satypes.Boolean):
        return PhysicalType.BOOLEAN
    if isinstance(sqlalchemy_type, (satypes.SmallInteger, satypes.Integer, satypes.BigInteger)):
        return PhysicalType.INT
    if isinstance(sqlalchemy_type, (satypes.Numeric, satypes.Float, satypes.DECIMAL, satypes.REAL, satypes.Double)):
        return PhysicalType.FLOAT
    if isinstance(
        sqlalchemy_type,
        (
            satypes.String,
            satypes.Text,
            satypes.Unicode,
            satypes.UnicodeText,
            satypes.CHAR,
            satypes.VARCHAR,
        ),
    ):
        return PhysicalType.STRING
    return PhysicalType.UNKNOWN


def is_numeric_physical(physical_type: PhysicalType) -> bool:
    return physical_type in {PhysicalType.INT, PhysicalType.FLOAT}


def infer_logical_type(
    physical_type: PhysicalType,
    sample_values: List[str],
    distinct_count: int,
    row_count: int,
) -> LogicalType:
    """Infer logical type from physical type and sampled values."""
    if is_numeric_physical(physical_type):
        return LogicalType.NUMERIC
    if physical_type in {PhysicalType.DATE, PhysicalType.DATETIME}:
        return LogicalType.DATETIME
    if physical_type == PhysicalType.BOOLEAN:
        return LogicalType.BOOLEAN

    if sample_values:
        avg_len = sum(len(v) for v in sample_values) / len(sample_values)
        distinct_ratio = (distinct_count / row_count) if row_count else 0.0
        if avg_len >= 40 and distinct_ratio >= 0.2:
            return LogicalType.TEXT

    return LogicalType.CATEGORICAL


def is_datetime_name(column_name: str) -> bool:
    col = column_name.lower()
    if "date" in col or "time" in col or "timestamp" in col:
        return True
    return col.endswith("_ts") or col == "ts" or col.startswith("ts_")


def is_id_name(column_name: str) -> bool:
    col = column_name.lower()
    return col.endswith("_id") or col in KNOWN_ID_COLUMNS


def is_boolean_name(column_name: str) -> bool:
    col = column_name.lower()
    return col.startswith("is_") or col.startswith("has_")


def has_measure_keyword(column_name: str) -> bool:
    col = column_name.lower()
    return any(keyword in col for keyword in MEASURE_KEYWORDS)


def has_numeric_dimension_hint(column_name: str) -> bool:
    col = column_name.lower()
    return any(hint in col for hint in NUMERIC_DIMENSION_HINTS)


def infer_role(
    column_name: str,
    physical_type: PhysicalType,
    logical_type: LogicalType,
    distinct_count: int,
    row_count: int,
) -> Role:
    """Infer business role using required precedence rules."""
    # 1) Datetime rule.
    if logical_type == LogicalType.DATETIME or is_datetime_name(column_name):
        return Role.DATETIME

    # 2) ID rule.
    if is_id_name(column_name):
        return Role.ID

    # 3) Boolean rule.
    if logical_type == LogicalType.BOOLEAN or is_boolean_name(column_name):
        return Role.BOOLEAN

    # 4) Measure rule with numeric semantics priority.
    if is_numeric_physical(physical_type):
        if has_measure_keyword(column_name):
            return Role.MEASURE

        if row_count < SMALL_TABLE_THRESHOLD:
            return Role.DIMENSION if has_numeric_dimension_hint(column_name) else Role.MEASURE

        return Role.DIMENSION if distinct_count <= 20 else Role.MEASURE

    # 6) Text/categorical fallback.
    if logical_type == LogicalType.TEXT:
        return Role.TEXT

    return Role.DIMENSION


def get_cardinality_bucket(distinct_count: int, row_count: int) -> CardinalityBucket:
    ratio = (distinct_count / row_count) if row_count else 0.0
    if ratio <= 0.05:
        return CardinalityBucket.LOW
    if ratio >= 0.8:
        return CardinalityBucket.HIGH
    return CardinalityBucket.MEDIUM


def get_row_null_distinct_counts(engine: Engine, table: Table) -> Tuple[int, Dict[str, Dict[str, int]]]:
    """Batch query row_count, null_count, and distinct_count for all columns."""
    select_exprs = [func.count().label("row_count")]

    for col in table.columns:
        select_exprs.append(func.sum(case((col.is_(None), 1), else_=0)).label(f"{col.name}__null"))
        select_exprs.append(func.count(func.distinct(col)).label(f"{col.name}__distinct"))

    stmt = select(*select_exprs).select_from(table)

    with engine.connect() as conn:
        result = conn.execute(stmt).mappings().one()

    row_count = int(result["row_count"] or 0)
    counts: Dict[str, Dict[str, int]] = {}

    for col in table.columns:
        counts[col.name] = {
            "null_count": int(result.get(f"{col.name}__null") or 0),
            "distinct_count": int(result.get(f"{col.name}__distinct") or 0),
        }

    return row_count, counts


def sample_rows(engine: Engine, table: Table, sample_n: int = 200) -> List[Dict[str, Any]]:
    """Sample rows once using TABLESAMPLE SYSTEM fallback to plain LIMIT."""
    sampled_rows: List[Dict[str, Any]] = []

    with engine.connect() as conn:
        if table.schema == "marts" and table.name == "mart_sales":
            try:
                sample_stmt = text(
                    "SELECT * FROM marts.mart_sales TABLESAMPLE SYSTEM (1) LIMIT :sample_n"
                )
                sampled_rows = [dict(row) for row in conn.execute(sample_stmt, {"sample_n": sample_n}).mappings().all()]
            except Exception:
                sampled_rows = []

        if not sampled_rows:
            fallback_stmt = select(table).limit(sample_n)
            sampled_rows = [dict(row) for row in conn.execute(fallback_stmt).mappings().all()]

    return sampled_rows


def _to_display_value(value: Any) -> str:
    if value is None:
        return ""
    if hasattr(value, "isoformat"):
        return str(value.isoformat())
    return str(value)


def derive_sample_values(
    sampled_rows: Iterable[Dict[str, Any]],
    column_names: Iterable[str],
    max_samples_per_column: int = 5,
) -> Dict[str, List[str]]:
    """Derive per-column sample values in Python from sampled rows."""
    samples: Dict[str, List[str]] = {name: [] for name in column_names}
    seen: Dict[str, set[str]] = {name: set() for name in column_names}

    for row in sampled_rows:
        for name in column_names:
            value = row.get(name)
            if value is None:
                continue
            display = _to_display_value(value)
            if display in seen[name]:
                continue
            seen[name].add(display)
            samples[name].append(display)

    for name in column_names:
        samples[name] = samples[name][:max_samples_per_column]

    return samples


def profile_dataset_base(
    engine: Engine,
    schema: str = "marts",
    table_name: str = "mart_sales",
    sample_n: int = 200,
) -> Tuple[Table, Dict[str, Any]]:
    """Build base dataset profile with batched core metrics and role inference."""
    table = reflect_table(engine=engine, schema=schema, table_name=table_name)

    row_count, count_map = get_row_null_distinct_counts(engine=engine, table=table)
    sampled_rows = sample_rows(engine=engine, table=table, sample_n=sample_n)
    sample_map = derive_sample_values(
        sampled_rows=sampled_rows,
        column_names=[col.name for col in table.columns],
        max_samples_per_column=5,
    )

    columns: List[Dict[str, Any]] = []

    for col in table.columns:
        physical_type = map_physical_type(col.type)
        null_count = count_map[col.name]["null_count"]
        distinct_count = count_map[col.name]["distinct_count"]
        column_samples = sample_map.get(col.name, [])

        logical_type = infer_logical_type(
            physical_type=physical_type,
            sample_values=column_samples,
            distinct_count=distinct_count,
            row_count=row_count,
        )
        role = infer_role(
            column_name=col.name,
            physical_type=physical_type,
            logical_type=logical_type,
            distinct_count=distinct_count,
            row_count=row_count,
        )

        column_profile = {
            "name": col.name,
            "physical_type": physical_type.value,
            "logical_type": logical_type.value,
            "base_role": role.value,
            "effective_role": role.value,
            "row_count": row_count,
            "distinct_count": distinct_count,
            "null_count": null_count,
            "null_fraction": (float(null_count) / float(row_count)) if row_count else 0.0,
            "cardinality_bucket": get_cardinality_bucket(distinct_count, row_count).value,
            "sample_values": column_samples,
            "stats": None,
            "is_unique": (null_count == 0 and distinct_count == row_count),
            "base_needs_review": False,
            "base_issues": [],
            "agent_meta": {},
            "llm_meta": {},
            "effective_meta": {},
        }

        columns.append(column_profile)

    dataset_profile = {
        "dataset_name": table_name,
        "schema_name": schema,
        "table_name": table_name,
        "row_count": row_count,
        "column_count": len(columns),
        "profiled_at": datetime.now(timezone.utc),
        "columns": columns,
        "dataset_meta": {},
    }

    return table, dataset_profile
