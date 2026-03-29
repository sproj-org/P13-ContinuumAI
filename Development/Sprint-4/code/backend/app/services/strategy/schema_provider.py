"""Dataset schema provider backed by profiling JSON artifacts."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from app.core.mart_registry import is_supported_dataset, list_marts

OUT_DIR = Path(__file__).resolve().parents[3] / "out"


@dataclass
class DatasetSchemaSnapshot:
    dataset_id: str
    available_marts: set[str] = field(default_factory=set)
    mart_columns: dict[str, set[str]] = field(default_factory=dict)
    unavailable_marts: dict[str, str] = field(default_factory=dict)
    notes: list[str] = field(default_factory=list)


def _load_mart_columns(profile_path: Path) -> set[str]:
    with profile_path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    columns = payload.get("columns", [])
    if not isinstance(columns, list):
        return set()
    names = {
        item.get("name")
        for item in columns
        if isinstance(item, dict) and isinstance(item.get("name"), str) and item.get("name").strip()
    }
    return {name for name in names if isinstance(name, str)}


def load_dataset_schema(dataset_id: str) -> DatasetSchemaSnapshot:
    if not is_supported_dataset(dataset_id):
        raise KeyError(f"Unknown dataset_id '{dataset_id}'")

    snapshot = DatasetSchemaSnapshot(dataset_id=dataset_id)
    for mart in list_marts(dataset_id):
        mart_id = str(mart.get("id"))
        profile_file = str(mart.get("profile_file", "")).strip()
        if not profile_file:
            snapshot.unavailable_marts[mart_id] = "missing_profile_file_mapping"
            snapshot.notes.append(f"{mart_id}: missing profile_file in mart registry")
            continue

        profile_path = OUT_DIR / profile_file
        if not profile_path.exists():
            snapshot.unavailable_marts[mart_id] = "missing_profile_json"
            snapshot.notes.append(f"{mart_id}: profile JSON not found at {profile_path.name}")
            continue

        try:
            columns = _load_mart_columns(profile_path)
        except json.JSONDecodeError:
            snapshot.unavailable_marts[mart_id] = "invalid_profile_json"
            snapshot.notes.append(f"{mart_id}: profile JSON is invalid")
            continue
        except OSError:
            snapshot.unavailable_marts[mart_id] = "profile_read_error"
            snapshot.notes.append(f"{mart_id}: profile JSON could not be read")
            continue

        snapshot.available_marts.add(mart_id)
        snapshot.mart_columns[mart_id] = columns

    return snapshot
