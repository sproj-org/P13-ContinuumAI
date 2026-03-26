from __future__ import annotations

import os
from types import SimpleNamespace
from typing import Any

import pytest

os.environ["DATABASE_URL"] = "sqlite:///./test_chat_orchestrator.db"
os.environ["JWT_SECRET_KEY"] = "test-secret"

from app.services.agents import chat_orchestrator
from app.services.agents.chat_models import ChatFocusContext, ChatState
from app.services.charts.models import ChartSpecV1
from app.services.intelligence.specs import AnalysisContextSpec, AnalysisResponse, InsightCard, PlanSpec


CONTEXT = {
    "measures": [{"name": "net_sales"}, {"name": "order_count"}],
    "dimensions": [{"name": "region"}, {"name": "store_id"}],
    "temporals": [{"name": "sales_date"}],
}

STRATEGY_DIGEST = {
    "north_star": {"name": "Revenue Growth"},
    "pillars": [{"id": "growth", "name": "Growth"}],
}


def _install_openai_stub(monkeypatch: pytest.MonkeyPatch, payloads: list[dict[str, Any]]) -> None:
    class StubClient:
        def __init__(self, **_: Any) -> None:
            self._call_count = 0

        def generate_json(self, **_: Any) -> dict[str, Any]:
            index = self._call_count if self._call_count < len(payloads) else len(payloads) - 1
            self._call_count += 1
            return payloads[index]

    monkeypatch.setattr(
        chat_orchestrator,
        "get_settings",
        lambda: SimpleNamespace(OPENAI_API_KEY="test-key", OPENAI_MODEL="gpt-4o-mini"),
    )
    monkeypatch.setattr(chat_orchestrator, "OpenAIClient", StubClient)
    monkeypatch.setattr(chat_orchestrator, "list_kpis", lambda dataset_id: [])


def test_generate_plan_normalizes_common_chart_aliases(monkeypatch: pytest.MonkeyPatch) -> None:
    _install_openai_stub(
        monkeypatch,
        [
            {
                "type": "visualization",
                "style": "brief",
                "chartSpec": {
                    "chart": "column",
                    "x": "region",
                    "y": {"column": "net_sales", "aggregation": "sum", "label": "metric_value"},
                    "filters": {"column": "region", "op": "eq", "value": "North"},
                    "sort": {"field": "metric_value", "direction": "descending"},
                    "limit": "15",
                },
            }
        ],
    )

    plan, fallback_reason, diagnostics, exception_class = chat_orchestrator._generate_plan(
        dataset_id="silkroute",
        table="gold_sales_daily",
        message="Show net sales by region",
        mode="auto",
        context=CONTEXT,
        strategy_digest=STRATEGY_DIGEST,
        strategy_notice=None,
        state=ChatState(),
        history=None,
    )

    assert fallback_reason is None
    assert diagnostics is None
    assert exception_class is None
    assert plan is not None
    assert plan.response_type == "chart"
    assert plan.chart_spec.chart.type == "bar"
    assert plan.chart_spec.encoding.x.field == "region"
    assert plan.chart_spec.encoding.y[0].field == "net_sales"
    assert plan.chart_spec.encoding.y[0].aggregation == "sum"
    assert plan.chart_spec.filters[0].op == "="
    assert plan.chart_spec.sort[0].direction == "desc"
    assert plan.chart_spec.limit == 15
    assert plan.narrative_style == "brief"


def test_generate_plan_normalizes_clarify_stage_aliases(monkeypatch: pytest.MonkeyPatch) -> None:
    _install_openai_stub(
        monkeypatch,
        [
            {
                "type": "question",
                "message": "Which field should I group or trend by?",
                "missing": "dimension",
                "dimensions": ["region"],
                "temporals": ["sales_date"],
            }
        ],
    )

    plan, fallback_reason, diagnostics, exception_class = chat_orchestrator._generate_plan(
        dataset_id="silkroute",
        table="gold_sales_daily",
        message="Break net sales down",
        mode="auto",
        context=CONTEXT,
        strategy_digest=STRATEGY_DIGEST,
        strategy_notice=None,
        state=ChatState(),
        history=None,
    )

    assert fallback_reason is None
    assert diagnostics is None
    assert exception_class is None
    assert plan is not None
    assert plan.response_type == "clarify"
    assert plan.missing == ["x_axis"]
    assert plan.options.dimensions == ["region"]
    assert plan.options.temporals == ["sales_date"]
    assert "group" in plan.question.lower()


