"""Verify generated gold profiles for schema parity, sanity, and Pydantic validity."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Iterable

BASE_DIR = Path(__file__).resolve().parents[1]
OUT_DIR = BASE_DIR / "out"
FRONTEND_DIR = BASE_DIR.parent / "frontend"
SCAN_ROOTS = [BASE_DIR, FRONTEND_DIR]

if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from services.profiling.compiled_runtime import get_profile_model_class

VALID_STATS_KINDS = {"numeric", "categorical", "datetime", "boolean", "text"}
NUMERIC_PHYSICAL_TYPES = {"int", "float", "decimal"}
ID_LIKE_RE = re.compile(r"(^id$|_id$|^.*_code$|^code$|^.*_key$)", re.IGNORECASE)
FLAG_LIKE_RE = re.compile(r"(_flag|flag|^is_|^has_|indicator)", re.IGNORECASE)
OLD_MART_IDS = tuple(f"mart_{suffix}" for suffix in ("sales", "customers", "stores"))
NON_FINITE_SAMPLE_TOKENS = {"inf", "+inf", "-inf", "infinity", "+infinity", "-infinity", "nan"}

EXCLUDED_SCAN_DIRS = {
    ".git",
    ".venv",
    "node_modules",
    ".next",
    ".npm-cache",
    "__pycache__",
}
SKIPPED_SCAN_SUFFIXES = {
    ".png",
    ".jpg",
    ".jpeg",
    ".gif",
    ".ico",
    ".pdf",
    ".docx",
    ".zip",
    ".pyc",
    ".pyd",
    ".dll",
    ".exe",
}


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def is_non_finite_sample_value(value: object) -> bool:
    if isinstance(value, float):
        return value != value or value in (float("inf"), float("-inf"))
    if isinstance(value, str):
        return value.strip().lower() in NON_FINITE_SAMPLE_TOKENS
    return False


def find_reference_profile() -> Path:
    preferred = OUT_DIR / "mart_sales_profile.json"
    if preferred.exists():
        return preferred

    candidates = sorted(OUT_DIR.glob("mart_*_profile.json"))
    if candidates:
        return candidates[0]

    raise FileNotFoundError(
        f"No mart reference profile found in {OUT_DIR} (expected mart_sales_profile.json)."
    )


def required_keys_from_reference(reference_profile: dict) -> tuple[set[str], set[str]]:
    if "columns" not in reference_profile or not reference_profile["columns"]:
        raise ValueError("Reference profile does not contain non-empty 'columns'.")

    top_level_required = set(reference_profile.keys())
    column_required = set(reference_profile["columns"][0].keys())
    return top_level_required, column_required


def verify_profile_schema(
    profile_path: Path,
    profile: dict,
    top_level_required: set[str],
    column_required: set[str],
    profile_model,
) -> list[str]:
    errors: list[str] = []
    prefix = str(profile_path)

    missing_top = sorted(top_level_required - set(profile.keys()))
    if missing_top:
        errors.append(f"{prefix}: missing top-level keys: {', '.join(missing_top)}")

    columns = profile.get("columns")
    if not isinstance(columns, list):
        errors.append(f"{prefix}: 'columns' is not a list")
        return errors

    for idx, column in enumerate(columns):
        if not isinstance(column, dict):
            errors.append(f"{prefix}: columns[{idx}] is not an object")
            continue

        missing_column_keys = sorted(column_required - set(column.keys()))
        if missing_column_keys:
            errors.append(
                f"{prefix}: columns[{idx}] missing keys: {', '.join(missing_column_keys)}"
            )

        stats = column.get("stats")
        if isinstance(stats, dict):
            stats_kind = stats.get("kind")
            if stats_kind not in VALID_STATS_KINDS:
                errors.append(
                    f"{prefix}: columns[{idx}] invalid stats.kind '{stats_kind}' "
                    f"(expected one of {sorted(VALID_STATS_KINDS)})"
                )

        name = str(column.get("name", ""))
        physical_type = str(column.get("physical_type", "")).lower()
        logical_type = str(column.get("logical_type", "")).lower()
        role = str(column.get("effective_role", ""))
        distinct_count = int(column.get("distinct_count", 0) or 0)
        cardinality_bucket = str(column.get("cardinality_bucket", "")).lower()
        id_like = bool(ID_LIKE_RE.search(name))
        flag_like = bool(FLAG_LIKE_RE.search(name))
        low_cardinality_int_dimension = (
            physical_type == "int"
            and role == "dimension"
            and (distinct_count <= 50 or cardinality_bucket == "low")
        )
        boolean_like_dimension = (
            flag_like
            and role == "dimension"
            and physical_type in NUMERIC_PHYSICAL_TYPES
            and logical_type in {"boolean", "categorical", "numeric"}
        )

        if (
            physical_type in NUMERIC_PHYSICAL_TYPES
            and role != "measure"
            and not id_like
            and not low_cardinality_int_dimension
            and not boolean_like_dimension
        ):
            errors.append(
                f"{prefix}: columns[{idx}] '{name}' has numeric physical_type "
                f"'{physical_type}' but effective_role='{role}' (expected 'measure')"
            )

        if role == "measure" and physical_type not in NUMERIC_PHYSICAL_TYPES:
            errors.append(
                f"{prefix}: columns[{idx}] '{name}' has effective_role='measure' but "
                f"non-numeric physical_type='{physical_type}'"
            )

        if physical_type in NUMERIC_PHYSICAL_TYPES:
            sample_values = column.get("sample_values")
            if isinstance(sample_values, list):
                bad_samples = [sample for sample in sample_values if is_non_finite_sample_value(sample)]
                if bad_samples:
                    errors.append(
                        f"{prefix}: column '{name}' has non-finite sample_values {bad_samples}"
                    )

    try:
        profile_model.model_validate(profile)
    except Exception as exc:
        errors.append(f"{prefix}: Pydantic validation failed: {exc}")

    return errors


def _iter_scan_files(root: Path) -> Iterable[Path]:
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        if any(part in EXCLUDED_SCAN_DIRS for part in path.parts):
            continue
        if path.name == "check_no_hardcoded_marts.py":
            continue
        if path.suffix.lower() in SKIPPED_SCAN_SUFFIXES:
            continue
        yield path


def find_hardcoded_old_marts() -> list[str]:
    errors: list[str] = []
    allowed_legacy_files = {p.resolve() for p in OUT_DIR.glob("mart_*_profile.json")}
    pattern = re.compile(
        r"\b(" + "|".join(re.escape(mart_id) for mart_id in OLD_MART_IDS) + r")\b"
    )

    for scan_root in SCAN_ROOTS:
        if not scan_root.exists():
            continue

        for path in _iter_scan_files(scan_root):
            if path.resolve() in allowed_legacy_files:
                continue

            try:
                text = path.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                continue
            except OSError as exc:
                errors.append(f"{path}: failed to read file ({exc})")
                continue

            for line_no, line in enumerate(text.splitlines(), start=1):
                match = pattern.search(line)
                if match:
                    errors.append(
                        f"{path}:{line_no}: found hardcoded legacy mart id '{match.group(1)}'"
                    )

    return errors


def main() -> int:
    errors: list[str] = []

    try:
        reference_path = find_reference_profile()
        reference_profile = load_json(reference_path)
        top_level_required, column_required = required_keys_from_reference(reference_profile)
    except Exception as exc:
        print(f"[ERROR] Failed to load reference profile: {exc}")
        return 1

    gold_profiles = sorted(OUT_DIR.glob("gold_*_profile.json"))
    if not gold_profiles:
        print(f"[ERROR] No generated gold profiles found in {OUT_DIR}.")
        return 1

    try:
        profile_model = get_profile_model_class()
    except Exception as exc:
        print(f"[ERROR] Failed to load existing profile Pydantic model: {exc}")
        return 1

    for profile_path in gold_profiles:
        try:
            profile = load_json(profile_path)
        except Exception as exc:
            errors.append(f"{profile_path}: failed to parse JSON ({exc})")
            continue

        errors.extend(
            verify_profile_schema(
                profile_path=profile_path,
                profile=profile,
                top_level_required=top_level_required,
                column_required=column_required,
                profile_model=profile_model,
            )
        )

    errors.extend(find_hardcoded_old_marts())

    if errors:
        print("[ERROR] Gold profile verification failed:")
        for item in errors:
            print(f" - {item}")
        return 1

    print("[OK] All gold profile checks passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
