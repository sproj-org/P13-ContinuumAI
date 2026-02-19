"""Run multi-mart chat smoke tests and write a markdown behavior report."""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

from pydantic import TypeAdapter, ValidationError

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.core.mart_registry import list_marts
from app.services.agents.chat_models import ChatResponseUnion
from app.services.charts.models import ChartSpecV1

REPORT_PATH = BACKEND_ROOT / "out" / "chat_smoke_report.md"
_RESPONSE_ADAPTER = TypeAdapter(ChatResponseUnion)
OUT_DIR = BACKEND_ROOT / "out"


def _normalize_text(value: str) -> str:
    return " ".join(value.lower().replace("_", " ").split())


def _pick_matching_field(message: str, fields: list[str]) -> str | None:
    normalized_message = _normalize_text(message)
    for field in fields:
        normalized_field = _normalize_text(field)
        if normalized_field and normalized_field in normalized_message:
            return field
    return None


def _extract_fields(context: dict[str, Any]) -> tuple[list[str], list[str], list[str]]:
    metrics = [item["name"] for item in context.get("measures", []) if isinstance(item, dict) and isinstance(item.get("name"), str)]
    dimensions = [
        item["name"] for item in context.get("dimensions", []) if isinstance(item, dict) and isinstance(item.get("name"), str)
    ]
    temporals = [item["name"] for item in context.get("temporals", []) if isinstance(item, dict) and isinstance(item.get("name"), str)]
    return metrics, dimensions, temporals


def _has_time_intent(message: str) -> bool:
    normalized = _normalize_text(message)
    return any(
        token in normalized
        for token in ["trend", "over time", "month", "monthly", "week", "weekly", "day", "daily", "quarter", "year", "date"]
    )


def _effective_role(raw_column: dict[str, Any]) -> str:
    role = raw_column.get("effective_role") or raw_column.get("base_role") or ""
    return str(role).lower()


def _build_compact_context_from_profile(dataset_id: str, mart: dict[str, Any]) -> dict[str, Any]:
    profile_path = OUT_DIR / str(mart.get("profile_file", ""))
    if not profile_path.exists():
        raise FileNotFoundError(f"Missing profile file: {profile_path}")

    profile = json.loads(profile_path.read_text(encoding="utf-8"))
    raw_columns = profile.get("columns", [])
    if not isinstance(raw_columns, list):
        raw_columns = []

    dimensions: list[dict[str, Any]] = []
    measures: list[dict[str, Any]] = []
    temporals: list[dict[str, Any]] = []
    for raw in raw_columns:
        if not isinstance(raw, dict):
            continue
        name = raw.get("name")
        if not isinstance(name, str):
            continue
        role = _effective_role(raw)
        base = {"name": name, "type": raw.get("physical_type"), "role": role}
        if role in {"datetime", "temporal"}:
            stats = raw.get("stats", {}) if isinstance(raw.get("stats"), dict) else {}
            temporals.append(
                {
                    **base,
                    "min": stats.get("min"),
                    "max": stats.get("max"),
                    "null_rate": raw.get("null_fraction"),
                }
            )
        elif role == "measure":
            stats = raw.get("stats", {}) if isinstance(raw.get("stats"), dict) else {}
            measures.append(
                {
                    **base,
                    "min": stats.get("min"),
                    "max": stats.get("max"),
                    "avg": stats.get("mean"),
                    "null_rate": raw.get("null_fraction"),
                }
            )
        elif role in {"dimension", "id", "text", "boolean"}:
            dimensions.append(
                {
                    **base,
                    "distinct_count": raw.get("distinct_count"),
                    "sample_values": list(raw.get("sample_values", [])[:4]) if isinstance(raw.get("sample_values"), list) else [],
                }
            )

    dimensions = sorted(dimensions, key=lambda item: str(item.get("name", "")))[:25]
    measures = sorted(measures, key=lambda item: str(item.get("name", "")))[:25]
    temporals = sorted(temporals, key=lambda item: str(item.get("name", "")))[:25]
    return {
        "dataset_id": dataset_id,
        "table_id": mart.get("id"),
        "description": mart.get("description"),
        "temporals": temporals,
        "dimensions": dimensions,
        "measures": measures,
        "role_rules": {
            "x": "dimension|temporal",
            "y": "measure with agg",
            "filters": "must reference valid fields",
        },
    }


