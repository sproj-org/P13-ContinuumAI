#!/usr/bin/env python3
"""
Build GOLD product 360 table from SILVER CSV files.

Usage:
    python build_gold_product_360.py

Input directory:
    ./silver_csv

Output:
    ./gold_csv/gold_product_360.csv
"""

from __future__ import annotations

from pathlib import Path
from typing import Iterable

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


def _find_first(columns: Iterable[str], candidates: list[str]) -> str | None:
    colset = set(columns)
    for c in candidates:
        if c in colset:
            return c
    return None


def _parse_date_col(df: pd.DataFrame, col: str, file_name: str) -> pd.Series:
    parsed = pd.to_datetime(df[col], errors="coerce")
    bad = int(parsed.isna().sum() - df[col].isna().sum())
    if bad > 0:
        print(f"Warning: {bad} invalid values found in {file_name}.{col}; set to null.")
    return parsed


def _discount_pct_series(raw: pd.Series, col_name: str) -> pd.Series:
    pct = pd.to_numeric(raw, errors="coerce")
    coerced = int(pct.isna().sum() - raw.isna().sum())
    if coerced > 0:
        print(f"Warning: coerced {coerced} non-numeric values in {col_name} to 0.")
    pct = pct.fillna(0.0)
    # NOTE: Synthetic data uses discount as percent (0-1); see discount_readme.md
    if ((pct > 1) & (pct <= 100)).any():
        pct = pct / 100.0
    return pct.clip(lower=0.0)


def _looks_like_percent(raw: pd.Series) -> bool:
    s = pd.to_numeric(raw, errors="coerce").dropna()
    if s.empty:
        return False
    return bool((s.max() <= 1.5) or (((s > 1) & (s <= 100)).any()))


def build_line_level_from_normalized(input_dir: Path) -> tuple[pd.DataFrame, pd.DataFrame]:
    tx_path = input_dir / "transactions.csv"
    lines_path = input_dir / "transaction_lines.csv"
    if not tx_path.exists() or not lines_path.exists():
        raise FileNotFoundError("transactions.csv and transaction_lines.csv are required for normalized path.")

    tx = pd.read_csv(tx_path)
    lines = pd.read_csv(lines_path)

    required_tx = ["transaction_id", "transaction_ts", "store_id", "channel_type"]
    missing_tx = [c for c in required_tx if c not in tx.columns]
    if missing_tx:
        raise ValueError(f"transactions.csv missing required columns: {missing_tx}")

    required_lines = ["transaction_id", "sku_id", "quantity", "unit_price", "line_total"]
    missing_lines = [c for c in required_lines if c not in lines.columns]
    if missing_lines:
        raise ValueError(f"transaction_lines.csv missing required columns: {missing_lines}")

    tx = tx[required_tx].copy()
    tx["transaction_ts"] = _parse_date_col(tx, "transaction_ts", "transactions.csv")
    bad_ts = int(tx["transaction_ts"].isna().sum())
    if bad_ts > 0:
        print(f"Warning: dropping {bad_ts} rows with invalid transactions.transaction_ts.")
        tx = tx.dropna(subset=["transaction_ts"])
    tx["sales_date"] = tx["transaction_ts"].dt.date
    tx["tx_month"] = tx["transaction_ts"].dt.to_period("M").astype(str)

    if tx["transaction_id"].duplicated().any():
        dupes = int(tx["transaction_id"].duplicated().sum())
        print(f"Warning: found {dupes} duplicate transaction_id rows in transactions.csv; keeping last.")
        tx = tx.drop_duplicates(subset=["transaction_id"], keep="last")

    lines = lines.copy()
    lines["quantity"] = _to_numeric(lines["quantity"], "transaction_lines.quantity")
    lines["unit_price"] = _to_numeric(lines["unit_price"], "transaction_lines.unit_price")
    lines["line_total"] = _to_numeric(lines["line_total"], "transaction_lines.line_total")
    lines["gross_line"] = lines["quantity"] * lines["unit_price"]

    if "discount" in lines.columns and lines["discount"].notna().any():
        # NOTE: Synthetic data uses discount as percent (0-1); see discount_readme.md
        pct = _discount_pct_series(lines["discount"], "transaction_lines.discount")
        lines["discount_amount_line"] = lines["gross_line"] * pct
    else:
        lines["discount_amount_line"] = (lines["gross_line"] - lines["line_total"]).clip(lower=0.0)

    line_level = lines.merge(
        tx[["transaction_id", "sales_date", "tx_month", "store_id", "channel_type"]],
        on="transaction_id",
        how="inner",
        validate="many_to_one",
    )
    dropped = len(lines) - len(line_level)
    if dropped > 0:
        print(f"Warning: dropped {dropped} line rows without matching transaction_id.")

    tx_ref = tx[["transaction_id"]].drop_duplicates()
    return line_level, tx_ref


