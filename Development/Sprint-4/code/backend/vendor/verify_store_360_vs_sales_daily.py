#!/usr/bin/env python3
"""
Verify gold_store_360 metrics against recomputation from gold_sales_daily.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd


THRESHOLD = 1e-6


def _safe_div(num: pd.Series, den: pd.Series) -> pd.Series:
    n = pd.to_numeric(num, errors="coerce").fillna(0.0)
    d = pd.to_numeric(den, errors="coerce").fillna(0.0)
    out = pd.Series(0.0, index=n.index)
    mask = d > 0
    out.loc[mask] = n.loc[mask] / d.loc[mask]
    return out


def main() -> None:
    sales_path = Path("./gold_csv/gold_sales_daily.csv")
    store_path = Path("./gold_csv/gold_store_360.csv")

    if not sales_path.exists():
        raise FileNotFoundError(f"Missing file: {sales_path}")
    if not store_path.exists():
        raise FileNotFoundError(f"Missing file: {store_path}")

    sales = pd.read_csv(sales_path)
    store = pd.read_csv(store_path)

    sales["sales_date"] = pd.to_datetime(sales["sales_date"], errors="coerce").dt.date
    sales["store_id"] = sales["store_id"].astype(str).str.strip().replace({"ONLINE": "S000"})
    store["store_id"] = store["store_id"].astype(str).str.strip().replace({"ONLINE": "S000"})

    for col in ["net_sales", "gross_sales", "discount_amount", "returns_amount"]:
        sales[col] = pd.to_numeric(sales[col], errors="coerce").fillna(0.0)
    sales["channel_type_norm"] = sales["channel_type"].astype(str).str.strip().str.lower()
    sales["online_net_sales"] = sales["net_sales"].where(sales["channel_type_norm"] == "online", 0.0)

    expected = sales.groupby("store_id", as_index=False).agg(
        net_sales_sum=("net_sales", "sum"),
        gross_sales_sum=("gross_sales", "sum"),
        discount_amount_sum=("discount_amount", "sum"),
        returns_amount_sum=("returns_amount", "sum"),
        online_net_sales=("online_net_sales", "sum"),
    )
    expected["expected_weighted_discount_ratio"] = _safe_div(
        expected["discount_amount_sum"], expected["gross_sales_sum"]
    )
    expected["expected_returns_rate_amount"] = _safe_div(
        expected["returns_amount_sum"], expected["net_sales_sum"]
    )
    expected["expected_channel_mix_online_pct"] = _safe_div(
        expected["online_net_sales"], expected["net_sales_sum"]
    )

    for col in ["weighted_discount_ratio", "returns_rate_amount", "channel_mix_online_pct", "net_sales"]:
        store[col] = pd.to_numeric(store[col], errors="coerce").fillna(0.0)

    actual = store[["store_id", "weighted_discount_ratio", "returns_rate_amount", "channel_mix_online_pct", "net_sales"]]

    rec = expected.merge(actual, on="store_id", how="outer").fillna(0.0)
    rec["diff_weighted_discount_ratio"] = (
        rec["weighted_discount_ratio"] - rec["expected_weighted_discount_ratio"]
    )
    rec["diff_returns_rate_amount"] = rec["returns_rate_amount"] - rec["expected_returns_rate_amount"]
    rec["diff_channel_mix_online_pct"] = (
        rec["channel_mix_online_pct"] - rec["expected_channel_mix_online_pct"]
    )
    rec["diff_net_sales"] = rec["net_sales"] - rec["net_sales_sum"]

    metric_pairs = [
        ("weighted_discount_ratio", "diff_weighted_discount_ratio"),
        ("returns_rate_amount", "diff_returns_rate_amount"),
        ("channel_mix_online_pct", "diff_channel_mix_online_pct"),
        ("net_sales", "diff_net_sales"),
    ]

    print("Store 360 validation vs sales_daily")
    print("-----------------------------------")
    rows = []
    pass_fail = True
    for metric, diff_col in metric_pairs:
        abs_diff = rec[diff_col].abs()
        max_abs = float(abs_diff.max())
        gt = int((abs_diff > THRESHOLD).sum())
        rows.append(
            {
                "metric": metric,
                "max_abs_diff": max_abs,
                "stores_with_abs_diff_gt_1e-6": gt,
            }
        )
        if metric in {
            "weighted_discount_ratio",
            "returns_rate_amount",
            "channel_mix_online_pct",
        } and max_abs > THRESHOLD:
            pass_fail = False
    print(pd.DataFrame(rows).to_string(index=False))
    print(f"\nVALIDATION: {'PASS' if pass_fail else 'FAIL'}")

    rec["max_abs_core_diff"] = rec[
        [
            "diff_weighted_discount_ratio",
            "diff_returns_rate_amount",
            "diff_channel_mix_online_pct",
        ]
    ].abs().max(axis=1)

    print("\nTop mismatches by core metric abs diff:")
    print(
        rec.sort_values("max_abs_core_diff", ascending=False)[
            [
                "store_id",
                "expected_weighted_discount_ratio",
                "weighted_discount_ratio",
                "diff_weighted_discount_ratio",
                "expected_returns_rate_amount",
                "returns_rate_amount",
                "diff_returns_rate_amount",
                "expected_channel_mix_online_pct",
                "channel_mix_online_pct",
                "diff_channel_mix_online_pct",
                "net_sales_sum",
                "net_sales",
                "diff_net_sales",
            ]
        ].to_string(index=False)
    )

    if not pass_fail:
        offenders = rec[rec["max_abs_core_diff"] > THRESHOLD][
            ["store_id", "max_abs_core_diff"]
        ].sort_values("max_abs_core_diff", ascending=False)
        print("\nOffending stores (core metrics > 1e-6):")
        print(offenders.to_string(index=False))


if __name__ == "__main__":
    main()
