"""Dataset-aware registry for supported marts."""

from __future__ import annotations

from typing import Any

DEFAULT_DATASET_ID = "silkroute"

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

_DATASET_MARTS: dict[str, list[dict[str, Any]]] = {
    DEFAULT_DATASET_ID: MARTS,
}


def supported_dataset_ids() -> list[str]:
    return sorted(_DATASET_MARTS.keys())


def is_supported_dataset(dataset_id: str) -> bool:
    return dataset_id in _DATASET_MARTS


def get_registry(dataset_id: str) -> list[dict[str, Any]]:
    if not is_supported_dataset(dataset_id):
        raise KeyError(f"Unsupported dataset_id '{dataset_id}'")
    return [dict(mart) for mart in _DATASET_MARTS[dataset_id]]


def list_marts(dataset_id: str = DEFAULT_DATASET_ID) -> list[dict[str, Any]]:
    return get_registry(dataset_id)


def get_mart_ids(dataset_id: str = DEFAULT_DATASET_ID) -> list[str]:
    return [str(mart["id"]) for mart in list_marts(dataset_id)]


def get_mart(dataset_id: str, mart_id: str) -> dict[str, Any]:
    for mart in list_marts(dataset_id):
        if str(mart["id"]) == mart_id:
            return mart
    raise KeyError(f"Mart '{mart_id}' is not registered for dataset '{dataset_id}'")


def get_mart_by_id(mart_id: str, dataset_id: str = DEFAULT_DATASET_ID) -> dict[str, Any] | None:
    try:
        return get_mart(dataset_id, mart_id)
    except KeyError:
        return None


def is_valid_mart_id(mart_id: str, dataset_id: str = DEFAULT_DATASET_ID) -> bool:
    return get_mart_by_id(mart_id, dataset_id=dataset_id) is not None
