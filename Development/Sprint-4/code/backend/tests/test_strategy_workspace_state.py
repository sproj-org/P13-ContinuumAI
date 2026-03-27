from __future__ import annotations

import os
from pathlib import Path
from types import SimpleNamespace

from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest

os.environ["DATABASE_URL"] = "sqlite:///./test_strategy_workspace_state.db"
os.environ.setdefault("JWT_SECRET_KEY", "test-secret")

from app.api import strategy as strategy_api
from app.api.strategy import bundle_router
from app.core.security import get_current_user
from app.services.strategy import storage


def _patch_storage_paths(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    config_dir = tmp_path / "strategy_config"
    monkeypatch.setattr(storage, "STRATEGY_CONFIG_DIR", config_dir)
    monkeypatch.setattr(storage, "OVERRIDES_DIR", config_dir / "overrides")
    monkeypatch.setattr(storage, "REVISIONS_DIR", config_dir / "revisions")
    monkeypatch.setattr(storage, "BASE_STRATEGY_PATH", config_dir / "strategy_bundle.yaml")
    monkeypatch.setattr(storage, "BASE_KPI_PATH", config_dir / "kpi_registry.yaml")
    monkeypatch.setattr(storage, "OVERRIDE_STRATEGY_PATH", config_dir / "overrides" / "strategy_bundle.override.yaml")
    monkeypatch.setattr(storage, "OVERRIDE_KPI_PATH", config_dir / "overrides" / "kpi_registry.override.yaml")
    monkeypatch.setattr(storage, "REVISION_INDEX_PATH", config_dir / "revisions" / "index.json")


@pytest.fixture
def strategy_workspace_client(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> TestClient:
    _patch_storage_paths(monkeypatch, tmp_path)
    storage.ensure_strategy_config_initialized()
    monkeypatch.setattr(
        strategy_api,
        "load_dataset_schema",
        lambda dataset_id: SimpleNamespace(
            available_marts={"gold_sales_daily", "gold_customer_360"},
            mart_columns={
                "gold_sales_daily": {"sales_date", "net_sales", "region", "store_id"},
                "gold_customer_360": {"customer_id", "segment", "cohort"},
            },
        ),
    )
    monkeypatch.setattr(
        strategy_api,
        "compute_readiness_and_coverage",
        lambda **_: (
            {
                "overall_score": 0.82,
                "strategy_completeness": 0.9,
                "kpi_completeness": 0.8,
                "target_completeness": 0.75,
                "rule_completeness": 0.7,
                "reconciliation_completeness": 0.8,
                "data_readiness": 0.9,
                "explanation": "Test readiness payload.",
            },
            [],
            {"readiness_notes": ["Targets are partially defined."]},
            {"kpis_defined": True, "targets_defined": True, "rules_defined": True, "placeholders": []},
        ),
    )

    app = FastAPI()
    app.include_router(bundle_router, prefix="/api")
    app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(id=1, username="tester")
    return TestClient(app)


def test_workspace_state_returns_consolidated_strategy_payload(
    strategy_workspace_client: TestClient,
) -> None:
    response = strategy_workspace_client.get("/api/strategy/workspace-state?dataset_id=silkroute")

    assert response.status_code == 200
    payload = response.json()
    assert payload["decision_state"]["revision"] == "r0001"
    assert payload["strategy_bundle"]["revision"] == "r0001"
    assert payload["kpi_bundle"]["revision"] == "r0001"
    assert payload["overview"]["revision"] == "r0001"
    assert payload["targets"]["revision"] == "r0001"
    assert payload["rules"]["revision"] == "r0001"
    assert payload["kpi_library"]["revision"] == "r0001"
    assert "base_yaml" in payload["strategy_bundle"]
    assert "override_yaml" in payload["strategy_bundle"]
    assert "base_yaml" in payload["kpi_bundle"]
    assert payload["kpi_library"]["available_marts"] == ["gold_customer_360", "gold_sales_daily"]
    assert payload["decision_state"]["readiness"]["overall_score"] == 0.82
    assert payload["decision_state"]["readiness_notes"] == ["Targets are partially defined."]
