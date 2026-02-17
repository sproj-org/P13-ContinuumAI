#!/usr/bin/env python3
"""
Build GOLD customer 360 table from SILVER CSV files.

Usage:
    python build_gold_customer_360.py
    python build_gold_customer_360.py --input-dir ./silver_csv --output-dir ./gold_csv

Required files in input dir:
    - customers.csv
    - Either:
        A) transactions.csv + transaction_lines.csv
        B) sales.csv (denormalized line-level fact)

Optional files:
    - returns.csv
    - product_variants_skus.csv + products.csv (for optional top_category)

Output:
    - ./gold_csv/gold_customer_360.csv
"""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Iterable

import numpy as np
import pandas as pd



RETURN_RATE_THRESHOLD = 0.10
DEFAULT_RECONCILE_ABS_TOL = 0.01
DEFAULT_RECONCILE_REL_TOL = 0.01


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


def _score_1_to_5(series: pd.Series, higher_is_better: bool) -> pd.Series:
    s = pd.to_numeric(series, errors="coerce")
    pct = s.rank(method="average", pct=True)
    if higher_is_better:
        score = np.ceil(pct * 5)
    else:
        score = np.ceil((1 - pct) * 5)
    score = pd.Series(score, index=series.index).clip(lower=1, upper=5)
    return score.fillna(1).astype(int)


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


def load_customers(input_dir: Path) -> pd.DataFrame:
    p = input_dir / "customers.csv"
    if not p.exists():
        raise FileNotFoundError(f"Required file missing: {p}")

    customers = pd.read_csv(p)
    required = ["customer_id", "segment", "city", "region", "first_purchase_date"]
    missing = [c for c in required if c not in customers.columns]
    if missing:
        raise ValueError(f"customers.csv missing required columns: {missing}")

    customers = customers[required].copy()
    customers["first_purchase_date"] = _parse_date_col(
        customers, "first_purchase_date", "customers.csv"
    ).dt.date

    if customers["customer_id"].isna().any():
        bad = int(customers["customer_id"].isna().sum())
        raise ValueError(f"DQ failed: customers.csv contains {bad} null customer_id values.")

    if customers["customer_id"].duplicated().any():
        dupes = int(customers["customer_id"].duplicated().sum())
        print(
            f"Warning: found {dupes} duplicate customer_id rows in customers.csv; keeping last."
        )
        customers = customers.drop_duplicates(subset=["customer_id"], keep="last")

    return customers


