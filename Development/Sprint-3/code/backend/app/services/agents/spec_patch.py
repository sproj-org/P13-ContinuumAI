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
    for raw_part in parts[:-1]:
        if raw_part.isdigit():
            index = int(raw_part)
            if not isinstance(cursor, list):
                raise HTTPException(status_code=400, detail=f"Patch path '{path}' is invalid.")
            while len(cursor) <= index:
                cursor.append({})
            cursor = cursor[index]
            continue

        if not isinstance(cursor, dict):
            raise HTTPException(status_code=400, detail=f"Patch path '{path}' is invalid.")
        if raw_part not in cursor or cursor[raw_part] is None:
            cursor[raw_part] = {}
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


def _delete_by_path(target: dict[str, Any], path: str) -> None:
    if path not in _UNSET_ALLOWED:
        raise HTTPException(status_code=400, detail=f"Unsupported unset path: '{path}'")
    target.pop(path, None)


def _add_by_path(target: dict[str, Any], path: str, value: Any) -> None:
    if not _is_allowed_path(path):
        raise HTTPException(status_code=400, detail=f"Unsupported add path: '{path}'")

    existing = target.get(path)
    if path in {"filters", "sort", "encoding.y"}:
        current = existing if isinstance(existing, list) else []
        incoming = value if isinstance(value, list) else [value]
        target[path] = [*current, *incoming]
        return

    if isinstance(existing, dict) and isinstance(value, dict):
        target[path] = {**existing, **value}
        return

    target[path] = value


def apply_patch(last_spec: ChartSpecV1, patch: ChartSpecPatch) -> ChartSpecV1:
    payload = last_spec.model_dump(mode="json")

    for path, value in patch.set.items():
        _set_by_path(payload, path, value)

    for path in patch.unset:
        _delete_by_path(payload, path)

    for path, value in patch.add.items():
        _add_by_path(payload, path, value)

    return ChartSpecV1.model_validate(payload)
