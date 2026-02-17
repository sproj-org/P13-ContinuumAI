"""Generate gold mart profiles using the existing compiled profiling pipeline."""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

from app.core.mart_registry import DEFAULT_DATASET_ID, list_marts
from services.profiling.compiled_runtime import (
    get_profile_model_class,
    get_run_profiler_module,
)
from services.profiling.json_sanitize import sanitize_for_json

OUT_DIR = Path(__file__).resolve().parents[2] / "out"
NON_FINITE_STRINGS = {"inf", "+inf", "-inf", "infinity", "+infinity", "-infinity", "nan"}
NUMERIC_PHYSICAL_TYPES = {"int", "float", "decimal", "numeric", "double", "real", "bigint", "smallint"}


def _assert_gold_profile_filename(filename: str) -> None:
    if not filename.startswith("gold_") or not filename.endswith("_profile.json"):
        raise ValueError(
            f"Invalid gold profile filename '{filename}'. Expected gold_*_profile.json."
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


def generate_gold_profiles(
    output_dir: Path | None = None,
    sample_n: int = 200,
    dataset_id: str = DEFAULT_DATASET_ID,
) -> list[Path]:
    """
    Build/validate profiles for all registry marts and write out/gold_*_profile.json files.
    Raises on the first failure.
    """
    output_dir = output_dir or OUT_DIR
    output_dir.mkdir(parents=True, exist_ok=True)

    run_profiler = get_run_profiler_module()
    profile_model = get_profile_model_class()
    engine = run_profiler.create_db_engine()

    written_files: list[Path] = []

    try:
        for mart in list_marts(dataset_id):
            mart_id = str(mart["id"])
            schema_name = str(mart["schema"])
            profile_file = str(mart["profile_file"])
            _assert_gold_profile_filename(profile_file)

            profile_obj = run_profiler._profile_single_dataset(
                engine=engine,
                schema_name=schema_name,
                table_name=mart_id,
                sample_n=sample_n,
            )

            profile_dict: dict[str, Any] = profile_obj.model_dump(
                mode="json",
                exclude_none=True,
            )
            _clean_non_finite_numeric_samples(profile_dict)
            profile_dict = sanitize_for_json(profile_dict)

            try:
                profile_model.model_validate(profile_dict)
            except Exception as exc:
                print(
                    f"[ERROR] Pydantic validation failed for {schema_name}.{mart_id}: {exc}",
                )
                raise

            destination = output_dir / profile_file
            destination.write_text(
                json.dumps(profile_dict, indent=2),
                encoding="utf-8",
            )
            written_files.append(destination)

    finally:
        engine.dispose()

    return written_files
