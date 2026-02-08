"""Profiler runner for marts datasets with strict schema validation."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, List

from sqlalchemy.engine import Engine

from services.profiling.base_profiler import create_db_engine, profile_dataset_base
from services.profiling.profile_schema import DatasetProfile, Role
from services.profiling.stats_calculator import compute_role_aware_stats

DEFAULT_SCHEMA = "marts"
DEFAULT_TABLES = ("mart_sales", "mart_customers", "mart_stores")
DEFAULT_OUTPUT_DIR = "out"
PROFILER_VERSION = "sprint3-profiler-mvp-v1"


def _parse_tables(raw_tables: str | None) -> List[str]:
    if not raw_tables:
        return list(DEFAULT_TABLES)

    tables = [table.strip() for table in raw_tables.split(",") if table.strip()]
    if not tables:
        return list(DEFAULT_TABLES)

    # Preserve order while removing duplicates.
    return list(dict.fromkeys(tables))


def _build_profile_metadata(
    schema_name: str,
    table_name: str,
    columns: List[dict],
) -> dict:
    generated_at = datetime.now(timezone.utc).isoformat()
    dataset_key = f"{schema_name}.{table_name}"

    return {
        "dataset_key": dataset_key,
        "generated_at": generated_at,
        "profiler_version": PROFILER_VERSION,
        "columns_map": {column["name"]: column for column in columns},
    }


def _profile_single_dataset(
    engine: Engine,
    schema_name: str,
    table_name: str,
    sample_n: int,
) -> DatasetProfile:
    table, profile_dict = profile_dataset_base(
        engine=engine,
        schema=schema_name,
        table_name=table_name,
        sample_n=sample_n,
    )

    profiled_columns = compute_role_aware_stats(
        engine=engine,
        table=table,
        columns=profile_dict["columns"],
        top_k_limit=10,
    )

    profile_dict["columns"] = profiled_columns
    profile_dict["schema_name"] = schema_name
    profile_dict["table_name"] = table_name

    dataset_meta = dict(profile_dict.get("dataset_meta") or {})
    dataset_meta.update(
        _build_profile_metadata(
            schema_name=schema_name,
            table_name=table_name,
            columns=profiled_columns,
        )
    )
    profile_dict["dataset_meta"] = dataset_meta

    return DatasetProfile.model_validate(profile_dict)


def _write_profile(profile: DatasetProfile, output_dir: Path) -> Path:
    table_name = profile.table_name or profile.dataset_name
    destination = output_dir / f"{table_name}_profile.json"
    destination.parent.mkdir(parents=True, exist_ok=True)

    destination.write_text(
        json.dumps(profile.model_dump(mode="json", exclude_none=True), indent=2),
        encoding="utf-8",
    )
    return destination


def _role_counts(profile: DatasetProfile) -> dict[str, int]:
    counts = {role.value: 0 for role in Role}
    for column in profile.columns:
        counts[column.effective_role.value] += 1
    return counts


def _dataset_key(profile: DatasetProfile) -> str:
    meta_key = profile.dataset_meta.get("dataset_key")
    if isinstance(meta_key, str) and meta_key:
        return meta_key

    if profile.schema_name and profile.table_name:
        return f"{profile.schema_name}.{profile.table_name}"

    return profile.dataset_name


def profile_datasets(
    schema_name: str,
    table_names: Iterable[str],
    output_dir: Path,
    sample_n: int,
) -> int:
    failures: List[tuple[str, str]] = []

    try:
        engine = create_db_engine()
    except Exception as exc:
        print(f"[ERROR] Failed to initialize DATABASE_URL engine: {exc}")
        return 1

    try:
        for table_name in table_names:
            key = f"{schema_name}.{table_name}"
            try:
                profile = _profile_single_dataset(
                    engine=engine,
                    schema_name=schema_name,
                    table_name=table_name,
                    sample_n=sample_n,
                )
                destination = _write_profile(profile, output_dir)

                counts = _role_counts(profile)
                print(
                    f"{_dataset_key(profile)} | row_count={profile.row_count} | "
                    f"column_count={profile.column_count} | "
                    f"role_counts(#measure={counts['measure']}/#dimension={counts['dimension']}/"
                    f"#id={counts['id']}/#datetime={counts['datetime']}/"
                    f"#boolean={counts['boolean']}/#text={counts['text']}) | "
                    f"output={destination}"
                )
            except Exception as exc:
                print(f"[ERROR] {key}: {exc}")
                failures.append((key, str(exc)))
    finally:
        engine.dispose()

    if failures:
        print("Failed datasets:")
        for dataset_key, error_text in failures:
            print(f"- {dataset_key}: {error_text}")
        return 1

    return 0


def main() -> None:
    parser = argparse.ArgumentParser(description="Run profiler for marts datasets")
    parser.add_argument("--schema", default=DEFAULT_SCHEMA)
    parser.add_argument(
        "--tables",
        default=",".join(DEFAULT_TABLES),
        help="Comma-separated table names",
    )
    parser.add_argument("--output-dir", default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--sample-n", type=int, default=200)
    args = parser.parse_args()

    table_names = _parse_tables(args.tables)
    exit_code = profile_datasets(
        schema_name=args.schema,
        table_names=table_names,
        output_dir=Path(args.output_dir),
        sample_n=args.sample_n,
    )
    raise SystemExit(exit_code)


if __name__ == "__main__":
    main()