def build_line_and_tx_from_normalized(
    input_dir: Path,
    reconcile_abs_tol: float = DEFAULT_RECONCILE_ABS_TOL,
    reconcile_rel_tol: float = DEFAULT_RECONCILE_REL_TOL,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    tx_path = input_dir / "transactions.csv"
    line_path = input_dir / "transaction_lines.csv"
    if not tx_path.exists() or not line_path.exists():
        raise FileNotFoundError(
            "Normalized path requires transactions.csv and transaction_lines.csv."
        )

    tx = pd.read_csv(tx_path)
    lines = pd.read_csv(line_path)

    required_tx = [
        "transaction_id",
        "transaction_ts",
        "customer_id",
        "store_id",
        "channel_type",
        "total_amount",
    ]
    missing_tx = [c for c in required_tx if c not in tx.columns]
    if missing_tx:
        raise ValueError(f"transactions.csv missing required columns: {missing_tx}")

    required_lines = [
        "line_id",
        "transaction_id",
        "sku_id",
        "quantity",
        "unit_price",
        "line_total",
    ]
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
        print(
            f"Warning: found {dupes} duplicate transaction_id rows in transactions.csv; keeping last."
        )
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
        tx[["transaction_id", "customer_id", "transaction_ts", "sales_date", "tx_month"]],
        on="transaction_id",
        how="inner",
        validate="many_to_one",
    )
    dropped = len(lines) - len(line_level)
    if dropped > 0:
        print(f"Warning: dropped {dropped} line rows without matching transaction_id.")

    # Reconcile per-transaction totals (sanity check): sum(line_total) vs transactions.total_amount
    # This does not fail the build; it warns when mismatches exceed tolerance.
    tx_lines_sum = (
        line_level.groupby("transaction_id", as_index=False)["line_total"]
        .sum()
        .rename(columns={"line_total": "lines_total"})
    )
    tx_totals = tx[["transaction_id", "total_amount"]].copy()
    tx_totals["total_amount"] = _to_numeric(tx_totals["total_amount"], "transactions.total_amount")
    tx_check = tx_totals.merge(tx_lines_sum, on="transaction_id", how="left", validate="one_to_one")
    tx_check["lines_total"] = tx_check["lines_total"].fillna(0.0)
    tx_check["abs_diff"] = (tx_check["lines_total"] - tx_check["total_amount"]).abs()
    tx_check["rel_diff"] = np.where(
        tx_check["total_amount"] > 0,
        tx_check["abs_diff"] / tx_check["total_amount"],
        0.0,
    )
    bad_mask = (tx_check["abs_diff"] > reconcile_abs_tol) & (tx_check["rel_diff"] > reconcile_rel_tol)
    bad_n = int(bad_mask.sum())
    if bad_n > 0:
        print(
            f"Warning: {bad_n} transactions have totals mismatch beyond tolerance "
            f"(abs>{reconcile_abs_tol}, rel>{reconcile_rel_tol})."
        )
        sample = tx_check.loc[
            bad_mask,
            ["transaction_id", "total_amount", "lines_total", "abs_diff", "rel_diff"],
        ].head(5)
        print("Sample mismatches:\n" + sample.to_string(index=False))

    tx_min = tx[["transaction_id", "customer_id", "transaction_ts", "sales_date", "tx_month"]].copy()
    return line_level, tx_min


