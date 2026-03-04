#!/usr/bin/env python3
"""
Build GOLD employee performance scorecard: 1 row per salesperson_id.

Input:
  ./silver_csv/salespeople.csv
  ./silver_csv/transactions.csv
  ./silver_csv/transaction_lines.csv
  ./silver_csv/returns.csv (optional)

Output:
  ./gold_csv/gold_employee_360.csv
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

    sp_path = input_dir / "salespeople.csv"
    tx_path = input_dir / "transactions.csv"
    lines_path = input_dir / "transaction_lines.csv"
    returns_path = input_dir / "returns.csv"
    out_path = output_dir / "gold_employee_360.csv"

    for p in [sp_path, tx_path, lines_path]:
        if not p.exists():
            raise FileNotFoundError(f"Required input file not found: {p}")

    salespeople = pd.read_csv(sp_path)
    tx = pd.read_csv(tx_path)
    lines = pd.read_csv(lines_path)
    returns_df = pd.read_csv(returns_path) if returns_path.exists() else None

    req_sp = ["salesperson_id", "name", "role", "store_id"]
    req_tx = ["transaction_id", "transaction_ts", "store_id", "channel_type", "salesperson_id"]
    req_lines = ["transaction_id", "quantity", "unit_price", "line_total", "sku_id"]
    miss_sp = [c for c in req_sp if c not in salespeople.columns]
    miss_tx = [c for c in req_tx if c not in tx.columns]
    miss_lines = [c for c in req_lines if c not in lines.columns]
    if miss_sp:
        raise ValueError(f"salespeople.csv missing required columns: {miss_sp}")
    if miss_tx:
        raise ValueError(f"transactions.csv missing required columns: {miss_tx}")
    if miss_lines:
        raise ValueError(f"transaction_lines.csv missing required columns: {miss_lines}")

    tx = tx.copy()
    tx["transaction_ts"] = pd.to_datetime(tx["transaction_ts"], errors="coerce")
    bad_ts = int(tx["transaction_ts"].isna().sum())
    if bad_ts > 0:
        print(f"Warning: dropping {bad_ts} transaction rows with invalid transaction_ts.")
        tx = tx.dropna(subset=["transaction_ts"])
    tx["sales_date"] = tx["transaction_ts"].dt.normalize().dt.date

    tx["transaction_id"] = _normalize_id(tx["transaction_id"])
    tx["store_id"] = _normalize_id(tx["store_id"])
    tx["salesperson_id"] = _normalize_id(tx["salesperson_id"])
    tx["channel_type"] = tx["channel_type"].astype("string").str.strip().fillna("").astype(str)
    tx.loc[tx["store_id"].eq(""), "store_id"] = "S000"
    tx = tx.drop_duplicates(subset=["transaction_id"], keep="last")

    lines = lines.copy()
    lines["transaction_id"] = _normalize_id(lines["transaction_id"])
    lines["sku_id"] = _normalize_id(lines["sku_id"])
    lines["quantity"] = _to_numeric(lines["quantity"], "transaction_lines.quantity")
    lines["unit_price"] = _to_numeric(lines["unit_price"], "transaction_lines.unit_price")
    lines["line_total"] = _to_numeric(lines["line_total"], "transaction_lines.line_total")

    line_level = lines.merge(
        tx[["salesperson_id", "transaction_id", "sales_date", "store_id", "channel_type"]],
        on="transaction_id",
        how="inner",
        validate="many_to_one",
    )
    dropped_lines = len(lines) - len(line_level)
    if dropped_lines > 0:
        print(
            f"Warning: dropped {dropped_lines} transaction_lines rows without matching transaction_id in transactions.csv."
        )
    blank_emp = int(line_level["salesperson_id"].astype(str).str.strip().eq("").sum())
    if blank_emp > 0:
        print(f"Warning: dropping {blank_emp} line rows with empty salesperson_id.")
        line_level = line_level.loc[~line_level["salesperson_id"].astype(str).str.strip().eq("")].copy()

    line_level["gross_line"] = line_level["quantity"] * line_level["unit_price"]

    if "discount" in line_level.columns and line_level["discount"].notna().any():
        disc = pd.to_numeric(line_level["discount"], errors="coerce").fillna(0.0)
        # Interpret discount as percent. Support mixed representations:
        # - 0..1   => already fraction
        # - 0..100 => percent points (convert per-row)
        disc = np.where(disc > 1.5, disc / 100.0, disc)
        disc = pd.Series(disc, index=line_level.index).clip(lower=0.0)
        line_level["discount_amount_line"] = line_level["gross_line"] * disc
    else:
        line_level["discount_amount_line"] = (
            line_level["gross_line"] - line_level["line_total"]
        ).clip(lower=0.0)

    gold = (
        line_level.groupby("salesperson_id", as_index=False)
        .agg(
            first_tx_date=("sales_date", "min"),
            last_tx_date=("sales_date", "max"),
            active_days=("sales_date", "nunique"),
            orders=("transaction_id", "nunique"),
            units=("quantity", "sum"),
            gross_sales=("gross_line", "sum"),
            discount_amount=("discount_amount_line", "sum"),
            net_sales=("line_total", "sum"),
        )
        .reset_index(drop=True)
    )

    if returns_df is not None and not returns_df.empty:
        if not {"transaction_id", "refund_amount"}.issubset(returns_df.columns):
            raise ValueError("returns.csv must contain transaction_id and refund_amount.")
        ret = returns_df.copy()
        ret["transaction_id"] = _normalize_id(ret["transaction_id"])
        ret["refund_amount"] = _to_numeric(ret["refund_amount"], "returns.refund_amount")

        known_tx = set(tx["transaction_id"].astype(str).tolist())
        keep_mask = ret["transaction_id"].astype(str).isin(known_tx)
        unmatched = int((~keep_mask).sum())
        if unmatched > 0:
            print(f"Warning: {unmatched} returns rows do not match known transaction_id values; excluded.")
        ret = ret.loc[keep_mask].copy()

        ret = ret.merge(
            tx[["transaction_id", "salesperson_id"]],
            on="transaction_id",
            how="inner",
            validate="many_to_one",
        )
        returns_agg = (
            ret.groupby("salesperson_id", as_index=False)["refund_amount"]
            .sum()
            .rename(columns={"refund_amount": "returns_amount"})
        )
        gold = gold.merge(returns_agg, on="salesperson_id", how="left")
        gold["returns_amount"] = gold["returns_amount"].fillna(0.0)
    else:
        gold["returns_amount"] = 0.0

    gold["avg_order_value"] = _safe_div(gold["net_sales"], gold["orders"])
    gold["discount_ratio"] = _safe_div(gold["discount_amount"], gold["gross_sales"])
    gold["return_rate_amount"] = _safe_div(gold["returns_amount"], gold["net_sales"])
    gold["net_sales_after_returns"] = (gold["net_sales"] - gold["returns_amount"]).clip(lower=0.0)

    salespeople = salespeople[req_sp].copy()
    salespeople["salesperson_id"] = _normalize_id(salespeople["salesperson_id"])
    salespeople["home_store_id"] = _normalize_id(salespeople["store_id"])
    salespeople = salespeople.drop(columns=["store_id"])
    salespeople = salespeople.drop_duplicates(subset=["salesperson_id"], keep="last")

    gold = gold.merge(salespeople, on="salesperson_id", how="left")

    missing_dim = int(gold["name"].isna().sum())
    if missing_dim > 0:
        print(
            f"Warning: {missing_dim} salesperson_id values from transactions are not found in salespeople.csv."
        )

    if gold["salesperson_id"].duplicated().any():
        bad = int(gold["salesperson_id"].duplicated().sum())
        raise ValueError(f"DQ failed: found {bad} duplicate salesperson_id rows.")

    for col in [
        "orders",
        "active_days",
        "units",
        "gross_sales",
        "discount_amount",
        "net_sales",
        "avg_order_value",
        "discount_ratio",
        "returns_amount",
        "return_rate_amount",
        "net_sales_after_returns",
    ]:
        gold[col] = pd.to_numeric(gold[col], errors="coerce").fillna(0.0)

    gold["orders"] = gold["orders"].astype(int)
    gold["active_days"] = gold["active_days"].astype(int)

    for col in [
        "units",
        "gross_sales",
        "discount_amount",
        "net_sales",
        "returns_amount",
        "net_sales_after_returns",
    ]:
        bad = int((gold[col] < 0).sum())
        if bad > 0:
            raise ValueError(f"DQ failed: found {bad} rows where {col} < 0.")

    bad_returns = int((gold["returns_amount"] > gold["net_sales"]).sum())
    if bad_returns > 0:
        print(f"Warning: found {bad_returns} rows where returns_amount > net_sales.")

    gold = gold[
        [
            "salesperson_id",
            "name",
            "role",
            "home_store_id",
            "first_tx_date",
            "last_tx_date",
            "active_days",
            "orders",
            "units",
            "gross_sales",
            "discount_amount",
            "net_sales",
            "avg_order_value",
            "discount_ratio",
            "returns_amount",
            "return_rate_amount",
            "net_sales_after_returns",
        ]
    ].copy()

    gold.to_csv(out_path, index=False)
    print(f"Wrote: {out_path}")

    print("\nTop 10 by net_sales:")
    print(
        gold.sort_values("net_sales", ascending=False)
        .head(10)[["salesperson_id", "name", "home_store_id", "net_sales", "orders", "discount_ratio", "return_rate_amount"]]
        .to_string(index=False)
    )

    dr = gold[gold["orders"] >= 20].sort_values("discount_ratio", ascending=False)
    print("\nTop 10 by discount_ratio (orders >= 20):")
    print(
        dr.head(10)[["salesperson_id", "name", "home_store_id", "discount_ratio", "orders", "net_sales"]]
        .to_string(index=False)
    )

    rr = gold[gold["orders"] >= 20].sort_values("return_rate_amount", ascending=False)
    print("\nTop 10 by return_rate_amount (orders >= 20):")
    print(
        rr.head(10)[["salesperson_id", "name", "home_store_id", "return_rate_amount", "orders", "net_sales"]]
        .to_string(index=False)
    )


if __name__ == "__main__":
    main()