def _stub_chart_response(
    *,
    dataset_id: str,
    table: str,
    metric: str,
    x_field: str,
    db,
) -> dict[str, Any]:
    chart_spec = ChartSpecV1(
        version="v1",
        dataset_id=dataset_id,
        table=table,
        chart={"type": "line" if "date" in x_field.lower() or "day" in x_field.lower() else "bar"},
        encoding={
            "x": {"field": x_field},
            "y": [{"field": metric, "aggregation": "sum", "alias": "metric_value"}],
        },
        filters=[],
        sort=[{"field": "metric_value", "direction": "desc"}],
        limit=20,
    )
    if db is None:
        return {
            "response_type": "chart",
            "chart_spec": chart_spec.model_dump(mode="json"),
            "columns": [x_field, "metric_value"],
            "rows": [],
            "narrative": f"Stub planning completed for {metric} by {x_field}.",
            "meta": {"stub": True, "db_available": False},
        }

    from app.services.charts.spec_resolver import execute_chart_preview

    preview = execute_chart_preview(dataset_id=dataset_id, chart_spec=chart_spec, db=db, debug=False)
    return {
        "response_type": "chart",
        "chart_spec": preview.get("chart_spec"),
        "columns": list(preview.get("columns", [])),
        "rows": list(preview.get("rows", [])),
        "narrative": f"Stub execution completed for {metric} by {x_field}.",
        "meta": dict(preview.get("meta", {})),
    }


def _run_stub_chat(
    *,
    dataset_id: str,
    table: str,
    message: str,
    mode: Literal["auto", "chart", "explain"],
    state: dict[str, Any] | None,
    context: dict[str, Any],
    db,
) -> dict[str, Any]:
    metrics, dimensions, temporals = _extract_fields(context)
    selections = dict((state or {}).get("selections", {}))
    metric = selections.get("metric")
    temporal = selections.get("temporal")
    dimension = selections.get("dimension")
    x_field = temporal or dimension
    time_grain = selections.get("time_grain")
    time_intent = _has_time_intent(message)
    prompt_metric = _pick_matching_field(message, metrics)
    prompt_x = _pick_matching_field(message, [*dimensions, *temporals])

    if mode == "explain" or "explain" in _normalize_text(message):
        return {
            "response_type": "explain",
            "message": f"{table} is scoped to mart analytics with measures {', '.join(metrics[:3]) or 'none'} and dimensions {', '.join(dimensions[:3]) or 'none'}.",
            "citations": [f"profile:{table}"],
            "meta": {"stub": True},
        }

    if "poem" in _normalize_text(message):
        return {
            "response_type": "refuse",
            "message": "I can only help with analytics questions for the selected mart.",
            "meta": {"stub": True},
        }

    if not metric:
        metric = prompt_metric
    if not x_field:
        if prompt_x:
            x_field = prompt_x
        elif time_intent and temporals:
            x_field = temporals[0]
        elif dimensions:
            x_field = dimensions[0]
        elif temporals:
            x_field = temporals[0]

    if not metric:
        return {
            "response_type": "clarify",
            "clarify_id": "stub-clarify",
            "question": "Which metric should I use?",
            "missing": ["metric"],
            "options": {
                "metrics": metrics[:5],
                "dimensions": [],
                "temporals": [],
                "time_grains": [],
            },
            "meta": {"stub": True},
        }

    if not x_field:
        return {
            "response_type": "clarify",
            "clarify_id": "stub-clarify",
            "question": "What should I group or trend by?",
            "missing": ["x_axis"],
            "options": {
                "metrics": [],
                "dimensions": dimensions[:5],
                "temporals": temporals[:5],
                "time_grains": [],
            },
            "meta": {"stub": True},
        }

    if x_field in temporals and time_intent and not time_grain:
        return {
            "response_type": "clarify",
            "clarify_id": "stub-clarify",
            "question": "Which time grain?",
            "missing": ["time_grain"],
            "options": {
                "metrics": [],
                "dimensions": [],
                "temporals": [],
                "time_grains": ["day", "week", "month", "quarter", "year"],
            },
            "meta": {"stub": True},
        }

    if "customer age distribution" in _normalize_text(message) and not _pick_matching_field(message, [*metrics, *dimensions, *temporals]):
        return {
            "response_type": "clarify",
            "clarify_id": "stub-clarify",
            "question": "That concept is not represented in this mart. Which available metric should I use instead?",
            "missing": ["metric"],
            "options": {
                "metrics": metrics[:5],
                "dimensions": [],
                "temporals": [],
                "time_grains": [],
            },
            "meta": {"stub": True},
        }

    if metric and x_field:
        return _stub_chart_response(
            dataset_id=dataset_id,
            table=table,
            metric=metric,
            x_field=x_field,
            db=db,
        )

    return {
        "response_type": "clarify",
        "clarify_id": "stub-clarify",
        "question": "Which metric should I use?",
        "missing": ["metric"],
        "options": {
            "metrics": metrics[:5],
            "dimensions": [],
            "temporals": [],
            "time_grains": [],
        },
        "meta": {"stub": True},
    }