def build_line_and_tx_from_sales(input_dir: Path) -> tuple[pd.DataFrame, pd.DataFrame]:
    sales_path = input_dir / "sales.csv"
    if not sales_path.exists():
        raise FileNotFoundError("sales.csv not found.")

    sales = pd.read_csv(sales_path)
    required = ["transaction_id", "customer_id"]
    missing = [c for c in required if c not in sales.columns]
    if missing:
        raise ValueError(f"sales.csv missing required columns: {missing}")

    ts_col = _find_first(
        sales.columns,
        [
            "transaction_ts",
            "sales_ts",
            "order_ts",
            "transaction_datetime",
            "sales_date",
            "order_date",
            "date",
        ],
    )
    if ts_col is None:
        raise ValueError(
            "sales.csv must contain a timestamp/date column (e.g., transaction_ts or sales_date)."
        )

    sales = sales.copy()
    sales["transaction_ts"] = _parse_date_col(sales, ts_col, "sales.csv")
    bad_ts = int(sales["transaction_ts"].isna().sum())
    if bad_ts > 0:
        print(f"Warning: dropping {bad_ts} rows with invalid sales timestamp.")
        sales = sales.dropna(subset=["transaction_ts"])
    sales["sales_date"] = sales["transaction_ts"].dt.date
    sales["tx_month"] = sales["transaction_ts"].dt.to_period("M").astype(str)

    quantity_col = _find_first(sales.columns, ["quantity", "units", "qty"])
    unit_price_col = _find_first(sales.columns, ["unit_price", "price", "list_price"])
    line_total_col = _find_first(
        sales.columns, ["line_total", "net_line_amount", "net_amount", "line_net_amount"]
    )
    discount_col = _find_first(sales.columns, ["discount", "discount_amount"])
    sku_col = _find_first(sales.columns, ["sku_id", "sku"])
    gross_col = _find_first(sales.columns, ["gross_line_amount", "gross_amount", "gross_line", "line_gross_amount"]) 
    discount_pct_col = _find_first(sales.columns, ["discount_pct", "discount_percent", "discount_percentage"]) 

    if quantity_col is None:
        sales["quantity"] = 0.0
    else:
        sales["quantity"] = _to_numeric(sales[quantity_col], f"sales.{quantity_col}")

    if unit_price_col is None:
        sales["unit_price"] = 0.0
    else:
        sales["unit_price"] = _to_numeric(sales[unit_price_col], f"sales.{unit_price_col}")

    if line_total_col is None:
        # Fallback if no explicit net amount exists.
        sales["line_total"] = sales["quantity"] * sales["unit_price"]
    else:
        sales["line_total"] = _to_numeric(sales[line_total_col], f"sales.{line_total_col}")

    if gross_col is not None:
        sales["gross_line"] = _to_numeric(sales[gross_col], f"sales.{gross_col}")
    else:
        sales["gross_line"] = sales["quantity"] * sales["unit_price"]

    # NOTE: Synthetic data uses discount as percent (0-1); see discount_readme.md
    # Precedence:
    # 1) explicit discount pct columns
    # 2) discount/discount_amount column (auto-detect percent-like vs amount)
    # 3) computed gross - net
    if discount_pct_col is not None:
        pct = _discount_pct_series(sales[discount_pct_col], f"sales.{discount_pct_col}")
        sales["discount_amount_line"] = (sales["gross_line"] * pct).fillna(0.0)
    elif discount_col is not None:
        discount_num = pd.to_numeric(sales[discount_col], errors="coerce")
        if _looks_like_percent(discount_num):
            pct = _discount_pct_series(sales[discount_col], f"sales.{discount_col}")
            sales["discount_amount_line"] = (sales["gross_line"] * pct).fillna(0.0)
        elif discount_num.notna().any():
            sales["discount_amount_line"] = discount_num.fillna(0.0).clip(lower=0.0)
        else:
            sales["discount_amount_line"] = (sales["gross_line"] - sales["line_total"]).clip(lower=0.0)
    else:
        sales["discount_amount_line"] = (sales["gross_line"] - sales["line_total"]).clip(lower=0.0)

    if sku_col is None:
        sales["sku_id"] = np.nan
    else:
        sales["sku_id"] = sales[sku_col]

    line_level = sales[
        [
            "transaction_id",
            "customer_id",
            "transaction_ts",
            "sales_date",
            "tx_month",
            "sku_id",
            "quantity",
            "unit_price",
            "gross_line",
            "discount_amount_line",
            "line_total",
        ]
    ].copy()
    tx_min = line_level[
        ["transaction_id", "customer_id", "transaction_ts", "sales_date", "tx_month"]
    ].drop_duplicates(subset=["transaction_id"], keep="last")
    return line_level, tx_min


def try_build_top_category(line_level: pd.DataFrame, input_dir: Path) -> pd.DataFrame | None:
    sku_path = input_dir / "product_variants_skus.csv"
    prod_path = input_dir / "products.csv"
    if not sku_path.exists() or not prod_path.exists():
        return None

    sku = pd.read_csv(sku_path)
    products = pd.read_csv(prod_path)

    sku_id_col = _find_first(sku.columns, ["sku_id"])
    product_id_col_sku = _find_first(sku.columns, ["product_id"])
    product_id_col_products = _find_first(products.columns, ["product_id"])
    category_col = _find_first(
        products.columns,
        ["category", "category_name", "category_id", "product_category"],
    )
    if None in [sku_id_col, product_id_col_sku, product_id_col_products, category_col]:
        print("Warning: optional top_category skipped due to missing mapping columns.")
        return None

    map_df = sku[[sku_id_col, product_id_col_sku]].merge(
        products[[product_id_col_products, category_col]],
        left_on=product_id_col_sku,
        right_on=product_id_col_products,
        how="left",
    )
    map_df = map_df.rename(columns={sku_id_col: "sku_id", category_col: "category"})

    work = line_level[["customer_id", "sku_id", "line_total"]].copy()
    work = work.merge(map_df[["sku_id", "category"]], on="sku_id", how="left")
    work = work.dropna(subset=["category"])
    if work.empty:
        return None

    by_cat = (
        work.groupby(["customer_id", "category"], as_index=False)["line_total"]
        .sum()
        .sort_values(["customer_id", "line_total"], ascending=[True, False])
    )
    top_cat = by_cat.drop_duplicates(subset=["customer_id"], keep="first").rename(
        columns={"category": "top_category"}
    )
    return top_cat[["customer_id", "top_category"]]


