"""Central registry for supported marts."""

from __future__ import annotations

from typing import Any

MARTS = [
    {
        "id": "gold_sales_daily",
        "label": "Sales Daily",
        "description": "Daily x store x channel sales fact table",
        "schema": "gold",
        "profile_file": "gold_sales_daily_profile.json",
    },
    {
        "id": "gold_store_sku_daily",
        "label": "Store-SKU Daily",
        "description": "Daily x store x sku fact table",
        "schema": "gold",
        "profile_file": "gold_store_sku_daily_profile.json",
    },
    {
        "id": "gold_store_360",
        "label": "Store 360",
        "description": "Store-level performance scorecard",
        "schema": "gold",
        "profile_file": "gold_store_360_profile.json",
    },
    {
        "id": "gold_product_360",
        "label": "Product 360",
        "description": "SKU-level performance scorecard",
        "schema": "gold",
        "profile_file": "gold_product_360_profile.json",
    },
    {
        "id": "gold_customer_360",
        "label": "Customer 360",
        "description": "Customer-level scorecard (RFM etc.)",
        "schema": "gold",
        "profile_file": "gold_customer_360_profile.json",
    },
    {
        "id": "gold_employee_360",
        "label": "Employee 360",
        "description": "Salesperson performance scorecard",
        "schema": "gold",
        "profile_file": "gold_employee_360_profile.json",
    },
    {
        "id": "gold_inventory_health_daily",
        "label": "Inventory Health Daily",
        "description": "Inventory health + velocity + reorder signals",
        "schema": "gold",
        "profile_file": "gold_inventory_health_daily_profile.json",
    },
]


def list_marts() -> list[dict[str, Any]]:
    return [dict(mart) for mart in MARTS]


def get_mart_ids() -> list[str]:
    return [str(mart["id"]) for mart in MARTS]


def get_mart_by_id(mart_id: str) -> dict[str, Any] | None:
    for mart in MARTS:
        if mart["id"] == mart_id:
            return dict(mart)
    return None


def is_valid_mart_id(mart_id: str) -> bool:
    return get_mart_by_id(mart_id) is not None
