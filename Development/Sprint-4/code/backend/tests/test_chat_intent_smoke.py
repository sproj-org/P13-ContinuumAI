from __future__ import annotations

import os
from types import SimpleNamespace
from typing import Any

import pytest

os.environ["DATABASE_URL"] = "sqlite:///./test_chat_intent_smoke.db"
os.environ["JWT_SECRET_KEY"] = "test-secret"

from app.services.agents import chat_orchestrator
from app.services.agents.chat_models import ChatFocusContext, ChatPlanPatch, ChatQuickPrompt, ChatState
from app.services.charts.models import ChartSpecV1


CONTEXT = {
    "description": "daily retail sales performance",
    "measures": [{"name": "net_sales"}, {"name": "order_count"}],
    "dimensions": [{"name": "region"}, {"name": "store_id"}],
    "temporals": [{"name": "sales_date"}],
}

STRATEGY_DIGEST = {
    "north_star": {"name": "Revenue Growth"},
    "pillars": [{"id": "growth", "name": "Growth"}],
}


def _chart_spec(
    *,
    chart_type: str = "bar",
    x_field: str = "region",
    metric: str = "net_sales",
    drill_path: list[str] | None = None,
) -> ChartSpecV1:
    payload: dict[str, Any] = {
        "version": "v1",
        "table": "gold_sales_daily",
        "chart": {"type": chart_type},
        "encoding": {
            "x": {"field": x_field},
            "y": [{"field": metric, "aggregation": "sum", "alias": "metric_value"}],
        },
    }
    if drill_path:
        payload["semantic_context"] = {
            "matched_kpi_id": "net_sales_growth",
            "matched_kpi_label": "Net Sales Growth",
            "preferred_drill_path": drill_path,
        }
    return ChartSpecV1.model_validate(payload)


def _chart_rows(x_field: str) -> list[dict[str, Any]]:
    if x_field == "sales_date":
        labels = ["2025-01", "2025-02", "2025-03"]
    elif x_field == "store_id":
        labels = ["store_001", "store_002", "store_003"]
    else:
        labels = ["North", "South", "East"]
    values = [120.0, 95.0, 80.0]
    return [{x_field: label, "metric_value": value} for label, value in zip(labels, values, strict=False)]


def _focus_chart(
    *,
    chart_type: str = "bar",
    x_field: str = "region",
    metric: str = "net_sales",
    drill_path: list[str] | None = None,
) -> ChatFocusContext:
    spec = _chart_spec(chart_type=chart_type, x_field=x_field, metric=metric, drill_path=drill_path)
    return ChatFocusContext(
        focus_type="chart",
        title="Current sales chart",
        table="gold_sales_daily",
        chart_spec=spec,
        chart_rows=_chart_rows(x_field),
        summary="Current sales signal.",
    )


def _preview_payload(chart_spec: ChartSpecV1) -> dict[str, Any]:
    alias = chart_spec.encoding.y[0].alias or "metric_value"
    rows = _chart_rows(chart_spec.encoding.x.field)
    if alias != "metric_value":
        rows = [
            {
                **{key: value for key, value in row.items() if key != "metric_value"},
                alias: row["metric_value"],
            }
            for row in rows
        ]
    return {
        "columns": [chart_spec.encoding.x.field, alias],
        "rows": rows,
        "meta": {
            "metric": {
                "output_column": alias,
                "field": chart_spec.encoding.y[0].field,
                "aggregation": chart_spec.encoding.y[0].aggregation,
            }
        },
    }