def test_generate_plan_returns_actionable_schema_hint(monkeypatch: pytest.MonkeyPatch) -> None:
    _install_openai_stub(
        monkeypatch,
        [
            {
                "response_type": "chart",
                "chart_spec": {
                    "chart": "line",
                    "encoding": {"x": {}, "y": []},
                },
            }
        ],
    )

    plan, fallback_reason, diagnostics, exception_class = chat_orchestrator._generate_plan(
        dataset_id="silkroute",
        table="gold_sales_daily",
        message="Show sales trend",
        mode="auto",
        context=CONTEXT,
        strategy_digest=STRATEGY_DIGEST,
        strategy_notice=None,
        state=ChatState(),
        history=None,
    )

    assert plan is None
    assert fallback_reason == "openai_error"
    assert exception_class == "ValidationError"
    assert diagnostics is not None
    assert diagnostics["openai_error_hint"] is not None
    assert diagnostics["openai_error_hint"].startswith("Schema mismatch:")
    assert "chart_spec" in diagnostics["openai_error_hint"] or "encoding" in diagnostics["openai_error_hint"]


def test_generate_plan_recovers_wrapped_chart_payload(monkeypatch: pytest.MonkeyPatch) -> None:
    _install_openai_stub(
        monkeypatch,
        [
            {
                "result": {
                    "responseType": "visualization",
                    "data": {
                        "chartSpec": {
                            "chart": {"type": "column"},
                            "groupBy": "region",
                            "metrics": [{"measure": "net_sales", "agg": "sum", "label": "sales_metric"}],
                            "filters": {"region": "North"},
                            "sort": "sales_metric",
                            "topN": "12",
                        },
                        "style": "brief",
                    },
                }
            }
        ],
    )

    plan, fallback_reason, diagnostics, exception_class = chat_orchestrator._generate_plan(
        dataset_id="silkroute",
        table="gold_sales_daily",
        message="Show net sales by region",
        mode="auto",
        context=CONTEXT,
        strategy_digest=STRATEGY_DIGEST,
        strategy_notice=None,
        state=ChatState(),
        history=None,
    )

    assert fallback_reason is None
    assert diagnostics is None
    assert exception_class is None
    assert plan is not None
    assert plan.response_type == "chart"
    assert plan.chart_spec.chart.type == "bar"
    assert plan.chart_spec.encoding.x.field == "region"
    assert plan.chart_spec.encoding.y[0].field == "net_sales"
    assert plan.chart_spec.filters[0].field == "region"
    assert plan.chart_spec.filters[0].value == "North"
    assert plan.chart_spec.limit == 12
    assert plan.narrative_style == "brief"


def test_generate_plan_recovers_stringified_explain_payload(monkeypatch: pytest.MonkeyPatch) -> None:
    _install_openai_stub(
        monkeypatch,
        [
            {
                "payload": "{\"type\":\"answer\",\"summary\":\"Net sales are strongest in North.\"}"
            }
        ],
    )

    plan, fallback_reason, diagnostics, exception_class = chat_orchestrator._generate_plan(
        dataset_id="silkroute",
        table="gold_sales_daily",
        message="Explain the current sales pattern",
        mode="auto",
        context=CONTEXT,
        strategy_digest=STRATEGY_DIGEST,
        strategy_notice=None,
        state=ChatState(),
        history=None,
    )

    assert fallback_reason is None
    assert diagnostics is None
    assert exception_class is None
    assert plan is not None
    assert plan.response_type == "explain"
    assert "North" in plan.message


def test_generate_plan_recovers_clarify_choices(monkeypatch: pytest.MonkeyPatch) -> None:
    _install_openai_stub(
        monkeypatch,
        [
            {
                "data": {
                    "action": "question",
                    "prompt": "Which time grain should I use?",
                    "needs": "time_grain",
                    "choices": ["day", "week", "month"],
                }
            }
        ],
    )

    plan, fallback_reason, diagnostics, exception_class = chat_orchestrator._generate_plan(
        dataset_id="silkroute",
        table="gold_sales_daily",
        message="Trend net sales over time",
        mode="auto",
        context=CONTEXT,
        strategy_digest=STRATEGY_DIGEST,
        strategy_notice=None,
        state=ChatState(),
        history=None,
    )

    assert fallback_reason is None
    assert diagnostics is None
    assert exception_class is None
    assert plan is not None
    assert plan.response_type == "clarify"
    assert plan.missing == ["time_grain"]
    assert plan.options.time_grains == ["day", "week", "month"]


