from __future__ import annotations
from dataclasses import dataclass
from typing import List, Tuple

@dataclass
class Config:
    seed: int = 42

    # Targets
    n_stores: int = 6
    n_products: int = 90
    n_skus_target: int = 150
    n_customers: int = 2500
    n_transactions: int = 15000
    n_lines_target: int = 30000
    n_salespeople: int = 26
    return_rate_target: Tuple[float, float] = (0.08, 0.12)

    # Date window
    start_date: str = "2025-01-01"
    end_date: str = "2025-12-31"

    # Cities/regions
    cities: List[Tuple[str, str]] = None  # default in dimensions.py

    # Seeded patterns
    online_share_start: float = 0.22
    online_share_end: float = 0.42

    hero_sku_count: int = 10
    high_return_sku_count: int = 8

    underperforming_store_count: int = 2
    discount_heavy_store_count: int = 2
    top_salespeople_count: int = 4

    # Knobs (pattern strength)
    hero_primary_pick_prob: float = 0.45      # stronger hero concentration
    clearance_line_prob: float = 0.015        # visible extreme tail
    clearance_discount_min: float = 0.30
    clearance_discount_max: float = 0.45

    # Returns outlier knobs
    high_return_sku_weight_mult: float = 6.0   # was 3.0
    high_return_customer_weight_mult: float = 3.0  # was 2.3
    high_return_customer_3line_prob: float = 0.20
    return_two_lines_prob: float = 0.15

    # Inventory cadence
    inventory_snapshot_freq_days: int = 7
