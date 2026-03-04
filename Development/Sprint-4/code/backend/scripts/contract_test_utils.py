"""Shared helpers for backend API contract test scripts."""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from typing import Any

import httpx

NON_FINITE_STRINGS = {"inf", "+inf", "-inf", "infinity", "+infinity", "-infinity", "nan"}
NUMERIC_PHYSICAL_TYPES = {"int", "float", "decimal", "numeric", "double", "real", "bigint", "smallint"}


class ContractTestError(RuntimeError):
    """Raised when a contract assertion fails."""


@dataclass
class ApiResult:
    status_code: int
    payload: Any
    text: str


def assert_json_safe(obj: Any, path: str = "$") -> None:
    """Fail if any non-finite float or string token appears in payload."""
    if isinstance(obj, dict):
        for key, value in obj.items():
            assert_json_safe(value, f"{path}.{key}")
        return
    if isinstance(obj, list):
        for idx, item in enumerate(obj):
            assert_json_safe(item, f"{path}[{idx}]")
        return
    if isinstance(obj, tuple):
        for idx, item in enumerate(obj):
            assert_json_safe(item, f"{path}({idx})")
        return
    if isinstance(obj, float):
        if not math.isfinite(obj):
            raise ContractTestError(f"{path}: non-finite float value {obj!r}")
        return
    if isinstance(obj, str):
        if obj.strip().lower() in NON_FINITE_STRINGS:
            raise ContractTestError(f"{path}: non-finite string token {obj!r}")


def assert_json_serializable(obj: Any, path: str = "$") -> None:
    try:
        json.dumps(obj, allow_nan=False)
    except (TypeError, ValueError) as exc:
        raise ContractTestError(f"{path}: payload is not strict-JSON serializable: {exc}") from exc


def ensure_required_keys(payload: Any, required: set[str], path: str) -> None:
    if not isinstance(payload, dict):
        raise ContractTestError(f"{path}: expected JSON object, got {type(payload).__name__}")
    missing = sorted(required - set(payload.keys()))
    if missing:
        raise ContractTestError(f"{path}: missing required keys: {', '.join(missing)}")


def request_json(
    client: httpx.Client,
    method: str,
    path: str,
    *,
    expected_status: int = 200,
    json_body: dict[str, Any] | None = None,
) -> ApiResult:
    response = client.request(method=method.upper(), url=path, json=json_body)
    text = response.text
    try:
        payload = response.json()
    except json.JSONDecodeError:
        payload = None

    result = ApiResult(status_code=response.status_code, payload=payload, text=text)
    if response.status_code != expected_status:
        detail = payload if payload is not None else text
        raise ContractTestError(
            f"{method.upper()} {path} returned {response.status_code}, expected {expected_status}. "
            f"Response: {detail}"
        )
    if payload is None:
        raise ContractTestError(f"{method.upper()} {path} did not return valid JSON.")
    return result


def pick_chart_request(
    table_name: str,
    profile: dict[str, Any],
) -> dict[str, Any]:
    columns = profile.get("columns", [])
    if not isinstance(columns, list) or not columns:
        raise ContractTestError(f"Table '{table_name}' profile has no columns")

    x_axis: str | None = None
    y_axis: str | None = None
    agg_fn = "sum"

    for column in columns:
        if not isinstance(column, dict):
            continue
        name = column.get("name")
        if not isinstance(name, str) or not name:
            continue
        role = str(column.get("effective_role", column.get("base_role", ""))).lower()
        physical_type = str(column.get("physical_type", "")).lower()

        if x_axis is None and role in {"dimension", "datetime", "boolean", "id", "text"}:
            x_axis = name
        if y_axis is None and role == "measure" and physical_type in NUMERIC_PHYSICAL_TYPES:
            y_axis = name

    if x_axis and y_axis:
        agg_fn = "sum"
    else:
        # Fallback to count over any available column so legacy chart-data endpoint can still be exercised.
        first_name = columns[0].get("name")
        if not isinstance(first_name, str) or not first_name:
            raise ContractTestError(f"Table '{table_name}' profile does not expose valid column names")
        x_axis = x_axis or first_name
        y_axis = y_axis or first_name
        agg_fn = "count"

    return {
        "table_name": table_name,
        "x_axis": x_axis,
        "y_axis": y_axis,
        "aggregation_fn": agg_fn,
        "limit": 20,
    }


def find_first_column_name(profile: dict[str, Any]) -> str:
    columns = profile.get("columns", [])
    if not isinstance(columns, list) or not columns:
        raise ContractTestError("Profile has no columns.")
    for column in columns:
        if isinstance(column, dict):
            name = column.get("name")
            if isinstance(name, str) and name:
                return name
    raise ContractTestError("No valid column name found in profile.")
