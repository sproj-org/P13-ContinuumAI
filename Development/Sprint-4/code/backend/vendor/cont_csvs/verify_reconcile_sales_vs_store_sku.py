#!/usr/bin/env python3
"""
Verify reconciliation between gold_sales_daily and gold_store_sku_daily at store-day grain.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd


METRICS = [
    "net_sales",
    "gross_sales",
    "discount_amount",
    "returns_amount",
    "net_sales_after_returns",
    "units",
]


def main() -> None:
    sales_path = Path("./gold_csv/gold_sales_daily.csv")
    bridge_path = Path("./gold_csv/gold_store_sku_daily.csv")

    if not sales_path.exists():
        raise FileNotFoundError(f"Missing file: {sales_path}")
    if not bridge_path.exists():
        raise FileNotFoundError(f"Missing file: {bridge_path}")

    sales = pd.read_csv(sales_path)
    bridge = pd.read_csv(bridge_path)

    sales["sales_date"] = pd.to_datetime(sales["sales_date"], errors="coerce").dt.date
    bridge["sales_date"] = pd.to_datetime(bridge["sales_date"], errors="coerce").dt.date

    sales["store_id"] = sales["store_id"].astype(str).str.strip().replace({"ONLINE": "S000"})
    bridge["store_id"] = bridge["store_id"].astype(str).str.strip()

    for m in METRICS:
        sales[m] = pd.to_numeric(sales[m], errors="coerce").fillna(0.0)
        bridge[m] = pd.to_numeric(bridge[m], errors="coerce").fillna(0.0)

    sales_sd = sales.groupby(["sales_date", "store_id"], as_index=False)[METRICS].sum()
    bridge_sd = bridge.groupby(["sales_date", "store_id"], as_index=False)[METRICS].sum()

    rec = sales_sd.merge(
        bridge_sd,
        on=["sales_date", "store_id"],
        how="outer",
        suffixes=("_daily", "_sku"),
    ).fillna(0.0)

    for m in METRICS:
        rec[f"diff_{m}"] = rec[f"{m}_daily"] - rec[f"{m}_sku"]

    print("Reconciliation summary (store-day)")
    print("----------------------------------")
    rows = []
    for m in METRICS:
        abs_diff = rec[f"diff_{m}"].abs()
        rows.append(
            {
                "metric": m,
                "max_abs_diff": float(abs_diff.max()),
                "pairs_with_abs_diff_gt_0_01": int((abs_diff > 0.01).sum()),
            }
        )
    summary = pd.DataFrame(rows)
    print(summary.to_string(index=False))

    print("\nTop 10 mismatches by abs(diff_discount_amount):")
    top = rec.assign(abs_diff_discount_amount=rec["diff_discount_amount"].abs()).sort_values(
        "abs_diff_discount_amount", ascending=False
    )
    cols = [
        "sales_date",
        "store_id",
        "discount_amount_daily",
        "discount_amount_sku",
        "diff_discount_amount",
        "abs_diff_discount_amount",
    ]
    print(top[cols].head(10).to_string(index=False))

    print("\nOverall totals (daily vs sku_rollup and diff):")
    total_rows = []
    for m in METRICS:
        daily_total = float(rec[f"{m}_daily"].sum())
        sku_total = float(rec[f"{m}_sku"].sum())
        total_rows.append(
            {
                "metric": m,
                "daily_total": daily_total,
                "sku_rollup_total": sku_total,
                "total_diff": daily_total - sku_total,
            }
        )
    totals = pd.DataFrame(total_rows)
    print(totals.to_string(index=False))


if __name__ == "__main__":
    main()