def aggregate_customer_360(
    customers: pd.DataFrame,
    line_level: pd.DataFrame,
    tx_min: pd.DataFrame,
    returns_df: pd.DataFrame | None,
    return_rate_threshold: float,
    top_category_df: pd.DataFrame | None,
) -> pd.DataFrame:
    line_agg = (
        line_level.groupby("customer_id", as_index=False)
        .agg(
            units=("quantity", "sum"),
            gross_sales=("gross_line", "sum"),
            discount_amount=("discount_amount_line", "sum"),
            net_sales=("line_total", "sum"),
        )
        .reset_index(drop=True)
    )

    tx_agg = (
        tx_min.groupby("customer_id", as_index=False)
        .agg(
            orders=("transaction_id", "nunique"),
            first_tx_date=("sales_date", "min"),
            last_tx_date=("sales_date", "max"),
            active_months=("tx_month", "nunique"),
        )
        .reset_index(drop=True)
    )

    if returns_df is not None and not returns_df.empty:
        needed = ["transaction_id", "refund_amount"]
        missing = [c for c in needed if c not in returns_df.columns]
        if missing:
            raise ValueError(f"returns.csv missing required columns: {missing}")
        ret = returns_df.copy()
        ret["refund_amount"] = _to_numeric(ret["refund_amount"], "returns.refund_amount")
        ret_join = ret.merge(
            tx_min[["transaction_id", "customer_id"]],
            on="transaction_id",
            how="left",
            validate="many_to_one",
        )
        unmatched = int(ret_join["customer_id"].isna().sum())
        if unmatched > 0:
            print(
                f"Warning: {unmatched} returns rows have no matching transaction_id; excluded."
            )
        returns_agg = (
            ret_join.dropna(subset=["customer_id"])
            .groupby("customer_id", as_index=False)["refund_amount"]
            .sum()
            .rename(columns={"refund_amount": "returns_amount"})
        )
    else:
        returns_agg = pd.DataFrame(columns=["customer_id", "returns_amount"])

    gold = customers.merge(tx_agg, on="customer_id", how="left")
    gold = gold.merge(line_agg, on="customer_id", how="left")
    gold = gold.merge(returns_agg, on="customer_id", how="left")

    if top_category_df is not None and not top_category_df.empty:
        gold = gold.merge(top_category_df, on="customer_id", how="left")

    fill_zero = [
        "orders",
        "active_months",
        "units",
        "gross_sales",
        "discount_amount",
        "net_sales",
        "returns_amount",
    ]
    for col in fill_zero:
        gold[col] = pd.to_numeric(gold[col], errors="coerce").fillna(0.0)

    max_tx_date = tx_min["sales_date"].max() if not tx_min.empty else None
    if max_tx_date is None or pd.isna(max_tx_date):
        gold["recency_days"] = np.nan
    else:
        last_tx = pd.to_datetime(gold["last_tx_date"], errors="coerce")
        gold["recency_days"] = (pd.to_datetime(max_tx_date) - last_tx).dt.days

    gold["avg_order_value"] = _safe_div(gold["net_sales"], gold["orders"])
    gold["avg_units_per_order"] = _safe_div(gold["units"], gold["orders"])
    gold["discount_ratio"] = _safe_div(gold["discount_amount"], gold["gross_sales"])
    gold["net_sales_after_returns"] = gold["net_sales"] - gold["returns_amount"]
    # Safety: returns should not exceed net sales; warn and floor net_sales_after_returns at 0.
    over_refund = gold["returns_amount"] > gold["net_sales"]
    if over_refund.any():
        n_over = int(over_refund.sum())
        print(f"Warning: {n_over} customers have returns_amount > net_sales; flooring net_sales_after_returns to 0 for them.")
    gold.loc[over_refund, "net_sales_after_returns"] = 0.0
    gold["return_rate_amount"] = _safe_div(gold["returns_amount"], gold["net_sales"])
    gold["return_rate_flag"] = (gold["return_rate_amount"] > return_rate_threshold).astype(int)
    gold["frequency_per_month"] = _safe_div(gold["orders"], gold["active_months"].clip(lower=1))

    has_orders = gold["orders"] > 0
    recency_score = pd.Series(1, index=gold.index, dtype=int)
    frequency_score = pd.Series(1, index=gold.index, dtype=int)
    monetary_score = pd.Series(1, index=gold.index, dtype=int)
    if has_orders.any():
        recency_score.loc[has_orders] = _score_1_to_5(
            gold.loc[has_orders, "recency_days"], higher_is_better=False
        )
        frequency_score.loc[has_orders] = _score_1_to_5(
            gold.loc[has_orders, "frequency_per_month"], higher_is_better=True
        )
        monetary_score.loc[has_orders] = _score_1_to_5(
            gold.loc[has_orders, "net_sales_after_returns"], higher_is_better=True
        )
    gold["rfm_score"] = recency_score * 100 + frequency_score * 10 + monetary_score

    high = (gold["recency_days"] > 60) & (gold["frequency_per_month"] < 1)
    medium = (
        gold["recency_days"].between(30, 60, inclusive="both")
        | gold["frequency_per_month"].between(1, 2, inclusive="both")
    )
    # Churn bucket should only apply to customers with order history.
    # For customers with no orders, mark as unknown (not "high churn").
    no_history = gold["orders"] <= 0
    gold["churn_risk_bucket"] = np.select(
        [no_history, high, medium],
        ["unknown", "high", "medium"],
        default="low",
    )
    # Guard: if recency_days is missing for customers with orders, set churn risk to "medium"
    missing_recency_with_orders = (gold["orders"] > 0) & (pd.to_numeric(gold["recency_days"], errors="coerce").isna())
    if missing_recency_with_orders.any():
        nmiss = int(missing_recency_with_orders.sum())
        print(f"Warning: {nmiss} customers have orders but recency_days is null; setting churn_risk_bucket to 'medium' for them.")
        gold.loc[missing_recency_with_orders, "churn_risk_bucket"] = "medium"

    gold["orders"] = gold["orders"].astype(int)
    gold["active_months"] = gold["active_months"].astype(int)
    gold["return_rate_flag"] = gold["return_rate_flag"].astype(int)
    money_and_ratio = [
        "units",
        "gross_sales",
        "discount_amount",
        "net_sales",
        "avg_order_value",
        "avg_units_per_order",
        "discount_ratio",
        "returns_amount",
        "net_sales_after_returns",
        "return_rate_amount",
        "frequency_per_month",
    ]
    for col in money_and_ratio:
        gold[col] = pd.to_numeric(gold[col], errors="coerce").fillna(0.0)

    return gold


