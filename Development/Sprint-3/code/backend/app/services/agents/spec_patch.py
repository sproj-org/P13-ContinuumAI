"""Safe patch application for follow-up chart edits."""

from __future__ import annotations

from typing import Any

from fastapi import HTTPException

from app.services.agents.chat_models import ChartSpecPatch
from app.services.charts.models import ChartSpecV1

_ALLOWED_PREFIXES = (
    "chart.type",
    "encoding.x.field",
    "encoding.y",
    "filters",
    "sort",
    "limit",
)

_UNSET_ALLOWED = {"filters", "sort"}


def _is_allowed_path(path: str) -> bool:
    return any(path == prefix or path.startswith(prefix + ".") for prefix in _ALLOWED_PREFIXES)


def _set_by_path(target: dict[str, Any], path: str, value: Any) -> None:
    if not _is_allowed_path(path):
        raise HTTPException(status_code=400, detail=f"Unsupported patch path: '{path}'")

    parts = path.split(".")
    cursor: Any = target
    for index, raw_part in enumerate(parts[:-1]):
        next_part = parts[index + 1]
        if raw_part.isdigit():
            index = int(raw_part)
            if not isinstance(cursor, list):
                raise HTTPException(status_code=400, detail=f"Patch path '{path}' is invalid.")
            while len(cursor) <= index:
                cursor.append([] if next_part.isdigit() else {})
            cursor = cursor[index]
            continue

        if not isinstance(cursor, dict):
            raise HTTPException(status_code=400, detail=f"Patch path '{path}' is invalid.")
        if raw_part not in cursor or cursor[raw_part] is None:
            cursor[raw_part] = [] if next_part.isdigit() else {}
        cursor = cursor[raw_part]

    last = parts[-1]
    if last.isdigit():
        index = int(last)
        if not isinstance(cursor, list):
            raise HTTPException(status_code=400, detail=f"Patch path '{path}' is invalid.")
        while len(cursor) <= index:
            cursor.append(None)
        cursor[index] = value
    else:
        if not isinstance(cursor, dict):
            raise HTTPException(status_code=400, detail=f"Patch path '{path}' is invalid.")
        cursor[last] = value


def _get_by_path(target: dict[str, Any], path: str) -> Any:
    cursor: Any = target
    for raw_part in path.split("."):
        if raw_part.isdigit():
            index = int(raw_part)
            if not isinstance(cursor, list) or index >= len(cursor):
                return None
            cursor = cursor[index]
            continue
        if not isinstance(cursor, dict) or raw_part not in cursor:
            return None
        cursor = cursor[raw_part]
    return cursor


def _delete_by_path(target: dict[str, Any], path: str) -> None:
    if path not in _UNSET_ALLOWED:
        raise HTTPException(status_code=400, detail=f"Unsupported unset path: '{path}'")
    target.pop(path, None)


def _add_by_path(target: dict[str, Any], path: str, value: Any) -> None:
    if not _is_allowed_path(path):
        raise HTTPException(status_code=400, detail=f"Unsupported add path: '{path}'")

    existing = _get_by_path(target, path)
    if path in {"filters", "sort", "encoding.y"}:
        if existing is not None and not isinstance(existing, list):
            raise HTTPException(status_code=400, detail=f"Patch add path '{path}' must reference a list.")
        current = list(existing) if isinstance(existing, list) else []
        incoming = value if isinstance(value, list) else [value]
        _set_by_path(target, path, [*current, *incoming])
        return

    if isinstance(existing, dict) and isinstance(value, dict):
        _set_by_path(target, path, {**existing, **value})
        return

    _set_by_path(target, path, value)


def apply_patch(last_spec: ChartSpecV1, patch: ChartSpecPatch) -> ChartSpecV1:
    payload = last_spec.model_dump(mode="json")

    for path, value in patch.set.items():
        _set_by_path(payload, path, value)

    for path in patch.unset:
        _delete_by_path(payload, path)

    for path, value in patch.add.items():
        _add_by_path(payload, path, value)

    return ChartSpecV1.model_validate(payload)
