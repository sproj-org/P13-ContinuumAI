from __future__ import annotations

import os

os.environ.setdefault("DATABASE_URL", "sqlite:///./test_kpi_registry_semantics.db")
os.environ.setdefault("JWT_SECRET_KEY", "test-secret")

from app.models.kpi_registry import KPIRegistry
from app.services.strategy.storage import load_current_artifacts


def test_seeded_kpis_include_semantic_and_drill_metadata() -> None:
    _strategy_payload, kpi_payload, _revision = load_current_artifacts()
    registry = KPIRegistry.model_validate(kpi_payload)

    assert len(registry.kpis) >= 10
    for kpi in registry.kpis:
        assert kpi.semantic_family
        assert kpi.business_concepts
        assert kpi.preferred_drill_path or kpi.mart_drill_overrides
        assert kpi.terminal_dimensions


def test_seeded_kpis_cover_deeper_business_hierarchies() -> None:
    _strategy_payload, kpi_payload, _revision = load_current_artifacts()
    registry = KPIRegistry.model_validate(kpi_payload)
    kpis = {kpi.id: kpi for kpi in registry.kpis}

    assert kpis["net_sales_growth"].preferred_drill_path[:4] == ["region", "city", "store_type", "store_id"]
    assert kpis["repeat_customer_rate"].preferred_drill_path[-2:] == ["top_category", "customer_id"]
    assert kpis["sell_through_rate"].preferred_drill_path[:3] == ["stockout_risk_flag", "store_id", "sku_id"]
    assert kpis["transactions"].preferred_drill_path[4:8] == ["store_id", "category", "brand", "product_id"]
    assert kpis["gross_margin_proxy"].mart_drill_overrides["gold_sales_daily"][5:9] == ["category", "brand", "product_id", "sku_id"]
    assert kpis["1"].mart_drill_overrides["gold_sales_daily"][-5:] == ["category", "brand", "product_id", "sku_id", "sales_date"]