def build_line_level_from_sales(input_dir: Path) -> tuple[pd.DataFrame, pd.DataFrame]:
    sales_path = input_dir / "sales.csv"
    if not sales_path.exists():
        raise FileNotFoundError("sales.csv not found.")

    sales = pd.read_csv(sales_path)
    required = ["transaction_id"]
    missing = [c for c in required if c not in sales.columns]
    if missing:
        raise ValueError(f"sales.csv missing required columns: {missing}")

    sku_col = _find_first(sales.columns, ["sku_id", "sku"])
    if sku_col is None:
        raise ValueError("sales.csv must include sku_id (or sku) for product aggregation.")

    ts_col = _find_first(
        sales.columns,
        ["transaction_ts", "sales_ts", "order_ts", "transaction_datetime", "sales_date", "order_date", "date"],
    )
    if ts_col is None:
        raise ValueError("sales.csv must contain a timestamp/date column (e.g., transaction_ts or sales_date).")

    quantity_col = _find_first(sales.columns, ["quantity", "units", "qty"])
    unit_price_col = _find_first(sales.columns, ["unit_price", "price", "list_price"])
    line_total_col = _find_first(sales.columns, ["line_total", "net_line_amount", "net_amount", "line_net_amount"])
    gross_col = _find_first(sales.columns, ["gross_line_amount", "gross_amount", "gross_line", "line_gross_amount"])
    discount_pct_col = _find_first(sales.columns, ["discount_pct", "discount_percent", "discount_percentage"])
    discount_col = _find_first(sales.columns, ["discount", "discount_amount"])
    store_col = _find_first(sales.columns, ["store_id", "store", "store_code"])
    channel_col = _find_first(sales.columns, ["channel_type", "channel", "sales_channel"])

    sales = sales.copy()
    sales["transaction_ts"] = _parse_date_col(sales, ts_col, "sales.csv")
    bad_ts = int(sales["transaction_ts"].isna().sum())
    if bad_ts > 0:
        print(f"Warning: dropping {bad_ts} rows with invalid sales timestamp.")
        sales = sales.dropna(subset=["transaction_ts"])
    sales["sales_date"] = sales["transaction_ts"].dt.date
    sales["tx_month"] = sales["transaction_ts"].dt.to_period("M").astype(str)

    sales["quantity"] = _to_numeric(sales[quantity_col], f"sales.{quantity_col}") if quantity_col else 0.0
    sales["unit_price"] = _to_numeric(sales[unit_price_col], f"sales.{unit_price_col}") if unit_price_col else 0.0

    if line_total_col is None:
        sales["line_total"] = sales["quantity"] * sales["unit_price"]
    else:
        sales["line_total"] = _to_numeric(sales[line_total_col], f"sales.{line_total_col}")

    if gross_col is not None:
        sales["gross_line"] = _to_numeric(sales[gross_col], f"sales.{gross_col}")
    else:
        sales["gross_line"] = sales["quantity"] * sales["unit_price"]

    # NOTE: Synthetic data uses discount as percent (0-1); see discount_readme.md
    if discount_pct_col is not None:
        pct = _discount_pct_series(sales[discount_pct_col], f"sales.{discount_pct_col}")
        sales["discount_amount_line"] = sales["gross_line"] * pct
    elif discount_col is not None:
        discount_num = pd.to_numeric(sales[discount_col], errors="coerce")
        if _looks_like_percent(discount_num):
            pct = _discount_pct_series(sales[discount_col], f"sales.{discount_col}")
            sales["discount_amount_line"] = sales["gross_line"] * pct
        elif discount_num.notna().any():
            sales["discount_amount_line"] = discount_num.fillna(0.0).clip(lower=0.0)
        else:
            sales["discount_amount_line"] = (sales["gross_line"] - sales["line_total"]).clip(lower=0.0)
    else:
        sales["discount_amount_line"] = (sales["gross_line"] - sales["line_total"]).clip(lower=0.0)

    sales["sku_id"] = sales[sku_col]
    sales["store_id"] = sales[store_col] if store_col is not None else np.nan
    sales["channel_type"] = sales[channel_col] if channel_col is not None else np.nan

    line_level = sales[
        [
            "transaction_id",
            "sku_id",
            "sales_date",
            "tx_month",
            "store_id",
            "channel_type",
            "quantity",
            "unit_price",
            "gross_line",
            "discount_amount_line",
            "line_total",
        ]
    ].copy()
    tx_ref = sales[["transaction_id"]].drop_duplicates()
    return line_level, tx_ref