def run_dq(gold: pd.DataFrame) -> None:
    if gold["customer_id"].isna().any():
        bad = int(gold["customer_id"].isna().sum())
        raise ValueError(f"DQ failed: found {bad} null customer_id values.")

    if (gold["orders"] < 0).any():
        bad = int((gold["orders"] < 0).sum())
        raise ValueError(f"DQ failed: found {bad} rows where orders < 0.")

    if (gold["net_sales"] < 0).any():
        bad = int((gold["net_sales"] < 0).sum())
        raise ValueError(f"DQ failed: found {bad} rows where net_sales < 0.")

    if (gold["discount_ratio"] < 0).any():
        bad = int((gold["discount_ratio"] < 0).sum())
        raise ValueError(f"DQ failed: found {bad} rows where discount_ratio < 0.")

    bad_recency = (gold["orders"] > 0) & (
        pd.to_numeric(gold["recency_days"], errors="coerce") < 0
    )
    if bad_recency.any():
        bad = int(bad_recency.sum())
        raise ValueError(f"DQ failed: found {bad} rows where recency_days < 0 for customers with orders.")


def print_summary(gold: pd.DataFrame) -> None:
    total = len(gold)
    with_orders = int((gold["orders"] > 0).sum())
    pct_with_orders = (with_orders / total * 100.0) if total else 0.0

    print("\nBuild summary")
    print("-------------")
    print(f"Customers: {total:,}")
    print(f"Customers with orders: {with_orders:,} ({pct_with_orders:.2f}%)")

    print("\nTop 10 customers by net_sales_after_returns:")
    top10 = (
        gold.sort_values("net_sales_after_returns", ascending=False)[
            ["customer_id", "segment", "net_sales_after_returns", "orders"]
        ]
        .head(10)
        .reset_index(drop=True)
    )
    print(top10.to_string(index=False))

    print("\nChurn bucket counts:")
    print(gold["churn_risk_bucket"].value_counts(dropna=False).to_string())


