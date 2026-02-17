"""Local smoke check for profiling/chart endpoints serialization safety."""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


@dataclass
class ApiResult:
    status: int
    payload: Any


def _request_json(method: str, url: str, body: dict[str, Any] | None = None) -> ApiResult:
    data = None
    headers = {"Accept": "application/json"}
    if body is not None:
        data = json.dumps(body).encode("utf-8")
        headers["Content-Type"] = "application/json"

    request = Request(url=url, data=data, method=method.upper(), headers=headers)
    try:
        with urlopen(request, timeout=20) as response:
            text = response.read().decode("utf-8")
            payload = json.loads(text) if text else {}
            return ApiResult(status=response.status, payload=payload)
    except HTTPError as exc:
        body_text = exc.read().decode("utf-8", errors="replace")
        try:
            payload = json.loads(body_text) if body_text else {"detail": body_text}
        except json.JSONDecodeError:
            payload = {"detail": body_text}
        return ApiResult(status=exc.code, payload=payload)
    except URLError as exc:
        raise RuntimeError(f"Unable to reach API at {url}: {exc}") from exc


def _pick_chart_columns(profile: dict[str, Any]) -> tuple[str, str, str]:
    columns = profile.get("columns", [])
    if not isinstance(columns, list) or not columns:
        raise RuntimeError("Profile has no columns; cannot build smoke chart payload.")

    dimension_col = None
    measure_col = None

    for column in columns:
        if not isinstance(column, dict):
            continue
        name = column.get("name")
        role = str(column.get("effective_role", "")).lower()
        physical_type = str(column.get("physical_type", "")).lower()
        if not isinstance(name, str) or not name:
            continue
        if dimension_col is None and role in {"dimension", "datetime", "id", "boolean", "text"}:
            dimension_col = name
        if measure_col is None and role == "measure":
            measure_col = name
        if measure_col is None and physical_type in {"int", "float", "decimal", "numeric", "double", "real"}:
            measure_col = name
        if dimension_col and measure_col:
            break

    if dimension_col and measure_col:
        return dimension_col, measure_col, "sum"

    fallback_name = columns[0].get("name")
    if not isinstance(fallback_name, str) or not fallback_name:
        raise RuntimeError("Could not determine fallback column name for smoke chart request.")
    return fallback_name, fallback_name, "count"


def main() -> int:
    parser = argparse.ArgumentParser(description="Local smoke checks for profiling + chart-data APIs.")
    parser.add_argument("--base-url", default="http://localhost:8000/api", help="Base API URL")
    parser.add_argument("--dataset-id", default="silkroute", help="Dataset id for scoped endpoints")
    args = parser.parse_args()

    base_url = args.base_url.rstrip("/")
    dataset_id = args.dataset_id

    dataset_agg_url = f"{base_url}/datasets/{dataset_id}/profiling/aggregations"
    legacy_agg_url = f"{base_url}/profiling/aggregations"

    print(f"[INFO] GET {dataset_agg_url}")
    agg_result = _request_json("GET", dataset_agg_url)
    use_legacy = agg_result.status == 404
    if use_legacy:
        print(f"[INFO] Dataset route unavailable (status=404), falling back to {legacy_agg_url}")
        agg_result = _request_json("GET", legacy_agg_url)

    if agg_result.status != 200:
        print(f"[ERROR] Aggregations call failed ({agg_result.status}): {agg_result.payload}")
        return 1

    aggregations = agg_result.payload.get("aggregations", [])
    if not aggregations:
        print("[ERROR] Aggregations response is empty.")
        return 1

    table_name = aggregations[0].get("table_name")
    if not isinstance(table_name, str) or not table_name:
        print("[ERROR] Could not determine table_name from aggregations response.")
        return 1

    profile_url = (
        f"{base_url}/profiling/aggregations/{table_name}/profile"
        if use_legacy
        else f"{base_url}/datasets/{dataset_id}/profiling/aggregations/{table_name}/profile"
    )
    print(f"[INFO] GET {profile_url}")
    profile_result = _request_json("GET", profile_url)
    if profile_result.status != 200:
        print(f"[ERROR] Profile call failed ({profile_result.status}): {profile_result.payload}")
        return 1

    profile_payload = profile_result.payload
    x_axis, y_axis, aggregation_fn = _pick_chart_columns(profile_payload)
    chart_payload = {
        "table_name": table_name,
        "x_axis": x_axis,
        "y_axis": y_axis,
        "aggregation_fn": aggregation_fn,
        "limit": 20,
    }

    chart_url = (
        f"{base_url}/profiling/chart-data"
        if use_legacy
        else f"{base_url}/datasets/{dataset_id}/profiling/chart-data"
    )
    print(f"[INFO] POST {chart_url}")
    chart_result = _request_json("POST", chart_url, chart_payload)
    if chart_result.status != 200:
        print(f"[ERROR] Chart-data call failed ({chart_result.status}): {chart_result.payload}")
        return 1

    payload = chart_result.payload
    if not isinstance(payload, dict) or "x" not in payload or "y" not in payload:
        print(f"[ERROR] Unexpected chart-data payload: {payload}")
        return 1

    print("[OK] Aggregations/profile/chart-data smoke checks passed.")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"[ERROR] smoke_api_local failed: {exc}")
        raise SystemExit(1) from exc