def aggregate_product_360(line_level: pd.DataFrame, returns_df: pd.DataFrame | None, tx_ref: pd.DataFrame) -> pd.DataFrame:
    work = line_level.copy()
    channel_norm = work["channel_type"].where(work["channel_type"].notna(), "").astype(str).str.strip().str.lower()
    work["online_units"] = np.where(channel_norm == "online", work["quantity"], 0.0)

    gold = (
        work.groupby("sku_id", as_index=False)
        .agg(
            first_tx_date=("sales_date", "min"),
            last_tx_date=("sales_date", "max"),
            active_months=("tx_month", "nunique"),
            orders=("transaction_id", "nunique"),
            units_sold=("quantity", "sum"),
            gross_sales=("gross_line", "sum"),
            discount_amount=("discount_amount_line", "sum"),
            net_sales=("line_total", "sum"),
            store_coverage=("store_id", "nunique"),
            online_units=("online_units", "sum"),
        )
        .reset_index(drop=True)
    )

    if returns_df is not None and not returns_df.empty:
        required_returns = ["transaction_id", "sku_id", "refund_amount"]
        missing = [c for c in required_returns if c not in returns_df.columns]
        if missing:
            raise ValueError(f"returns.csv missing required columns: {missing}")
        ret = returns_df.copy()
        ret["refund_amount"] = _to_numeric(ret["refund_amount"], "returns.refund_amount")

        # Validate returns against known transactions (transaction_id is a string like "T0011229").
        tx_ids = set(tx_ref["transaction_id"].astype(str).tolist())
        keep_mask = ret["transaction_id"].astype(str).isin(tx_ids)

        unmatched = int((~keep_mask).sum())
        if unmatched > 0:
            print(f"Warning: {unmatched} returns rows do not match known transaction_id values; excluded.")
        ret = ret.loc[keep_mask].copy()

        # sku_id is required to attribute returns to products.
        ret = ret.dropna(subset=["sku_id"])

        returns_agg = (
            ret.groupby("sku_id", as_index=False)["refund_amount"]
            .sum()
            .rename(columns={"refund_amount": "returns_amount"})
        )
        gold = gold.merge(returns_agg, on="sku_id", how="left")
        gold["returns_amount"] = gold["returns_amount"].fillna(0.0)
    else:
        gold["returns_amount"] = 0.0

    gold["avg_selling_price"] = _safe_div(gold["net_sales"], gold["units_sold"])
    gold["discount_ratio"] = _safe_div(gold["discount_amount"], gold["gross_sales"])
    gold["return_rate_amount"] = _safe_div(gold["returns_amount"], gold["net_sales"])
    gold["channel_mix_online_pct"] = _safe_div(gold["online_units"], gold["units_sold"])
    gold = gold.drop(columns=["online_units"])

    return gold


def attach_product_mapping(gold: pd.DataFrame, input_dir: Path) -> pd.DataFrame:
    sku_path = input_dir / "product_variants_skus.csv"
    prod_path = input_dir / "products.csv"
    if not sku_path.exists():
        return gold

    sku = pd.read_csv(sku_path)
    if "sku_id" not in sku.columns or "product_id" not in sku.columns:
        print("Warning: product_variants_skus.csv missing sku_id/product_id; skipping product mapping.")
        return gold

    map_df = sku[["sku_id", "product_id"]].copy()
    if map_df["sku_id"].duplicated().any():
        dupes = int(map_df["sku_id"].duplicated().sum())
        print(f"Warning: found {dupes} duplicate sku_id rows in product_variants_skus.csv; keeping last.")
        map_df = map_df.drop_duplicates(subset=["sku_id"], keep="last")

    if prod_path.exists():
        products = pd.read_csv(prod_path)
        keep = ["product_id"]
        if "category" in products.columns:
            keep.append("category")
        if "brand" in products.columns:
            keep.append("brand")
        products = products[keep].drop_duplicates(subset=["product_id"], keep="last")
        map_df = map_df.merge(products, on="product_id", how="left")

    return gold.merge(map_df, on="sku_id", how="left")


