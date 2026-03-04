"""Contract checks for legacy /api/profiling endpoints."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import httpx

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from contract_test_utils import (  # noqa: E402
    ContractTestError,
    assert_json_safe,
    assert_json_serializable,
    ensure_required_keys,
    find_first_column_name,
    pick_chart_request,
    request_json,
)

PROFILE_TOP_LEVEL_KEYS = {
    "dataset_name",
    "schema_name",
    "table_name",
    "row_count",
    "column_count",
    "profiled_at",
    "columns",
    "dataset_meta",
}
CHART_KEYS = {"x", "y", "title", "x_axis_label", "y_axis_label"}


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate legacy profiling endpoint contracts.")
    parser.add_argument("--base-url", default="http://127.0.0.1:8000", help="Backend base URL")
    args = parser.parse_args()

    base_url = args.base_url.rstrip("/")
    client = httpx.Client(base_url=base_url, timeout=30.0)

    try:
        agg_res = request_json(client, "GET", "/api/profiling/aggregations")
        ensure_required_keys(agg_res.payload, {"aggregations"}, "/api/profiling/aggregations")
        assert_json_safe(agg_res.payload)
        assert_json_serializable(agg_res.payload, "/api/profiling/aggregations")

        aggregations = agg_res.payload["aggregations"]
        if not isinstance(aggregations, list) or not aggregations:
            raise ContractTestError("/api/profiling/aggregations returned empty/non-list 'aggregations'.")

        first = aggregations[0]
        ensure_required_keys(first, {"table_name", "schema_name"}, "/api/profiling/aggregations[0]")
        table_name = first["table_name"]
        if not isinstance(table_name, str) or not table_name:
            raise ContractTestError("First aggregation has invalid table_name.")

        profile_path = f"/api/profiling/aggregations/{table_name}/profile"
        profile_res = request_json(client, "GET", profile_path)
        ensure_required_keys(profile_res.payload, PROFILE_TOP_LEVEL_KEYS, profile_path)
        assert_json_safe(profile_res.payload)
        assert_json_serializable(profile_res.payload, profile_path)

        column_name = find_first_column_name(profile_res.payload)
        col_path = f"/api/profiling/aggregations/{table_name}/columns/{column_name}"
        col_res = request_json(client, "GET", col_path)
        if not isinstance(col_res.payload, dict) or col_res.payload.get("name") != column_name:
            raise ContractTestError(f"{col_path} returned unexpected payload: {col_res.payload}")
        assert_json_safe(col_res.payload)
        assert_json_serializable(col_res.payload, col_path)

        chart_payload = pick_chart_request(table_name=table_name, profile=profile_res.payload)
        chart_res = request_json(
            client,
            "POST",
            "/api/profiling/chart-data",
            json_body=chart_payload,
        )
        if not isinstance(chart_res.payload, dict):
            raise ContractTestError("/api/profiling/chart-data must return an object.")
        if set(chart_res.payload.keys()) != CHART_KEYS:
            raise ContractTestError(
                f"/api/profiling/chart-data keys mismatch. "
                f"Expected {sorted(CHART_KEYS)}, got {sorted(chart_res.payload.keys())}"
            )
        assert_json_safe(chart_res.payload)
        assert_json_serializable(chart_res.payload, "/api/profiling/chart-data")

        x_vals = chart_res.payload.get("x")
        y_vals = chart_res.payload.get("y")
        if not isinstance(x_vals, list) or not isinstance(y_vals, list):
            raise ContractTestError("chart-data response requires list fields 'x' and 'y'.")
        if len(x_vals) != len(y_vals):
            raise ContractTestError("chart-data response has mismatched x/y lengths.")

    except ContractTestError as exc:
        print(f"[ERROR] Legacy endpoint contract test failed: {exc}")
        return 1
    finally:
        client.close()

    print("[OK] Legacy endpoint contract checks passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
