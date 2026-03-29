#!/usr/bin/env python3
"""
Build GOLD store 360 table from gold_sales_daily.

Input:
    ./gold_csv/gold_sales_daily.csv

Output:
    ./gold_csv/gold_store_360.csv
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd


def _safe_div(numerator: pd.Series, denominator: pd.Series) -> pd.Series:
    n = pd.to_numeric(numerator, errors="coerce").fillna(0.0)
    d = pd.to_numeric(denominator, errors="coerce").fillna(0.0)
    return np.where(d > 0, n / d, 0.0)


def _first_non_null(series: pd.Series):
    s = series.dropna()
    return s.iloc[0] if not s.empty else np.nan


def _run_dq(gold: pd.DataFrame) -> None:
    if gold["store_id"].isna().any():
        bad = int(gold["store_id"].isna().sum())
        raise ValueError(f"DQ failed: found {bad} rows with null store_id.")

    if gold["store_id"].duplicated().any():
        bad = int(gold["store_id"].duplicated().sum())
        raise ValueError(f"DQ failed: found {bad} duplicate store_id rows.")

    non_negative_cols = [
        "net_sales",
        "orders",
        "units",
        "gross_sales",
        "discount_amount",
        "returns_amount",
        "net_sales_after_returns",
    ]
    for col in non_negative_cols:
        bad = int((pd.to_numeric(gold[col], errors="coerce") < 0).sum())
        if bad > 0:
            raise ValueError(f"DQ failed: found {bad} rows where {col} < 0.")

    ratio_cols = [
        "weighted_discount_ratio",
        "returns_rate_amount",
        "channel_mix_online_pct",
    ]
    for col in ratio_cols:
        bad = int((~gold[col].between(0, 1.5, inclusive="both")).sum())
        if bad > 0:
            print(f"Warning: found {bad} rows where {col} is outside [0, 1.5].")


def main() -> None:
    input_path = Path("./gold_csv/gold_sales_daily.csv")
    output_dir = Path("./gold_csv")
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / "gold_store_360.csv"

    if not input_path.exists():
        raise FileNotFoundError(f"Required input file not found: {input_path}")

    df = pd.read_csv(input_path)
    required = [
        "sales_date",
        "channel_type",
        "store_id",
        "city",
        "region",
        "store_type",
        "orders",
        "units",
        "gross_sales",
        "discount_amount",
        "net_sales",
        "returns_amount",
        "net_sales_after_returns",
    ]
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise ValueError(f"gold_sales_daily.csv missing required columns: {missing}")

    df = df.copy()
    df["sales_date"] = pd.to_datetime(df["sales_date"], errors="coerce")
    bad_dates = int(df["sales_date"].isna().sum())
    if bad_dates > 0:
        raise ValueError(f"Found {bad_dates} rows with invalid sales_date.")
    df["store_id"] = df["store_id"].astype(str).str.strip().replace({"ONLINE": "S000"})

    numeric_cols = [
        "orders",
        "units",
        "gross_sales",
        "discount_amount",
        "net_sales",
        "returns_amount",
        "net_sales_after_returns",
    ]
    for col in numeric_cols:
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0.0)

    df["channel_type_norm"] = (
        df["channel_type"]
        .where(df["channel_type"].notna(), "")
        .astype(str)
        .str.strip()
        .str.lower()
    )
    df["online_net_sales"] = np.where(df["channel_type_norm"] == "online", df["net_sales"], 0.0)

    store_agg = (
        df.groupby("store_id", as_index=False)
        .agg(
            city=("city", _first_non_null),
            region=("region", _first_non_null),
            store_type=("store_type", _first_non_null),
            first_date=("sales_date", "min"),
            last_date=("sales_date", "max"),
            active_days=("sales_date", "nunique"),
            net_sales=("net_sales", "sum"),
            orders=("orders", "sum"),
            units=("units", "sum"),
            gross_sales=("gross_sales", "sum"),
            discount_amount=("discount_amount", "sum"),
            returns_amount=("returns_amount", "sum"),
            net_sales_after_returns=("net_sales_after_returns", "sum"),
            online_net_sales=("online_net_sales", "sum"),
        )
        .reset_index(drop=True)
    )

    store_agg["avg_order_value"] = _safe_div(store_agg["net_sales"], store_agg["orders"])
    store_agg["weighted_discount_ratio"] = _safe_div(store_agg["discount_amount"], store_agg["gross_sales"])
    store_agg["returns_rate_amount"] = _safe_div(store_agg["returns_amount"], store_agg["net_sales"])
    store_agg["channel_mix_online_pct"] = _safe_div(store_agg["online_net_sales"], store_agg["net_sales"])

    trend = df[["store_id", "sales_date", "net_sales"]].merge(
        store_agg[["store_id", "last_date"]],
        on="store_id",
        how="left",
        validate="many_to_one",
    )
    trend["day_diff"] = (trend["last_date"] - trend["sales_date"]).dt.days
    trend["last_28d_part"] = np.where(trend["day_diff"].between(0, 27, inclusive="both"), trend["net_sales"], 0.0)
    trend["prev_28d_part"] = np.where(trend["day_diff"].between(28, 55, inclusive="both"), trend["net_sales"], 0.0)
    trend_agg = (
        trend.groupby("store_id", as_index=False)
        .agg(
            last_28d_net_sales=("last_28d_part", "sum"),
            prev_28d_net_sales=("prev_28d_part", "sum"),
        )
        .reset_index(drop=True)
    )

    gold = store_agg.merge(trend_agg, on="store_id", how="left", validate="one_to_one")
    gold["last_28d_net_sales"] = gold["last_28d_net_sales"].fillna(0.0)
    gold["prev_28d_net_sales"] = gold["prev_28d_net_sales"].fillna(0.0)
    gold["net_sales_28d_growth_pct"] = _safe_div(
        gold["last_28d_net_sales"] - gold["prev_28d_net_sales"],
        gold["prev_28d_net_sales"],
    )

    gold["needs_attention"] = (
        (
            (gold["net_sales_28d_growth_pct"] < 0)
            & (gold["weighted_discount_ratio"] > 0.08)
        )
        | (gold["returns_rate_amount"] > 0.10)
    ).astype(int)

    gold["orders"] = pd.to_numeric(gold["orders"], errors="coerce").fillna(0).astype(int)
    gold["active_days"] = pd.to_numeric(gold["active_days"], errors="coerce").fillna(0).astype(int)
    for col in [
        "units",
        "net_sales",
        "avg_order_value",
        "weighted_discount_ratio",
        "returns_rate_amount",
        "net_sales_after_returns",
        "channel_mix_online_pct",
        "last_28d_net_sales",
        "prev_28d_net_sales",
        "net_sales_28d_growth_pct",
        "gross_sales",
        "discount_amount",
        "returns_amount",
    ]:
        gold[col] = pd.to_numeric(gold[col], errors="coerce").fillna(0.0)

    gold["first_date"] = pd.to_datetime(gold["first_date"]).dt.date
    gold["last_date"] = pd.to_datetime(gold["last_date"]).dt.date

    _run_dq(gold)

    gold = gold[
        [
            "store_id",
            "city",
            "region",
            "store_type",
            "first_date",
            "last_date",
            "active_days",
            "net_sales",
            "orders",
            "units",
            "avg_order_value",
            "weighted_discount_ratio",
            "returns_rate_amount",
            "net_sales_after_returns",
            "channel_mix_online_pct",
            "last_28d_net_sales",
            "prev_28d_net_sales",
            "net_sales_28d_growth_pct",
            "needs_attention",
        ]
    ]

    gold.to_csv(output_path, index=False)
    print(f"Wrote: {output_path}")

    print("\nTop 10 stores by net_sales:")
    top10 = gold.sort_values("net_sales", ascending=False).head(10)[
        ["store_id", "net_sales", "orders", "units", "needs_attention"]
    ]
    print(top10.to_string(index=False))

    print(f"\nNeeds attention stores: {int(gold['needs_attention'].sum())}")


if __name__ == "__main__":
    main()
