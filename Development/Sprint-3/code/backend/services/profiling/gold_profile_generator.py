"""Generate gold mart profiles using the existing compiled profiling pipeline."""

from __future__ import annotations

import json
import math
import os
from pathlib import Path
from typing import Any

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

from app.core.mart_registry import DEFAULT_DATASET_ID, list_marts
from services.profiling.compiled_runtime import (
    get_profile_model_class,
    get_run_profiler_module,
)
from services.profiling.json_sanitize import sanitize_for_json

OUT_DIR = Path(__file__).resolve().parents[2] / "out"
NON_FINITE_STRINGS = {"inf", "+inf", "-inf", "infinity", "+infinity", "-infinity", "nan"}
NUMERIC_PHYSICAL_TYPES = {"int", "float", "decimal", "numeric", "double", "real", "bigint", "smallint"}
DEFAULT_PROFILE_SAMPLE_ROWS = 5000
DEFAULT_PROFILE_STATEMENT_TIMEOUT_MS = 30000
DEFAULT_PROFILE_MAX_RETRIES = 3
PROFILE_APP_NAME = "continuumai_profile_gen"


def _assert_gold_profile_filename(filename: str) -> None:
    if not filename.startswith("gold_") or not filename.endswith("_profile.json"):
        raise ValueError(
            f"Invalid gold profile filename '{filename}'. Expected gold_*_profile.json."
        )


def _env_int(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None or raw.strip() == "":
        return default
    try:
        value = int(raw.strip())
    except ValueError as exc:
        raise ValueError(f"Environment variable {name} must be an integer. Got: {raw!r}") from exc
    if value <= 0:
        raise ValueError(f"Environment variable {name} must be > 0. Got: {value}")
    return value


def _build_profile_engine(database_url: str, statement_timeout_ms: int) -> Engine:
    connect_args = {
        "options": (
            f"-c statement_timeout={statement_timeout_ms} "
            f"-c application_name={PROFILE_APP_NAME}"
        ),
    }
    return create_engine(
        database_url,
        pool_pre_ping=True,
        pool_recycle=180,
        pool_size=5,
        max_overflow=5,
        connect_args=connect_args,
    )


def _is_non_finite_sample_value(value: Any) -> bool:
    if isinstance(value, float):
        return not math.isfinite(value)
    if isinstance(value, str):
        return value.strip().lower() in NON_FINITE_STRINGS
    return False


def _clean_non_finite_numeric_samples(profile_dict: dict[str, Any]) -> None:
    columns = profile_dict.get("columns")
    if not isinstance(columns, list):
        return

    for column in columns:
        if not isinstance(column, dict):
            continue
        physical_type = str(column.get("physical_type", "")).lower()
        if physical_type not in NUMERIC_PHYSICAL_TYPES:
            continue

        sample_values = column.get("sample_values")
        if not isinstance(sample_values, list):
            continue

        cleaned_samples = [sample for sample in sample_values if not _is_non_finite_sample_value(sample)]
        column["sample_values"] = cleaned_samples


def _preflight_table_access(
    engine: Engine,
    schema_name: str,
    table_name: str,
    sample_rows: int,
) -> None:
    info_schema_query = text(
        """
        SELECT column_name
        FROM information_schema.columns
        WHERE table_schema = :schema_name
          AND table_name = :table_name
        ORDER BY ordinal_position
        """
    )
    sample_query = text(f'SELECT * FROM "{schema_name}"."{table_name}" LIMIT :sample_rows')

    with engine.connect() as conn:
        columns = conn.execute(
            info_schema_query,
            {"schema_name": schema_name, "table_name": table_name},
        ).fetchall()
        if not columns:
            raise RuntimeError(
                f"Table {schema_name}.{table_name} not found or has no columns in information_schema."
            )

        conn.execute(sample_query, {"sample_rows": sample_rows}).fetchmany(1)


def generate_gold_profiles(
    output_dir: Path | None = None,
    sample_n: int | None = None,
    dataset_id: str = DEFAULT_DATASET_ID,
) -> list[Path]:
    """
    Build/validate profiles for all registry marts and write out/gold_*_profile.json files.
    Uses DB-only profiling and retries per table with a fresh engine.
    """
    output_dir = output_dir or OUT_DIR
    output_dir.mkdir(parents=True, exist_ok=True)

    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        raise RuntimeError("DATABASE_URL is required for DB-only gold profile generation.")

    sample_rows = sample_n if sample_n is not None else _env_int(
        "PROFILE_SAMPLE_ROWS",
        DEFAULT_PROFILE_SAMPLE_ROWS,
    )
    statement_timeout_ms = _env_int(
        "PROFILE_STATEMENT_TIMEOUT_MS",
        DEFAULT_PROFILE_STATEMENT_TIMEOUT_MS,
    )
    max_retries = _env_int("PROFILE_MAX_RETRIES", DEFAULT_PROFILE_MAX_RETRIES)

    run_profiler = get_run_profiler_module()
    profile_model = get_profile_model_class()
    written_files: list[Path] = []

    for mart in list_marts(dataset_id):
        mart_id = str(mart["id"])
        schema_name = str(mart["schema"])
        profile_file = str(mart["profile_file"])
        table_fqn = f"{schema_name}.{mart_id}"
        _assert_gold_profile_filename(profile_file)

        last_error: Exception | None = None
        for attempt in range(1, max_retries + 1):
            engine: Engine | None = None
            try:
                engine = _build_profile_engine(database_url, statement_timeout_ms)
                _preflight_table_access(
                    engine=engine,
                    schema_name=schema_name,
                    table_name=mart_id,
                    sample_rows=sample_rows,
                )

                profile_obj = run_profiler._profile_single_dataset(
                    engine=engine,
                    schema_name=schema_name,
                    table_name=mart_id,
                    sample_n=sample_rows,
                )

                profile_dict: dict[str, Any] = profile_obj.model_dump(
                    mode="json",
                    exclude_none=True,
                )
                _clean_non_finite_numeric_samples(profile_dict)
                profile_dict = sanitize_for_json(profile_dict)

                profile_model.model_validate(profile_dict)

                destination = output_dir / profile_file
                destination.write_text(
                    json.dumps(profile_dict, indent=2),
                    encoding="utf-8",
                )
                written_files.append(destination)
                print(
                    f"[OK] dataset_id={dataset_id} mart_id={mart_id} table={table_fqn} "
                    f"attempt={attempt}/{max_retries} wrote={destination.name}"
                )
                last_error = None
                break
            except Exception as exc:
                last_error = exc
                print(
                    f"[WARN] dataset_id={dataset_id} mart_id={mart_id} table={table_fqn} "
                    f"attempt={attempt}/{max_retries} error={type(exc).__name__}: {exc}"
                )
            finally:
                if engine is not None:
                    engine.dispose()

        if last_error is not None:
            raise RuntimeError(
                f"Profile generation failed after {max_retries} attempts for "
                f"dataset_id={dataset_id}, mart_id={mart_id}, table={table_fqn}: "
                f"{type(last_error).__name__}: {last_error}"
            ) from last_error

    return written_files

