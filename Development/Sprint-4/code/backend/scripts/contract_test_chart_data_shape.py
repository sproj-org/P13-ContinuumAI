"""Contract test for legacy chart-data response shape/model."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import httpx

SCRIPT_DIR = Path(__file__).resolve().parent
BASE_DIR = Path(__file__).resolve().parents[1]
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from app.schemas.chart_data import LegacyChartDataResponse  # noqa: E402
from contract_test_utils import (  # noqa: E402
    ContractTestError,
    assert_json_safe,
    assert_json_serializable,
    pick_chart_request,
    request_json,
)


def _validate_chart_payload(payload: dict, endpoint_name: str) -> None:
    model = LegacyChartDataResponse.model_validate(payload)
    expected = set(LegacyChartDataResponse.model_fields.keys())
    actual = set(payload.keys())
    if actual != expected:
        raise ContractTestError(
            f"{endpoint_name} keys mismatch. Expected {sorted(expected)}, got {sorted(actual)}"
        )
    assert_json_safe(model.model_dump())
    assert_json_serializable(model.model_dump(), endpoint_name)
    if len(model.x) != len(model.y):
        raise ContractTestError(f"{endpoint_name} has mismatched x/y lengths.")


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate chart-data response shape against schema.")
    parser.add_argument("--base-url", default="http://127.0.0.1:8000", help="Backend base URL")
    parser.add_argument("--dataset-id", default="silkroute", help="Dataset id")
    args = parser.parse_args()

    base_url = args.base_url.rstrip("/")
    dataset_id = args.dataset_id
    client = httpx.Client(base_url=base_url, timeout=30.0)

    try:
        agg_res = request_json(client, "GET", "/api/profiling/aggregations")
        aggregations = agg_res.payload.get("aggregations", [])
        if not isinstance(aggregations, list) or not aggregations:
            raise ContractTestError("No aggregations available for chart-data shape test.")

        table_name = aggregations[0].get("table_name")
        if not isinstance(table_name, str) or not table_name:
            raise ContractTestError("Invalid table_name in aggregations response.")

        profile_res = request_json(client, "GET", f"/api/profiling/aggregations/{table_name}/profile")
        chart_req = pick_chart_request(table_name=table_name, profile=profile_res.payload)

        legacy_chart = request_json(
            client,
            "POST",
            "/api/profiling/chart-data",
            json_body=chart_req,
        )
        if not isinstance(legacy_chart.payload, dict):
            raise ContractTestError("Legacy chart-data endpoint returned non-object JSON.")
        _validate_chart_payload(legacy_chart.payload, "/api/profiling/chart-data")

        dataset_chart = request_json(
            client,
            "POST",
            f"/api/datasets/{dataset_id}/profiling/chart-data",
            json_body=chart_req,
        )
        if not isinstance(dataset_chart.payload, dict):
            raise ContractTestError("Dataset chart-data endpoint returned non-object JSON.")
        _validate_chart_payload(
            dataset_chart.payload,
            f"/api/datasets/{dataset_id}/profiling/chart-data",
        )

    except ContractTestError as exc:
        print(f"[ERROR] Chart-data shape contract test failed: {exc}")
        return 1
    finally:
        client.close()

    print("[OK] Chart-data shape contract checks passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
