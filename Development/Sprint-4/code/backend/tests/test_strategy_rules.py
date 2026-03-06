from __future__ import annotations

import os
from pathlib import Path
from types import SimpleNamespace

from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest

os.environ["DATABASE_URL"] = "sqlite:///./test_strategy_rules.db"
os.environ.setdefault("JWT_SECRET_KEY", "test-secret")

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
def strategy_rules_client(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> TestClient:
    _patch_storage_paths(monkeypatch, tmp_path)
    storage.ensure_strategy_config_initialized()
    storage.write_yaml(
        storage.BASE_KPI_PATH,
        {
            "schema_version": 1,
            "version": "1.0.0",
            "kpis": [
                {
                    "id": "sales_growth",
                    "description": "Sales growth",
                    "formula": "sum(net_sales)",
                    "marts": [],
                    "required_columns": [],
                    "dimensions": [],
                }
            ],
            "aliases": {},
            "derived_metrics": {},
        },
    )

    app = FastAPI()
    app.include_router(bundle_router, prefix="/api")
    app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(id=1, username="tester")
    return TestClient(app)


def test_rules_crud(strategy_rules_client: TestClient) -> None:
    fetched = strategy_rules_client.get("/api/strategy/rules")
    assert fetched.status_code == 200
    start = fetched.json()
    assert start["revision"] == "r0001"
    assert start["rules"] == []
    assert start["available_kpis"] == ["sales_growth"]

    created = strategy_rules_client.post(
        "/api/strategy/rules",
        json={
            "expected_revision": start["revision"],
            "rule": {
                "id": "rule_sales_guardrail",
                "condition": 'kpi("sales_growth") < 0.05',
                "action": "Alert owner",
                "severity": "warn",
                "rationale": "Catch low growth",
            },
            "author": "tester",
            "reason": "create rule",
        },
    )
    assert created.status_code == 200
    created_payload = created.json()
    assert created_payload["revision"] == "r0002"
    assert created_payload["rules"][0]["id"] == "rule_sales_guardrail"

    updated = strategy_rules_client.put(
        "/api/strategy/rules/rule_sales_guardrail",
        json={
            "expected_revision": created_payload["revision"],
            "rule": {
                "id": "rule_sales_guardrail",
                "condition": 'kpi("sales_growth") < 0.03',
                "action": "Escalate to finance",
                "severity": "block",
                "rationale": "Critical threshold",
            },
            "author": "tester",
            "reason": "update rule",
        },
    )
    assert updated.status_code == 200
    updated_payload = updated.json()
    assert updated_payload["revision"] == "r0003"
    assert updated_payload["rules"][0]["severity"] == "block"

    deleted = strategy_rules_client.request(
        "DELETE",
        "/api/strategy/rules/rule_sales_guardrail",
        json={
            "expected_revision": updated_payload["revision"],
            "author": "tester",
            "reason": "delete rule",
        },
    )
    assert deleted.status_code == 200
    deleted_payload = deleted.json()
    assert deleted_payload["revision"] == "r0004"
    assert deleted_payload["rules"] == []


def test_rules_reference_validation(strategy_rules_client: TestClient) -> None:
    fetched = strategy_rules_client.get("/api/strategy/rules")
    assert fetched.status_code == 200
    revision = fetched.json()["revision"]

    invalid = strategy_rules_client.post(
        "/api/strategy/rules",
        json={
            "expected_revision": revision,
            "rule": {
                "id": "rule_invalid",
                "condition": 'kpi("unknown_metric") < 0.2',
                "action": "Do something",
                "severity": "warn",
            },
            "author": "tester",
            "reason": "invalid ref",
        },
    )
    assert invalid.status_code == 422
    detail = invalid.json()["detail"]
    assert detail["code"] == "VALIDATION_ERROR"