def reorder_columns(gold: pd.DataFrame) -> pd.DataFrame:
    ordered = [
        "customer_id",
        "segment",
        "city",
        "region",
        "first_purchase_date",
        "first_tx_date",
        "last_tx_date",
        "recency_days",
        "active_months",
        "orders",
        "units",
        "gross_sales",
        "discount_amount",
        "net_sales",
        "avg_order_value",
        "avg_units_per_order",
        "discount_ratio",
        "returns_amount",
        "net_sales_after_returns",
        "return_rate_amount",
        "return_rate_flag",
        "frequency_per_month",
        "rfm_score",
        "churn_risk_bucket",
    ]
    if "top_category" in gold.columns:
        ordered.append("top_category")
    return gold[ordered]


def main() -> None:
    parser = argparse.ArgumentParser(description="Build gold_customer_360 from SILVER CSVs.")
    parser.add_argument(
        "--input-dir",
        default="./silver_csv",
        help="Input directory containing SILVER CSVs (default: ./silver_csv).",
    )
    parser.add_argument(
        "--output-dir",
        default="./gold_csv",
        help="Output directory for GOLD CSV (default: ./gold_csv).",
    )
    parser.add_argument(
        "--return-rate-threshold",
        type=float,
        default=RETURN_RATE_THRESHOLD,
        help=f"Threshold for return_rate_flag (default: {RETURN_RATE_THRESHOLD}).",
    )
    args = parser.parse_args()

    input_dir = Path(args.input_dir)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    customers = load_customers(input_dir)

    sales_path = input_dir / "sales.csv"
    if sales_path.exists():
        print("Detected sales.csv; using denormalized sales input path.")
        line_level, tx_min = build_line_and_tx_from_sales(input_dir)
    else:
        line_level, tx_min = build_line_and_tx_from_normalized(
            input_dir,
            reconcile_abs_tol=DEFAULT_RECONCILE_ABS_TOL,
            reconcile_rel_tol=DEFAULT_RECONCILE_REL_TOL,
        )

    returns_path = input_dir / "returns.csv"
    returns_df = pd.read_csv(returns_path) if returns_path.exists() else None

    top_category_df = try_build_top_category(line_level, input_dir)
    if top_category_df is not None:
        print("Optional feature enabled: top_category")

    gold = aggregate_customer_360(
        customers=customers,
        line_level=line_level,
        tx_min=tx_min,
        returns_df=returns_df,
        return_rate_threshold=args.return_rate_threshold,
        top_category_df=top_category_df,
    )
    gold = reorder_columns(gold)
    run_dq(gold)

    out_path = output_dir / "gold_customer_360.csv"
    gold.to_csv(out_path, index=False)
    print(f"\nWrote: {out_path}")
    print_summary(gold)


if __name__ == "__main__":
    main()