def test_generate_plan_normalizes_chart_patch_operations(monkeypatch: pytest.MonkeyPatch) -> None:
    _install_openai_stub(
        monkeypatch,
        [
            {
                "response": {
                    "type": "update_chart",
                    "operations": [
                        {"op": "set", "path": "chart.type", "value": "line"},
                        {"op": "unset", "path": "filters"},
                        {"op": "add", "path": "filters.0", "value": {"field": "region", "op": "=", "value": "North"}},
                    ],
                }
            }
        ],
    )

    plan, fallback_reason, diagnostics, exception_class = chat_orchestrator._generate_plan(
        dataset_id="silkroute",
        table="gold_sales_daily",
        message="Turn this into a line chart",
        mode="auto",
        context=CONTEXT,
        strategy_digest=STRATEGY_DIGEST,
        strategy_notice=None,
        state=ChatState(),
        history=None,
    )

    assert fallback_reason is None
    assert diagnostics is None
    assert exception_class is None
    assert plan is not None
    assert plan.response_type == "chart_patch"
    assert plan.patch.set["chart.type"] == "line"
    assert plan.patch.unset == ["filters"]
    assert plan.patch.add["filters.0"]["field"] == "region"


def test_generate_plan_rejects_unrecoverable_payloads(monkeypatch: pytest.MonkeyPatch) -> None:
    _install_openai_stub(
        monkeypatch,
        [[1, 2, 3]],
    )

    plan, fallback_reason, diagnostics, exception_class = chat_orchestrator._generate_plan(
        dataset_id="silkroute",
        table="gold_sales_daily",
        message="Show something useful",
        mode="auto",
        context=CONTEXT,
        strategy_digest=STRATEGY_DIGEST,
        strategy_notice=None,
        state=ChatState(),
        history=None,
    )

    assert plan is None
    assert fallback_reason == "openai_error"
    assert diagnostics is not None
    assert diagnostics["openai_error_hint"] is not None
    assert "could not be recovered" in diagnostics["openai_error_hint"]


def test_build_user_prompt_includes_focused_artifact_context() -> None:
    prompt = chat_orchestrator._build_user_prompt(
        dataset_id="silkroute",
        table="gold_sales_daily",
        message="Explain this chart",
        mode="auto",
        context=CONTEXT,
        state=ChatState(),
        history=None,
        focus=ChatFocusContext(
            focus_type="chart",
            title="Revenue Trend",
            table="gold_sales_daily",
            kpi_id="total_sales",
            active_task="forecast",
            summary="Sales are accelerating.",
            breadcrumbs=["Dashboard", "Revenue"],
        ),
    )

    assert "Focused artifact context" in prompt
    assert "Revenue Trend" in prompt
    assert "forecast" in prompt


def test_maybe_run_structured_analysis_uses_focus_context_for_insight(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, Any] = {}

    def fake_create_plan(request, *, dataset_id):
        captured["request"] = request
        return (
            PlanSpec(
                dataset_id=dataset_id,
                table="gold_sales_daily",
                user_message=request.message or "Explain this chart",
                primary_task="insight",
                route_reason="Focused artifact insight",
                tasks=[],
                suggested_follow_ups=[],
            ),
            None,
        )

    def fake_run_analysis_request(*, dataset_id, request, db):
        captured["analysis_request"] = request
        return AnalysisResponse(
            task_type="insight",
            agent_role="insight_agent",
            plan_spec=PlanSpec(
                dataset_id=dataset_id,
                table="gold_sales_daily",
                user_message=request.message or "Explain this chart",
                primary_task="insight",
                route_reason="Focused artifact insight",
                tasks=[],
                suggested_follow_ups=[],
            ),
            insight_cards=[
                InsightCard(
                    title="Focused insight",
                    summary="Uses the current artifact context for the explanation.",
                    severity="info",
                )
            ],
            suggested_actions=[],
            meta={},
        )

    monkeypatch.setattr(chat_orchestrator, "create_analysis_plan", fake_create_plan)
    monkeypatch.setattr(chat_orchestrator, "run_analysis_request", fake_run_analysis_request)

    response = chat_orchestrator._maybe_run_structured_analysis(
        dataset_id="silkroute",
        table="gold_sales_daily",
        message="Explain this chart",
        state=ChatState(),
        focus=ChatFocusContext(
            focus_type="analysis_result",
            title="Revenue Risk",
            table="gold_sales_daily",
            kpi_id="total_sales",
            chart_spec=ChartSpecV1.model_validate(
                {
                    "version": "v1",
                    "table": "gold_sales_daily",
                    "chart": {"type": "line"},
                    "encoding": {
                        "x": {"field": "sales_date"},
                        "y": [{"field": "net_sales", "aggregation": "sum"}],
                    },
                }
            ),
            analysis_context=AnalysisContextSpec(source="dashboard", table="gold_sales_daily"),
            active_task="strategy_risk",
            summary="Risk is trending higher.",
        ),
        db=SimpleNamespace(),
    )

    assert response is not None
    assert response.response_type == "explain"
    assert captured["request"].kpi_id == "total_sales"
    assert captured["request"].chart_spec.table == "gold_sales_daily"
    assert captured["request"].analysis_context is not None
    assert captured["request"].analysis_context.source == "dashboard"