def run_dq(gold: pd.DataFrame) -> None:
    if gold["sku_id"].isna().any():
        bad = int(gold["sku_id"].isna().sum())
        raise ValueError(f"DQ failed: found {bad} rows with null sku_id.")

    if gold["sku_id"].duplicated().any():
        bad = int(gold["sku_id"].duplicated().sum())
        raise ValueError(f"DQ failed: found {bad} duplicate sku_id rows.")

    for col in ["net_sales", "units_sold", "discount_amount", "returns_amount"]:
        bad = int((pd.to_numeric(gold[col], errors="coerce") < 0).sum())
        if bad > 0:
            raise ValueError(f"DQ failed: found {bad} rows where {col} < 0.")

    bad_discount_ratio = int((gold["discount_ratio"] > 1.5).sum())
    if bad_discount_ratio > 0:
        print(f"Warning: found {bad_discount_ratio} rows where discount_ratio > 1.5.")

    bad_returns = int((gold["returns_amount"] > gold["net_sales"]).sum())
    if bad_returns > 0:
        print(f"Warning: found {bad_returns} rows where returns_amount > net_sales.")


def reorder_columns(gold: pd.DataFrame) -> pd.DataFrame:
    cols = ["sku_id"]
    if "product_id" in gold.columns:
        cols.append("product_id")
    if "category" in gold.columns:
        cols.append("category")
    if "brand" in gold.columns:
        cols.append("brand")

    cols.extend(
        [
            "first_tx_date",
            "last_tx_date",
            "active_months",
            "orders",
            "units_sold",
            "gross_sales",
            "discount_amount",
            "net_sales",
            "avg_selling_price",
            "discount_ratio",
            "returns_amount",
            "return_rate_amount",
            "store_coverage",
            "channel_mix_online_pct",
        ]
    )
    return gold[cols]


def print_summary(gold: pd.DataFrame) -> None:
    print("\nBuild summary")
    print("-------------")
    print(f"Products (sku_id): {len(gold):,}")
    print("\nTop 10 SKUs by net_sales:")
    top10 = gold.sort_values("net_sales", ascending=False)[["sku_id", "net_sales", "units_sold", "orders"]].head(10)
    print(top10.to_string(index=False))


def main() -> None:
    input_dir = Path("./silver_csv")
    output_dir = Path("./gold_csv")
    output_dir.mkdir(parents=True, exist_ok=True)

    sales_path = input_dir / "sales.csv"
    if sales_path.exists():
        print("Detected sales.csv; using denormalized sales input path.")
        line_level, tx_ref = build_line_level_from_sales(input_dir)
    else:
        line_level, tx_ref = build_line_level_from_normalized(input_dir)

    returns_path = input_dir / "returns.csv"
    returns_df = pd.read_csv(returns_path) if returns_path.exists() else None

    gold = aggregate_product_360(line_level, returns_df, tx_ref)
    gold = attach_product_mapping(gold, input_dir)

    gold["orders"] = pd.to_numeric(gold["orders"], errors="coerce").fillna(0).astype(int)
    gold["active_months"] = pd.to_numeric(gold["active_months"], errors="coerce").fillna(0).astype(int)
    gold["store_coverage"] = pd.to_numeric(gold["store_coverage"], errors="coerce").fillna(0).astype(int)
    for col in [
        "units_sold",
        "gross_sales",
        "discount_amount",
        "net_sales",
        "avg_selling_price",
        "discount_ratio",
        "returns_amount",
        "return_rate_amount",
        "channel_mix_online_pct",
    ]:
        gold[col] = pd.to_numeric(gold[col], errors="coerce").fillna(0.0)

    gold = reorder_columns(gold)
    run_dq(gold)

    out_path = output_dir / "gold_product_360.csv"
    gold.to_csv(out_path, index=False)
    print(f"\nWrote: {out_path}")
    print_summary(gold)


if __name__ == "__main__":
    main()