def _validate_response_shape(payload: dict[str, Any]) -> tuple[bool, str]:
    try:
        _RESPONSE_ADAPTER.validate_python(payload)
    except ValidationError as exc:
        return False, str(exc).splitlines()[0]
    return True, ""


def _pick_clarify_selections(response: dict[str, Any], state: dict[str, Any], *, message: str) -> dict[str, Any]:
    options = response.get("options", {}) if isinstance(response.get("options"), dict) else {}
    missing = response.get("missing", []) if isinstance(response.get("missing"), list) else []
    next_state = dict(state)
    selections = dict(next_state.get("selections", {}))
    stage = str(missing[0]).strip().lower() if missing else "metric"
    if stage in {"dimension", "temporal"}:
        stage = "x_axis"

    if stage == "metric" and not selections.get("metric"):
        metrics = options.get("metrics", [])
        if isinstance(metrics, list) and metrics:
            selections["metric"] = metrics[0]
    elif stage == "x_axis" and not (selections.get("dimension") or selections.get("temporal")):
        dimensions = options.get("dimensions", [])
        temporals = options.get("temporals", [])
        if _has_time_intent(message) and isinstance(temporals, list) and temporals:
            selections["temporal"] = temporals[0]
        elif isinstance(dimensions, list) and dimensions:
            selections["dimension"] = dimensions[0]
        elif isinstance(temporals, list) and temporals:
            selections["temporal"] = temporals[0]
    elif stage == "time_grain" and not selections.get("time_grain"):
        time_grains = options.get("time_grains", [])
        if isinstance(time_grains, list) and "month" in time_grains:
            selections["time_grain"] = "month"
        elif isinstance(time_grains, list) and time_grains:
            selections["time_grain"] = time_grains[0]

    next_state["clarify_id"] = response.get("clarify_id")
    next_state["selections"] = selections
    return next_state


def _build_prompt_suite(context: dict[str, Any]) -> list[dict[str, str]]:
    metrics, dimensions, temporals = _extract_fields(context)
    metric = metrics[0] if metrics else None
    dimension = dimensions[0] if dimensions else None
    temporal = temporals[0] if temporals else None
    if not metric:
        return []

    prompts: list[dict[str, str]] = []
    if dimension:
        prompts.append({"kind": "basic", "mode": "chart", "prompt": f"Show {metric} by {dimension}"})
        prompts.append({"kind": "topk", "mode": "chart", "prompt": f"Top 10 {dimension} by {metric}"})
    if temporal:
        prompts.append({"kind": "time", "mode": "chart", "prompt": f"Trend of {metric} by month using {temporal}"})
    prompts.append(
        {
            "kind": "explain",
            "mode": "explain",
            "prompt": "Explain what this mart represents and what KPIs it supports",
        }
    )
    prompts.append({"kind": "ambiguous", "mode": "auto", "prompt": "Show performance"})
    prompts.append({"kind": "mismatch", "mode": "auto", "prompt": "Show customer age distribution"})
    return prompts


