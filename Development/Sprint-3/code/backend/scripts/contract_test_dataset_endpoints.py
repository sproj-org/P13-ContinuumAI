"""Contract checks for dataset-scoped Sprint-3 endpoints."""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from typing import Any

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
AGG_KEYS = {"columns", "rows", "meta"}
CHART_KEYS = {"x", "y", "title", "x_axis_label", "y_axis_label"}
FLAG_RE = re.compile(r"(_flag|^is_|^has_|indicator)", re.IGNORECASE)
NUMERIC_TYPES = {"int", "float", "decimal", "numeric", "double", "real", "bigint", "smallint"}
GROUPABLE_ROLES = {"dimension", "datetime", "boolean", "id", "text", "temporal"}


def _iter_columns(profile: dict[str, Any]) -> list[dict[str, Any]]:
    columns = profile.get("columns", [])
    if not isinstance(columns, list):
        return []
    return [c for c in columns if isinstance(c, dict) and isinstance(c.get("name"), str)]


def _column_role(column: dict[str, Any]) -> str:
    return str(column.get("effective_role", column.get("base_role", ""))).lower()


def _column_type(column: dict[str, Any]) -> str:
    return str(column.get("physical_type", "")).lower()


def _is_groupable(column: dict[str, Any]) -> bool:
    role = _column_role(column)
    if role in GROUPABLE_ROLES:
        return True
    name = str(column.get("name", ""))
    return bool(FLAG_RE.search(name))


def _is_measure(column: dict[str, Any]) -> bool:
    return _column_role(column) == "measure" and _column_type(column) in NUMERIC_TYPES


def _is_datetime(column: dict[str, Any]) -> bool:
    role = _column_role(column)
    logical_type = str(column.get("logical_type", "")).lower()
    return role in {"datetime", "temporal"} or logical_type == "datetime"


def _is_flag(column: dict[str, Any]) -> bool:
    name = str(column.get("name", ""))
    role = _column_role(column)
    return bool(FLAG_RE.search(name)) or role == "boolean"


def _aggregate_call(
    client: httpx.Client,
    dataset_id: str,
    payload: dict[str, Any],
    scenario: str,
) -> dict[str, Any]:
    response = request_json(
        client,
        "POST",
        f"/api/datasets/{dataset_id}/query/aggregate",
        json_body=payload,
    )
    if not isinstance(response.payload, dict):
        raise ContractTestError(f"{scenario}: aggregate endpoint returned non-object JSON.")
    if set(response.payload.keys()) != AGG_KEYS:
        raise ContractTestError(
            f"{scenario}: aggregate endpoint keys mismatch. "
            f"Expected {sorted(AGG_KEYS)}, got {sorted(response.payload.keys())}"
        )
    assert_json_safe(response.payload)
    assert_json_serializable(response.payload, scenario)
    rows = response.payload.get("rows", [])
    if not isinstance(rows, list):
        raise ContractTestError(f"{scenario}: aggregate 'rows' must be a list.")
    return response.payload


