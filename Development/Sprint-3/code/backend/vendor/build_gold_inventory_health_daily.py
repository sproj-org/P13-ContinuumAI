#!/usr/bin/env python3
"""
Build GOLD inventory health daily table with momentum-adjusted velocity.

Input:
  ./silver_csv/inventory_snapshots.csv
  ./silver_csv/transactions.csv
  ./silver_csv/transaction_lines.csv

Output:
  ./gold_csv/gold_inventory_health_daily.csv
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd


def _to_numeric(series: pd.Series, name: str) -> pd.Series:
    raw_na = series.isna().sum()
    numeric = pd.to_numeric(series, errors="coerce")
    coerced = int(numeric.isna().sum() - raw_na)
    if coerced > 0:
        print(f"Warning: coerced {coerced} non-numeric values in {name} to 0.")
    return numeric.fillna(0.0)


def _days_inventory(stock: pd.Series, velocity: pd.Series) -> pd.Series:
    s = pd.to_numeric(stock, errors="coerce").fillna(0.0)
    v = pd.to_numeric(velocity, errors="coerce").fillna(0.0)
    return np.where(v > 0, s / v, np.where(s > 0, np.inf, 0.0))


def _cum_lookup(inv: pd.DataFrame, sales_cum: pd.DataFrame, target_col: str, out_col: str) -> None:
    left = (
        inv[["row_id", "store_id", "sku_id", target_col]]
        .rename(columns={target_col: "lookup_date"})
        .sort_values(["lookup_date", "store_id", "sku_id", "row_id"])
    )
    right = sales_cum.sort_values(["sales_date", "store_id", "sku_id"])

    merged = pd.merge_asof(
        left,
        right,
        left_on="lookup_date",
        right_on="sales_date",
        by=["store_id", "sku_id"],
        direction="backward",
        allow_exact_matches=True,
    )
    vals = merged.set_index("row_id")["cum_units"]
    inv[out_col] = inv["row_id"].map(vals).fillna(0.0)


def main() -> None:
    input_dir = Path("./silver_csv")
    output_dir = Path("./gold_csv")
    output_dir.mkdir(parents=True, exist_ok=True)

    inv_path = input_dir / "inventory_snapshots.csv"
    tx_path = input_dir / "transactions.csv"
    lines_path = input_dir / "transaction_lines.csv"

    for p in [inv_path, tx_path, lines_path]:
        if not p.exists():
            raise FileNotFoundError(f"Required input file not found: {p}")

    inv = pd.read_csv(inv_path)
    tx = pd.read_csv(tx_path)
    lines = pd.read_csv(lines_path)

    req_inv = ["snapshot_date", "store_id", "sku_id", "stock_on_hand", "stock_on_order"]
    req_tx = ["transaction_id", "transaction_ts", "store_id", "channel_type"]
    req_lines = ["transaction_id", "sku_id", "quantity"]
    miss_inv = [c for c in req_inv if c not in inv.columns]
    miss_tx = [c for c in req_tx if c not in tx.columns]
    miss_lines = [c for c in req_lines if c not in lines.columns]
    if miss_inv:
        raise ValueError(f"inventory_snapshots.csv missing required columns: {miss_inv}")
    if miss_tx:
        raise ValueError(f"transactions.csv missing required columns: {miss_tx}")
    if miss_lines:
        raise ValueError(f"transaction_lines.csv missing required columns: {miss_lines}")

    inv = inv[req_inv].copy()
    tx = tx[req_tx].copy()
    lines = lines[req_lines].copy()

    # Key integrity + type normalization (merge_asof requires matching dtypes for by= keys).
    inv_key_nulls = inv[["snapshot_date", "store_id", "sku_id"]].isna().any(axis=1)
    if inv_key_nulls.any():
        raise ValueError(
            f"DQ failed: found {int(inv_key_nulls.sum())} rows with null snapshot_date/store_id/sku_id in inventory_snapshots.csv."
        )

    # Normalize identifiers to strings to avoid silent join misses (e.g., int vs str).
    inv["store_id"] = inv["store_id"].astype(str).str.strip()
    inv["sku_id"] = inv["sku_id"].astype(str).str.strip()
    tx["transaction_id"] = tx["transaction_id"].astype(str).str.strip()
    tx["store_id"] = tx["store_id"].astype(str).str.strip()
    tx["channel_type"] = tx["channel_type"].astype(str).str.strip()
    lines["transaction_id"] = lines["transaction_id"].astype(str).str.strip()
    lines["sku_id"] = lines["sku_id"].astype(str).str.strip()

    inv["snapshot_date"] = pd.to_datetime(inv["snapshot_date"], errors="coerce").dt.normalize()
    tx["transaction_ts"] = pd.to_datetime(tx["transaction_ts"], errors="coerce")
    tx["sales_date"] = tx["transaction_ts"].dt.normalize()
    tx["store_id"] = tx["store_id"].replace({"nan": "", "None": ""}).fillna("")
    # Online transactions have null store_id in transactions.csv; map them to S000 to align with inventory_snapshots.csv.
    tx.loc[tx["store_id"].eq(""), "store_id"] = "S000"

    lines["quantity"] = _to_numeric(lines["quantity"], "transaction_lines.quantity")
    inv["stock_on_hand"] = _to_numeric(inv["stock_on_hand"], "inventory_snapshots.stock_on_hand")
    inv["stock_on_order"] = _to_numeric(inv["stock_on_order"], "inventory_snapshots.stock_on_order")

    bad_tx_ts = int(tx["sales_date"].isna().sum())
    if bad_tx_ts > 0:
        print(f"Warning: dropping {bad_tx_ts} transaction rows with invalid transaction_ts.")
        tx = tx.dropna(subset=["sales_date"])

    tx = tx.drop_duplicates(subset=["transaction_id"], keep="last")

    line_level = lines.merge(
        tx[["transaction_id", "store_id", "sales_date"]],
        on="transaction_id",
        how="inner",
        validate="many_to_one",
    )[["store_id", "sku_id", "quantity", "sales_date"]]

    dropped_lines = len(lines) - len(line_level)
    if dropped_lines > 0:
        print(f"Warning: dropped {dropped_lines} transaction_lines rows without matching transaction_id in transactions.csv.")

    sales_daily = (
        line_level.groupby(["store_id", "sku_id", "sales_date"], as_index=False)["quantity"]
        .sum()
        .rename(columns={"quantity": "units_day"})
        .sort_values(["store_id", "sku_id", "sales_date"])
    )
    sales_daily["cum_units"] = sales_daily.groupby(["store_id", "sku_id"])["units_day"].cumsum()
    sales_cum = sales_daily[["store_id", "sku_id", "sales_date", "cum_units"]].copy()

    out = inv.copy()
    out["row_id"] = np.arange(len(out))
    out["d_end"] = out["snapshot_date"]
    out["d_m14"] = out["snapshot_date"] - pd.Timedelta(days=14)
    out["d_m28"] = out["snapshot_date"] - pd.Timedelta(days=28)

    _cum_lookup(out, sales_cum, "d_end", "cum_end")
    _cum_lookup(out, sales_cum, "d_m14", "cum_m14")
    _cum_lookup(out, sales_cum, "d_m28", "cum_m28")

    out["units_28d"] = (out["cum_end"] - out["cum_m28"]).clip(lower=0.0)
    out["units_last_14d"] = (out["cum_end"] - out["cum_m14"]).clip(lower=0.0)
    out["units_prev_14d"] = (out["cum_m14"] - out["cum_m28"]).clip(lower=0.0)

    out["avg_daily_units_28d"] = out["units_28d"] / 28.0

    epsilon = 1.0
    out["momentum_factor"] = (out["units_last_14d"] + epsilon) / (out["units_prev_14d"] + epsilon)
    out["momentum_clipped"] = out["momentum_factor"].clip(lower=0.5, upper=1.5)
    out["adj_avg_daily_units"] = out["avg_daily_units_28d"] * out["momentum_clipped"]

    out["days_of_inventory"] = _days_inventory(out["stock_on_hand"], out["avg_daily_units_28d"])
    out["adj_days_of_inventory"] = _days_inventory(out["stock_on_hand"], out["adj_avg_daily_units"])

    out["stockout_risk_flag"] = (out["adj_days_of_inventory"] < 7).astype(int)
    out["overstock_flag"] = (out["adj_days_of_inventory"] > 60).astype(int)

    target_DOI = 30.0
    out["reorder_qty_suggestion"] = np.maximum(
        0.0,
        (target_DOI * out["adj_avg_daily_units"]) - out["stock_on_hand"],
    )

    # DQ checks
    if (out["stock_on_hand"] < 0).any():
        bad = int((out["stock_on_hand"] < 0).sum())
        raise ValueError(f"DQ failed: found {bad} rows where stock_on_hand < 0.")
    if (out["avg_daily_units_28d"] < 0).any():
        bad = int((out["avg_daily_units_28d"] < 0).sum())
        raise ValueError(f"DQ failed: found {bad} rows where avg_daily_units_28d < 0.")
    if (out["momentum_factor"] < 0).any():
        bad = int((out["momentum_factor"] < 0).sum())
        raise ValueError(f"DQ failed: found {bad} rows where momentum_factor < 0.")
    if (out["days_of_inventory"] < 0).any():
        bad = int((out["days_of_inventory"] < 0).sum())
        raise ValueError(f"DQ failed: found {bad} rows where days_of_inventory < 0.")

    extreme_adj = int((out["adj_days_of_inventory"] > 365).sum())
    if extreme_adj > 0:
        print(f"Warning: found {extreme_adj} rows where adj_days_of_inventory > 365.")

    final_cols = [
        "snapshot_date",
        "store_id",
        "sku_id",
        "stock_on_hand",
        "stock_on_order",
        "units_28d",
        "avg_daily_units_28d",
        "momentum_factor",
        "adj_avg_daily_units",
        "days_of_inventory",
        "adj_days_of_inventory",
        "stockout_risk_flag",
        "overstock_flag",
        "reorder_qty_suggestion",
    ]
    out = out[final_cols].copy()

    out["snapshot_date"] = pd.to_datetime(out["snapshot_date"]).dt.date
    out["stockout_risk_flag"] = out["stockout_risk_flag"].astype(int)
    out["overstock_flag"] = out["overstock_flag"].astype(int)
    for col in [
        "stock_on_hand",
        "stock_on_order",
        "units_28d",
        "avg_daily_units_28d",
        "momentum_factor",
        "adj_avg_daily_units",
        "days_of_inventory",
        "adj_days_of_inventory",
        "reorder_qty_suggestion",
    ]:
        out[col] = pd.to_numeric(out[col], errors="coerce")

    out_path = output_dir / "gold_inventory_health_daily.csv"
    out.to_csv(out_path, index=False)
    print(f"Wrote: {out_path}")

    risk = out[out["stockout_risk_flag"] == 1].sort_values("adj_days_of_inventory", ascending=True)
    if risk.empty:
        risk = out.sort_values("adj_days_of_inventory", ascending=True)
    print("\nTop 10 highest stockout risk SKUs:")
    print(
        risk[
            ["snapshot_date", "store_id", "sku_id", "stock_on_hand", "adj_days_of_inventory", "reorder_qty_suggestion"]
        ]
        .head(10)
        .to_string(index=False)
    )

    over = out[out["overstock_flag"] == 1].sort_values("adj_days_of_inventory", ascending=False)
    if over.empty:
        over = out.sort_values("adj_days_of_inventory", ascending=False)
    print("\nTop 10 highest overstock SKUs:")
    print(
        over[
            ["snapshot_date", "store_id", "sku_id", "stock_on_hand", "adj_days_of_inventory", "reorder_qty_suggestion"]
        ]
        .head(10)
        .to_string(index=False)
    )

    mom = pd.to_numeric(out["momentum_factor"], errors="coerce")
    print("\nMomentum factor summary:")
    print(
        f"count={int(mom.notna().sum())}, min={mom.min():.4f}, median={mom.median():.4f}, "
        f"p95={mom.quantile(0.95):.4f}, max={mom.max():.4f}"
    )


if __name__ == "__main__":
    main()
