from __future__ import annotations

import os
from types import SimpleNamespace
from typing import Any

import pytest

os.environ["DATABASE_URL"] = "sqlite:///./test_chat_orchestrator.db"
os.environ["JWT_SECRET_KEY"] = "test-secret"

from app.services.agents import chat_orchestrator
from app.services.agents.chat_models import ChatState


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
