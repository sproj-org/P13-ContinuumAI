#!/usr/bin/env python3
"""
Build GOLD bridge table: sales_date x store_id x sku_id.

Input:
  ./silver_csv/transactions.csv
  ./silver_csv/transaction_lines.csv
  ./silver_csv/returns.csv (optional)

Output:
  ./gold_csv/gold_store_sku_daily.csv
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


def _safe_div(numerator: pd.Series, denominator: pd.Series) -> pd.Series:
    n = pd.to_numeric(numerator, errors="coerce").fillna(0.0)
    d = pd.to_numeric(denominator, errors="coerce").fillna(0.0)
    return np.where(d > 0, n / d, 0.0)


def _normalize_id(series: pd.Series) -> pd.Series:
    s = series.astype("string").str.strip()
    s = s.replace({"nan": "", "None": "", "<NA>": ""}).fillna("")
    return s.astype(str)


def main() -> None:
    input_dir = Path("./silver_csv")
    output_dir = Path("./gold_csv")
    output_dir.mkdir(parents=True, exist_ok=True)

    tx_path = input_dir / "transactions.csv"
    lines_path = input_dir / "transaction_lines.csv"
    returns_path = input_dir / "returns.csv"
    out_path = output_dir / "gold_store_sku_daily.csv"

    for p in [tx_path, lines_path]:
        if not p.exists():
            raise FileNotFoundError(f"Required input file not found: {p}")

    tx = pd.read_csv(tx_path)
    lines = pd.read_csv(lines_path)
    returns_df = pd.read_csv(returns_path) if returns_path.exists() else None

    req_tx = ["transaction_id", "transaction_ts", "store_id", "channel_type"]
    req_lines = ["transaction_id", "sku_id", "quantity", "unit_price", "line_total"]
    miss_tx = [c for c in req_tx if c not in tx.columns]
    miss_lines = [c for c in req_lines if c not in lines.columns]
    if miss_tx:
        raise ValueError(f"transactions.csv missing required columns: {miss_tx}")
    if miss_lines:
        raise ValueError(f"transaction_lines.csv missing required columns: {miss_lines}")

    tx = tx.copy()
    lines = lines.copy()
    tx["transaction_ts"] = pd.to_datetime(tx["transaction_ts"], errors="coerce")
    bad_ts = int(tx["transaction_ts"].isna().sum())
    if bad_ts > 0:
        print(f"Warning: dropping {bad_ts} transaction rows with invalid transaction_ts.")
        tx = tx.dropna(subset=["transaction_ts"])
    tx["sales_date"] = tx["transaction_ts"].dt.normalize().dt.date

    tx["transaction_id"] = _normalize_id(tx["transaction_id"])
    tx["store_id"] = _normalize_id(tx["store_id"])
    tx["channel_type"] = tx["channel_type"].astype("string").str.strip().fillna("").astype(str)
    tx.loc[tx["store_id"].eq(""), "store_id"] = "S000"

    lines["transaction_id"] = _normalize_id(lines["transaction_id"])
    lines["sku_id"] = _normalize_id(lines["sku_id"])
    lines["quantity"] = _to_numeric(lines["quantity"], "transaction_lines.quantity")
    lines["unit_price"] = _to_numeric(lines["unit_price"], "transaction_lines.unit_price")
    lines["line_total"] = _to_numeric(lines["line_total"], "transaction_lines.line_total")

    tx = tx.drop_duplicates(subset=["transaction_id"], keep="last")

    line_level = lines.merge(
        tx[["transaction_id", "store_id", "channel_type", "sales_date"]],
        on="transaction_id",
        how="inner",
        validate="many_to_one",
    )

    line_level["gross_line"] = line_level["quantity"] * line_level["unit_price"]

    if "discount" in line_level.columns and line_level["discount"].notna().any():
        disc = pd.to_numeric(line_level["discount"], errors="coerce").fillna(0.0)
        if ((disc > 1) & (disc <= 100)).any():
            disc = disc / 100.0
        elif float(disc.max()) <= 1.5:
            disc = disc
        disc = disc.clip(lower=0.0)
        line_level["discount_amount_line"] = line_level["gross_line"] * disc
    else:
        line_level["discount_amount_line"] = (
            line_level["gross_line"] - line_level["line_total"]
        ).clip(lower=0.0)

    group_cols = ["sales_date", "store_id", "sku_id"]
    gold = (
        line_level.groupby(group_cols, as_index=False)
        .agg(
            orders=("transaction_id", "nunique"),
            units=("quantity", "sum"),
            gross_sales=("gross_line", "sum"),
            discount_amount=("discount_amount_line", "sum"),
            net_sales=("line_total", "sum"),
        )
        .reset_index(drop=True)
    )

    if returns_df is not None and not returns_df.empty:
        if not {"transaction_id", "sku_id", "refund_amount"}.issubset(returns_df.columns):
            raise ValueError("returns.csv must contain transaction_id, sku_id, refund_amount.")
        ret = returns_df.copy()
        ret["transaction_id"] = _normalize_id(ret["transaction_id"])
        ret["sku_id"] = _normalize_id(ret["sku_id"])
        ret["refund_amount"] = _to_numeric(ret["refund_amount"], "returns.refund_amount")

        known_tx = set(tx["transaction_id"].astype(str).tolist())
        keep_mask = ret["transaction_id"].astype(str).isin(known_tx)
        unmatched = int((~keep_mask).sum())
        if unmatched > 0:
            print(f"Warning: {unmatched} returns rows do not match known transaction_id values; excluded.")
        ret = ret.loc[keep_mask].copy()

        ret = ret.merge(
            tx[["transaction_id", "sales_date", "store_id"]],
            on="transaction_id",
            how="inner",
            validate="many_to_one",
        )
        returns_agg = (
            ret.groupby(group_cols, as_index=False)["refund_amount"]
            .sum()
            .rename(columns={"refund_amount": "returns_amount"})
        )
        gold = gold.merge(returns_agg, on=group_cols, how="left")
        gold["returns_amount"] = gold["returns_amount"].fillna(0.0)
    else:
        gold["returns_amount"] = 0.0

    gold["discount_ratio"] = _safe_div(gold["discount_amount"], gold["gross_sales"])
    gold["net_sales_after_returns"] = (gold["net_sales"] - gold["returns_amount"]).clip(lower=0.0)

    # DQ checks
    if gold[["sales_date", "store_id", "sku_id"]].isna().any(axis=1).any():
        bad = int(gold[["sales_date", "store_id", "sku_id"]].isna().any(axis=1).sum())
        raise ValueError(f"DQ failed: found {bad} rows with null key columns.")

    if gold.duplicated(subset=group_cols).any():
        bad = int(gold.duplicated(subset=group_cols).sum())
        raise ValueError(f"DQ failed: found {bad} duplicate key rows.")

    for col in ["units", "gross_sales", "net_sales", "discount_amount", "returns_amount"]:
        bad = int((pd.to_numeric(gold[col], errors="coerce") < 0).sum())
        if bad > 0:
            raise ValueError(f"DQ failed: found {bad} rows where {col} < 0.")

    bad_returns = int((gold["returns_amount"] > gold["net_sales"]).sum())
    if bad_returns > 0:
        print(f"Warning: found {bad_returns} rows where returns_amount > net_sales.")

    gold = gold[
        [
            "sales_date",
            "store_id",
            "sku_id",
            "orders",
            "units",
            "gross_sales",
            "discount_amount",
            "net_sales",
            "discount_ratio",
            "returns_amount",
            "net_sales_after_returns",
        ]
    ].copy()

    gold["orders"] = pd.to_numeric(gold["orders"], errors="coerce").fillna(0).astype(int)
    for col in [
        "units",
        "gross_sales",
        "discount_amount",
        "net_sales",
        "discount_ratio",
        "returns_amount",
        "net_sales_after_returns",
    ]:
        gold[col] = pd.to_numeric(gold[col], errors="coerce").fillna(0.0)

    gold.to_csv(out_path, index=False)
    print(f"Wrote: {out_path}")

    # Post-run summaries
    bucket = np.where(gold["store_id"] == "S000", "S000", "PHYSICAL")
    bucket_df = (
        pd.DataFrame({"bucket": bucket, "store_id": gold["store_id"]})
        .groupby("bucket", as_index=False)
        .agg(rows=("store_id", "size"), distinct_stores=("store_id", "nunique"))
    )
    print("\nStore counts for S000 vs physical:")
    print(bucket_df.to_string(index=False))

    print("\nTop 10 rows by net_sales:")
    print(
        gold.sort_values("net_sales", ascending=False)
        .head(10)[["sales_date", "store_id", "sku_id", "net_sales", "orders", "units"]]
        .to_string(index=False)
    )

    print("\nTop 10 rows by returns_amount:")
    print(
        gold.sort_values("returns_amount", ascending=False)
        .head(10)[["sales_date", "store_id", "sku_id", "returns_amount", "net_sales"]]
        .to_string(index=False)
    )


if __name__ == "__main__":
    main()