def _install_chat_runtime_stubs(
    monkeypatch: pytest.MonkeyPatch,
    *,
    forced_plan: Any | None = None,
) -> None:
    monkeypatch.setattr(
        chat_orchestrator,
        "get_settings",
        lambda: SimpleNamespace(OPENAI_API_KEY="", OPENAI_MODEL="gpt-4o-mini"),
    )
    monkeypatch.setattr(chat_orchestrator, "build_compact_mart_context", lambda dataset_id, table: CONTEXT)
    monkeypatch.setattr(chat_orchestrator, "_load_strategy_runtime", lambda dataset_id: (STRATEGY_DIGEST, None, None))
    monkeypatch.setattr(chat_orchestrator, "list_kpis", lambda dataset_id: [])
    monkeypatch.setattr(chat_orchestrator, "_maybe_run_structured_analysis", lambda **kwargs: None)
    monkeypatch.setattr(
        chat_orchestrator,
        "execute_chart_preview",
        lambda *, dataset_id, chart_spec, db, debug=False: _preview_payload(chart_spec),
    )
    if forced_plan is None:
        monkeypatch.setattr(chat_orchestrator, "_generate_plan", lambda **kwargs: (None, "missing_key", None, None))
    else:
        monkeypatch.setattr(chat_orchestrator, "_generate_plan", lambda **kwargs: (forced_plan, None, None, None))


def _run_chat(
    monkeypatch: pytest.MonkeyPatch,
    *,
    message: str,
    mode: str = "auto",
    focus: ChatFocusContext | None = None,
    state: ChatState | None = None,
    quick_prompt: ChatQuickPrompt | None = None,
    forced_plan: Any | None = None,
) -> dict[str, Any]:
    _install_chat_runtime_stubs(monkeypatch, forced_plan=forced_plan)
    return chat_orchestrator.run_chat_orchestration(
        dataset_id="silkroute",
        message=message,
        table="gold_sales_daily",
        mode=mode,  # type: ignore[arg-type]
        state=state or ChatState(),
        history=None,
        focus=focus,
        quick_prompt=quick_prompt,
        db=SimpleNamespace(),
        debug=False,
    )


QUALITATIVE_CASES = [
    {
        "id": "focused-chart-change-to-monthly",
        "category": "chart_patching",
        "message": "Change this chart to monthly",
        "focus": _focus_chart(chart_type="line", x_field="sales_date"),
        "state": ChatState(last_chart_spec=_chart_spec(chart_type="line", x_field="sales_date")),
        "expected_types": {"chart", "chart_patch"},
        "forbidden_types": {"explain"},
    },
    {
        "id": "focused-turn-into-line",
        "category": "chart_patching",
        "message": "Turn this chart into a line chart",
        "focus": _focus_chart(chart_type="bar", x_field="region"),
        "state": ChatState(last_chart_spec=_chart_spec(chart_type="bar", x_field="region")),
        "expected_types": {"chart", "chart_patch"},
        "expected_chart_type": "line",
        "forbidden_types": {"explain"},
    },
    {
        "id": "focused-break-down-by-store",
        "category": "chart_patching",
        "message": "Break this down by store",
        "focus": _focus_chart(chart_type="line", x_field="sales_date"),
        "state": ChatState(last_chart_spec=_chart_spec(chart_type="line", x_field="sales_date")),
        "expected_types": {"chart", "chart_patch"},
        "expected_x_field": "store_id",
        "forbidden_types": {"explain"},
    },
    {
        "id": "no-focus-what-is-by",
        "category": "chart_generation",
        "message": "What is net sales by region?",
        "expected_types": {"chart"},
        "forbidden_types": {"explain"},
    },
    {
        "id": "no-focus-trend-question",
        "category": "chart_generation",
        "message": "What is the trend of order count over time?",
        "expected_types": {"chart"},
        "expected_chart_type": "line",
        "forbidden_types": {"explain"},
    },
    {
        "id": "explicit-explain-chart",
        "category": "artifact_explanation",
        "message": "Explain this chart",
        "focus": _focus_chart(chart_type="bar", x_field="region"),
        "state": ChatState(last_chart_spec=_chart_spec(chart_type="bar", x_field="region")),
        "expected_types": {"explain"},
    },
    {
        "id": "explicit-off-topic",
        "category": "off_topic_refusal",
        "message": "Write a poem about revenue",
        "expected_types": {"refuse"},
    },
    {
        "id": "true-ambiguity",
        "category": "ambiguity",
        "message": "Show performance",
        "expected_types": {"clarify"},
    },
    {
        "id": "drill-follow-up",
        "category": "drill_follow_up",
        "message": "What should I drill into next?",
        "focus": _focus_chart(chart_type="bar", x_field="region", drill_path=["region", "store_id"]),
        "state": ChatState(last_chart_spec=_chart_spec(chart_type="bar", x_field="region", drill_path=["region", "store_id"])),
        "quick_prompt": ChatQuickPrompt(
            label="What should I drill into next?",
            prompt_text="What should I drill into next?",
            prompt_kind="drill",
            preferred_route="chart_patch",
            focus_type="chart",
            artifact_action="drill_next",
        ),
        "expected_types": {"chart_patch"},
        "expected_patch_path": ("set", "encoding.x.field", "store_id"),
    },
    {
        "id": "guidance-follow-up",
        "category": "guidance",
        "message": "What should I look at next?",
        "focus": _focus_chart(chart_type="bar", x_field="region", drill_path=["region", "store_id"]),
        "state": ChatState(last_chart_spec=_chart_spec(chart_type="bar", x_field="region", drill_path=["region", "store_id"])),
        "expected_types": {"explain"},
        "message_contains": "store_id",
    },
]