def _exercise_scenario(
    client: httpx.Client,
    dataset_id: str,
    scenario_name: str,
    candidate_payloads: list[dict[str, Any]],
) -> None:
    if not candidate_payloads:
        raise ContractTestError(f"{scenario_name}: no candidate payloads could be built from profiles.")

    errors: list[str] = []
    for payload in candidate_payloads:
        try:
            _aggregate_call(client, dataset_id, payload, scenario_name)
            print(f"[OK] {scenario_name}: passed using table '{payload['table_name']}'.")
            return
        except ContractTestError as exc:
            errors.append(str(exc))
    raise ContractTestError(
        f"{scenario_name}: all candidate requests failed. Last error: {errors[-1]}"
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate dataset-scoped endpoint contracts.")
    parser.add_argument("--base-url", default="http://127.0.0.1:8000", help="Backend base URL")
    parser.add_argument("--dataset-id", default="silkroute", help="Dataset id")
    args = parser.parse_args()

    base_url = args.base_url.rstrip("/")
    dataset_id = args.dataset_id
    client = httpx.Client(base_url=base_url, timeout=30.0)

    try:
        agg_path = f"/api/datasets/{dataset_id}/profiling/aggregations"
        agg_res = request_json(client, "GET", agg_path)
        ensure_required_keys(agg_res.payload, {"aggregations"}, agg_path)
        assert_json_safe(agg_res.payload)
        assert_json_serializable(agg_res.payload, agg_path)

        aggregations = agg_res.payload["aggregations"]
        if not isinstance(aggregations, list) or not aggregations:
            raise ContractTestError(f"{agg_path} returned empty/non-list 'aggregations'.")

        first = aggregations[0]
        ensure_required_keys(first, {"table_name", "schema_name"}, f"{agg_path}[0]")
        first_table = first["table_name"]
        if not isinstance(first_table, str) or not first_table:
            raise ContractTestError("First dataset aggregation has invalid table_name.")

        first_profile_path = f"/api/datasets/{dataset_id}/profiling/aggregations/{first_table}/profile"
        first_profile_res = request_json(client, "GET", first_profile_path)
        ensure_required_keys(first_profile_res.payload, PROFILE_TOP_LEVEL_KEYS, first_profile_path)
        assert_json_safe(first_profile_res.payload)
        assert_json_serializable(first_profile_res.payload, first_profile_path)

        first_col_name = find_first_column_name(first_profile_res.payload)
        first_col_path = (
            f"/api/datasets/{dataset_id}/profiling/aggregations/{first_table}/columns/{first_col_name}"
        )
        first_col_res = request_json(client, "GET", first_col_path)
        if not isinstance(first_col_res.payload, dict) or first_col_res.payload.get("name") != first_col_name:
            raise ContractTestError(f"{first_col_path} returned unexpected payload: {first_col_res.payload}")
        assert_json_safe(first_col_res.payload)
        assert_json_serializable(first_col_res.payload, first_col_path)

        # Dataset-scoped chart-data contract
        chart_req = pick_chart_request(table_name=first_table, profile=first_profile_res.payload)
        chart_res = request_json(
            client,
            "POST",
            f"/api/datasets/{dataset_id}/profiling/chart-data",
            json_body=chart_req,
        )
        if not isinstance(chart_res.payload, dict):
            raise ContractTestError("Dataset chart-data returned non-object JSON.")
        if set(chart_res.payload.keys()) != CHART_KEYS:
            raise ContractTestError(
                f"Dataset chart-data keys mismatch. Expected {sorted(CHART_KEYS)}, "
                f"got {sorted(chart_res.payload.keys())}"
            )
        assert_json_safe(chart_res.payload)
        assert_json_serializable(
            chart_res.payload,
            f"/api/datasets/{dataset_id}/profiling/chart-data",
        )

        # Load all profiles for aggregate scenario selection.
        profiles_by_table: dict[str, dict[str, Any]] = {}
        for item in aggregations:
            table_name = item.get("table_name")
            if not isinstance(table_name, str) or not table_name:
                continue
            profile_path = f"/api/datasets/{dataset_id}/profiling/aggregations/{table_name}/profile"
            profile_res = request_json(client, "GET", profile_path)
            ensure_required_keys(profile_res.payload, PROFILE_TOP_LEVEL_KEYS, profile_path)
            assert_json_safe(profile_res.payload)
            assert_json_serializable(profile_res.payload, profile_path)
            profiles_by_table[table_name] = profile_res.payload

        # Minimal safe aggregate request.
        minimal_candidates: list[dict[str, Any]] = []
        for table_name, profile in profiles_by_table.items():
            columns = _iter_columns(profile)
            groupable = [c for c in columns if _is_groupable(c)]
            measures = [c for c in columns if _is_measure(c)]
            if groupable and measures:
                x_name = str(groupable[0]["name"])
                y_name = str(measures[0]["name"])
                minimal_candidates.append(
                    {
                        "table_name": table_name,
                        "x": x_name,
                        "y": y_name,
                        "group_by": [x_name],
                        "filters": [],
                        "agg": {"column": y_name, "fn": "sum"},
                        "limit": 100,
                    }
                )
        _exercise_scenario(client, dataset_id, "minimal aggregate request", minimal_candidates)

        # Scenario: boolean/flag as x.
        flag_candidates: list[dict[str, Any]] = []
        for table_name, profile in profiles_by_table.items():
            columns = _iter_columns(profile)
            flags = [c for c in columns if _is_flag(c)]
            measures = [c for c in columns if _is_measure(c)]
            if flags and measures:
                flag_name = str(flags[0]["name"])
                measure_name = str(measures[0]["name"])
                flag_candidates.append(
                    {
                        "table_name": table_name,
                        "x": flag_name,
                        "y": measure_name,
                        "group_by": [flag_name],
                        "filters": [],
                        "agg": {"column": measure_name, "fn": "sum"},
                        "limit": 100,
                    }
                )
        _exercise_scenario(client, dataset_id, "flag-as-x aggregate", flag_candidates)

        # Scenario: datetime as x.
        datetime_candidates: list[dict[str, Any]] = []
        for table_name, profile in profiles_by_table.items():
            columns = _iter_columns(profile)
            datetimes = [c for c in columns if _is_datetime(c)]
            measures = [c for c in columns if _is_measure(c)]
            if datetimes and measures:
                datetime_name = str(datetimes[0]["name"])
                measure_name = str(measures[0]["name"])
                datetime_candidates.append(
                    {
                        "table_name": table_name,
                        "x": datetime_name,
                        "y": measure_name,
                        "group_by": [datetime_name],
                        "filters": [],
                        "agg": {"column": measure_name, "fn": "sum"},
                        "limit": 100,
                    }
                )
        _exercise_scenario(client, dataset_id, "datetime-as-x aggregate", datetime_candidates)

        # Scenario: numeric measure as y with sum and avg.
        measure_sum_avg_candidates: list[dict[str, Any]] = []
        for table_name, profile in profiles_by_table.items():
            columns = _iter_columns(profile)
            groupable = [c for c in columns if _is_groupable(c)]
            measures = [c for c in columns if _is_measure(c)]
            if groupable and measures:
                x_name = str(groupable[0]["name"])
                y_name = str(measures[0]["name"])
                measure_sum_avg_candidates.append(
                    {
                        "table_name": table_name,
                        "x": x_name,
                        "y": y_name,
                        "group_by": [x_name],
                        "filters": [],
                        "agg": {"column": y_name, "fn": "sum"},
                        "limit": 100,
                    }
                )
                measure_sum_avg_candidates.append(
                    {
                        "table_name": table_name,
                        "x": x_name,
                        "y": y_name,
                        "group_by": [x_name],
                        "filters": [],
                        "agg": {"column": y_name, "fn": "avg"},
                        "limit": 100,
                    }
                )
        _exercise_scenario(client, dataset_id, "numeric-measure sum/avg aggregate", measure_sum_avg_candidates)

        # Scenario: multi group_by.
        multi_group_candidates: list[dict[str, Any]] = []
        for table_name, profile in profiles_by_table.items():
            columns = _iter_columns(profile)
            groupable = [c for c in columns if _is_groupable(c)]
            measures = [c for c in columns if _is_measure(c)]
            if len(groupable) >= 2 and measures:
                x_name = str(groupable[0]["name"])
                group_name = str(groupable[1]["name"])
                y_name = str(measures[0]["name"])
                multi_group_candidates.append(
                    {
                        "table_name": table_name,
                        "x": x_name,
                        "y": y_name,
                        "group_by": [x_name, group_name],
                        "filters": [],
                        "agg": {"column": y_name, "fn": "sum"},
                        "limit": 100,
                    }
                )
        _exercise_scenario(client, dataset_id, "multi-group_by aggregate", multi_group_candidates)

    except ContractTestError as exc:
        print(f"[ERROR] Dataset endpoint contract test failed: {exc}")
        return 1
    finally:
        client.close()

    print("[OK] Dataset endpoint contract checks passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