def _call_chat(
    *,
    dataset_id: str,
    table: str,
    message: str,
    mode: Literal["auto", "chart", "explain"],
    state: dict[str, Any] | None,
    context: dict[str, Any],
    db,
    use_stub: bool,
) -> dict[str, Any]:
    if use_stub:
        return _run_stub_chat(
            dataset_id=dataset_id,
            table=table,
            message=message,
            mode=mode,
            state=state,
            context=context,
            db=db,
        )
    from app.services.agents.chat_orchestrator import run_chat_orchestration

    return run_chat_orchestration(
        dataset_id=dataset_id,
        table=table,
        message=message,
        mode=mode,
        state=state,
        db=db,
        debug=False,
    )


def _write_report(
    path: Path,
    rows: list[dict[str, Any]],
    summary: dict[str, Any],
    clarify_rates: dict[str, float],
    use_stub: bool,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    generated_at = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    lines = [
        "# Chat Smoke Report",
        "",
        f"- Generated: {generated_at}",
        f"- Mode: {'stub' if use_stub else 'live_llm'}",
        "",
        "| mart | prompt | response_type | steps_to_converge | notes |",
        "| --- | --- | --- | --- | --- |",
    ]
    for row in rows:
        prompt = str(row["prompt"]).replace("|", "\\|")
        notes = str(row["notes"]).replace("|", "\\|")
        lines.append(
            f"| {row['mart']} | {prompt} | {row['response_type']} | {row['steps_to_converge']} | {notes} |"
        )

    lines.extend(
        [
            "",
            "## Summary",
            f"- charts: {summary['chart']}",
            f"- explains: {summary['explain']}",
            f"- clarifies: {summary['clarify']}",
            f"- refuses: {summary['refuse']}",
            f"- failures: {summary['failures']}",
            f"- avg steps (all prompts): {summary['avg_steps']:.2f}",
            f"- avg steps to converge (in-scope prompts): {summary['avg_in_scope_steps']:.2f}",
            "",
            "## Clarify Rate By Mart",
        ]
    )
    for mart_id, rate in sorted(clarify_rates.items()):
        lines.append(f"- {mart_id}: {rate:.2f}")
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Run chat behavior smoke tests across all marts.")
    parser.add_argument("--dataset-id", default="silkroute", help="Dataset id to test")
    parser.add_argument("--report-path", default=str(REPORT_PATH), help="Path for markdown report output")
    args = parser.parse_args()

    dataset_id = args.dataset_id
    db = None
    db_boot_error: str | None = None
    try:
        from app.db.database import SessionLocal

        db = SessionLocal()
    except Exception as exc:
        db_boot_error = str(exc)

    use_stub = (not bool(os.getenv("OPENAI_API_KEY"))) or db is None
    marts = list_marts(dataset_id)
    if not marts:
        print(f"[ERROR] No marts registered for dataset '{dataset_id}'.")
        return 1

    summary = {
        "chart": 0,
        "explain": 0,
        "clarify": 0,
        "refuse": 0,
        "failures": 0,
        "avg_steps": 0.0,
        "avg_in_scope_steps": 0.0,
    }
    rows: list[dict[str, Any]] = []
    total_steps = 0
    total_cases = 0
    in_scope_steps = 0
    in_scope_cases = 0
    mart_total: dict[str, int] = {}
    mart_clarify: dict[str, int] = {}

    try:
        for mart in marts:
            table = str(mart["id"])
            try:
                context = _build_compact_context_from_profile(dataset_id, mart)
            except Exception as exc:
                rows.append(
                    {
                        "mart": table,
                        "prompt": "n/a",
                        "response_type": "error",
                        "steps_to_converge": 0,
                        "notes": f"Failed to load profile context: {exc}",
                    }
                )
                summary["failures"] += 1
                continue
            prompt_suite = _build_prompt_suite(context)
            if not prompt_suite:
                rows.append(
                    {
                        "mart": table,
                        "prompt": "n/a",
                        "response_type": "refuse",
                        "steps_to_converge": 0,
                        "notes": "Skipped: no measure fields available",
                    }
                )
                continue

            for prompt_case in prompt_suite:
                kind = prompt_case["kind"]
                prompt_text = prompt_case["prompt"]
                mode = prompt_case["mode"]
                state: dict[str, Any] = {"original_user_intent": prompt_text}
                steps = 0
                response: dict[str, Any] | None = None
                notes = "success"
                mart_total[table] = mart_total.get(table, 0) + 1

                for _ in range(3):
                    response = _call_chat(
                        dataset_id=dataset_id,
                        table=table,
                        message=prompt_text,
                        mode=mode,  # type: ignore[arg-type]
                        state=state,
                        context=context,
                        db=db,
                        use_stub=use_stub,
                    )
                    steps += 1

                    valid_shape, validation_note = _validate_response_shape(response)
                    if not valid_shape:
                        notes = f"invalid response shape: {validation_note}"
                        break

                    response_type = str(response.get("response_type"))
                    if response_type != "clarify":
                        break

                    state = _pick_clarify_selections(response, state, message=prompt_text)
                    if not state.get("selections"):
                        notes = "clarify without usable options"
                        break

                if response is None:
                    summary["failures"] += 1
                    rows.append(
                        {
                            "mart": table,
                            "prompt": prompt_text,
                            "response_type": "error",
                            "steps_to_converge": steps,
                            "notes": "No response",
                        }
                    )
                    continue

                response_type = str(response.get("response_type", "unknown"))
                if response_type == "clarify":
                    mart_clarify[table] = mart_clarify.get(table, 0) + 1

                if notes != "success":
                    summary["failures"] += 1

                if response_type in summary:
                    summary[response_type] += 1
                else:
                    summary["failures"] += 1

                if kind in {"basic", "time", "topk"}:
                    in_scope_steps += steps
                    in_scope_cases += 1
                    if response_type != "chart":
                        notes = f"expected chart for in-scope prompt, got {response_type}"
                        summary["failures"] += 1
                    if steps > 2:
                        notes = f"took {steps} steps; expected <=2"
                        summary["failures"] += 1
                elif kind == "explain" and response_type != "explain":
                    notes = f"expected explain, got {response_type}"
                    summary["failures"] += 1
                elif kind == "mismatch" and response_type not in {"clarify", "refuse"}:
                    notes = f"mismatch prompt should clarify/refuse, got {response_type}"
                    summary["failures"] += 1

                rows.append(
                    {
                        "mart": table,
                        "prompt": prompt_text,
                        "response_type": response_type,
                        "steps_to_converge": steps,
                        "notes": notes,
                    }
                )

                total_steps += steps
                total_cases += 1

    finally:
        if db is not None:
            db.close()

    if total_cases:
        summary["avg_steps"] = total_steps / total_cases
    if in_scope_cases:
        summary["avg_in_scope_steps"] = in_scope_steps / in_scope_cases

    clarify_rates: dict[str, float] = {}
    for mart in marts:
        mart_id = str(mart["id"])
        total = mart_total.get(mart_id, 0)
        clarifies = mart_clarify.get(mart_id, 0)
        clarify_rates[mart_id] = (clarifies / total) if total else 0.0

    report_path = Path(args.report_path)
    _write_report(report_path, rows, summary, clarify_rates, use_stub=use_stub)

    if use_stub and db_boot_error:
        print(f"[WARN] DB unavailable, using stub mode: {db_boot_error}")

    print(
        "[OK] chat smoke complete "
        f"(charts={summary['chart']}, explains={summary['explain']}, clarifies={summary['clarify']}, "
        f"refuses={summary['refuse']}, failures={summary['failures']}, avg_steps={summary['avg_steps']:.2f}, "
        f"avg_in_scope_steps={summary['avg_in_scope_steps']:.2f})"
    )
    print(f"[OK] report: {report_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