@pytest.mark.parametrize("case", QUALITATIVE_CASES, ids=[case["id"] for case in QUALITATIVE_CASES])
def test_chat_orchestration_qualitative_smoke(case: dict[str, Any], monkeypatch: pytest.MonkeyPatch) -> None:
    response = _run_chat(
        monkeypatch,
        message=case["message"],
        focus=case.get("focus"),
        state=case.get("state"),
        quick_prompt=case.get("quick_prompt"),
    )

    assert response["response_type"] in case["expected_types"], (case["category"], response)
    assert response["response_type"] not in case.get("forbidden_types", set()), response

    if response["response_type"] == "chart":
        if "expected_chart_type" in case:
            assert response["chart_spec"]["chart"]["type"] == case["expected_chart_type"]
        if "expected_x_field" in case:
            assert response["chart_spec"]["encoding"]["x"]["field"] == case["expected_x_field"]

    if response["response_type"] == "chart_patch" and "expected_patch_path" in case:
        bucket, path, expected_value = case["expected_patch_path"]
        assert response["patch"][bucket][path] == expected_value

    if "message_contains" in case:
        assert case["message_contains"] in response["message"]


def test_chart_patch_plan_uses_focus_chart_when_state_is_empty(monkeypatch: pytest.MonkeyPatch) -> None:
    response = _run_chat(
        monkeypatch,
        message="Turn this chart into a line chart",
        mode="chart",
        focus=_focus_chart(chart_type="bar", x_field="region"),
        state=ChatState(),
        forced_plan=ChatPlanPatch(
            response_type="chart_patch",
            patch={"set": {"chart.type": "line"}, "unset": [], "add": {}},
            narrative_style="standard",
        ),
    )

    assert response["response_type"] == "chart"
    assert response["chart_spec"]["chart"]["type"] == "line"


def test_build_user_prompt_is_mode_specific_and_does_not_inject_explain_examples() -> None:
    prompt = chat_orchestrator._build_user_prompt(
        dataset_id="silkroute",
        table="gold_sales_daily",
        message="Show net sales by region",
        mode="auto",
        context=CONTEXT,
        state=ChatState(),
        history=None,
        focus=_focus_chart(chart_type="bar", x_field="region"),
        quick_prompt=None,
    )

    assert "Planning instructions:" in prompt
    assert "defaulting to explanation" in prompt
    assert "3-5 example prompts" not in prompt
