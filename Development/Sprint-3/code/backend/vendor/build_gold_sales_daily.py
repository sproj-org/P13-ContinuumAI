#!/usr/bin/env python3
"""
Build GOLD daily sales aggregate (gold_sales_daily) from SILVER CSV files.

What this builds (business-level aggregate)
------------------------------------------
This script produces a GOLD table at the grain:
    sales_date × channel_type × store_id

It is designed to support Continuum MVP descriptive + diagnostic analytics for SilkRoute,
including the core "What happened?" views (sales trends, channel/store performance) and
inputs to later strategy-guided recommendations (discount dependency, returns impact).
(ContAI.docx defines transactions + transaction lines as the core sales entities, with
returns at SKU-level and channel/store context.)

How the aggregate is built
--------------------------
Inputs (SILVER CSVs):
  - transactions.csv
      transaction_id, transaction_ts, channel_type, store_id, total_amount, ...
  - transaction_lines.csv
      line_id, transaction_id, sku_id, quantity, unit_price, discount (optional), line_total
  - stores.csv
      store_id, city, region, store_type
  - returns.csv (optional)
      return_id, transaction_id, sku_id, refund_amount, ...

Steps:
  1) Parse transactions.transaction_ts → sales_date (date)
  2) Normalize numerics in transaction_lines (quantity, unit_price, line_total)
  3) Compute per-line gross_line = unit_price × quantity
  4) Compute per-line discount_amount_line using --discount-mode
     - auto (default): if a numeric discount column exists, treat it as line discount amount;
       otherwise compute discount as (gross_line - line_total)
     - amount: discount is absolute line discount
     - per_unit: discount is per-unit, multiplied by quantity
     - percent: discount is percent-off (0–1 or 0–100), applied to (unit_price × quantity)
  5) Join transaction_lines → transactions on transaction_id (many-to-one) to attach:
     sales_date, channel_type, store_id
  6) Aggregate to (sales_date, channel_type, store_id):
       orders          = distinct transaction_id count
       units           = sum(quantity)
       gross_sales     = sum(gross_line)
       discount_amount = sum(discount_amount_line)
       net_sales       = sum(line_total)
  7) Derive KPIs:
       avg_order_value = net_sales / orders
       discount_ratio  = discount_amount / gross_sales
  8) If returns.csv exists, aggregate returns_amount by the same grain and compute:
       net_sales_after_returns = net_sales - returns_amount
  9) Enrich with stores metadata (city, region, store_type)

Data quality + sanity checks
----------------------------
- Transaction reconciliation: compares per-transaction sum(line_total) vs transactions.total_amount
  and WARNs when mismatches exceed tolerances (see --reconcile-abs-tol, --reconcile-rel-tol).
- GOLD DQ checks: non-null keys (sales_date/channel_type/store_id), orders>0, net_sales>=0,
  discount_amount>=0; warns if discount_ratio outside [0, 1.5].

What you can compute from this table (KPIs & charts)
----------------------------------------------------
This table is the main input for executive-style views and baseline diagnostic slices:

Common KPIs:
  - Net Sales (net_sales)
  - Gross Sales (gross_sales)
  - Discount Amount (discount_amount)
  - Discount Ratio (discount_ratio)  ← discount dependency signal
  - Orders (orders)
  - Units Sold (units)
  - Average Order Value (avg_order_value)
  - Returns Amount (returns_amount) and Net Sales After Returns (net_sales_after_returns)

Typical charts:
  - Sales trend line: net_sales by sales_date (overall)
  - Channel split: net_sales by sales_date grouped by channel_type
  - Store leaderboard: top stores by net_sales or net_sales_after_returns
  - Discount dependency trend: discount_ratio over time (overall / by channel / by store)
  - Returns impact: returns_amount and net_sales_after_returns over time
  - Regional comparison: net_sales by region over time (via store enrichment)

Notes / limitations (MVP)
-------------------------
- This table is intentionally not SKU/product/customer level. For product/customer analytics,
  build additional GOLD aggregates (e.g., gold_product_360, gold_customer_360).
- Margin/profit is not computed here because COGS is not available in the SILVER sales files.
  A separate GOLD profit bridge can be added once COGS assumptions are defined.

How to run
----------
    python build_gold_sales_daily.py

By default, the script expects SILVER files in:
    ./silver_csv/

You can override locations:
    python build_gold_sales_daily.py --input-dir . --output-dir ./gold_csv

Flags:
    --discount-mode (auto|amount|per_unit|percent)
    --reconcile-abs-tol
    --reconcile-rel-tol

Optional DB load
----------------
If DATABASE_URL is set, the script will also create schema "gold" (if needed) and load
results to table "gold.gold_sales_daily" in Postgres/Supabase using SQLAlchemy
`to_sql(if_exists="replace")`.
"""

from __future__ import annotations

import argparse
import os
from pathlib import Path

import numpy as np
import pandas as pd


REQUIRED_TRANSACTIONS = [
    "transaction_id",
    "transaction_ts",
    "channel_type",
    "store_id",
    "total_amount",
]
REQUIRED_LINES = [
    "line_id",
    "transaction_id",
    "sku_id",
    "quantity",
    "unit_price",
    "discount",
    "line_total",
]
REQUIRED_STORES = ["store_id", "city", "region", "store_type"]

DEFAULT_DISCOUNT_MODE = "auto"  # auto|amount|per_unit|percent
DEFAULT_RECONCILE_ABS_TOL = 0.01
DEFAULT_RECONCILE_REL_TOL = 0.01


def _pick_columns(df: pd.DataFrame, required: list[str], file_name: str) -> pd.DataFrame:
    missing = [c for c in required if c not in df.columns]
    # "discount" is optional in logic even if listed in expected shape.
    if file_name == "transaction_lines.csv":
        missing = [c for c in missing if c != "discount"]
    if missing:
        raise ValueError(f"{file_name} is missing required columns: {missing}")
    keep = [c for c in required if c in df.columns]
    extra = [c for c in df.columns if c not in keep]
    return df[keep + extra]


def _to_numeric(series: pd.Series, column_name: str) -> pd.Series:
    raw_na = series.isna().sum()
    numeric = pd.to_numeric(series, errors="coerce")
    coerced = int(numeric.isna().sum() - raw_na)
    if coerced > 0:
        print(f"Warning: coerced {coerced} non-numeric values in {column_name} to 0.")
    return numeric.fillna(0.0)


def _compute_discount_amount_line(
    df: pd.DataFrame,
    discount_mode: str,
) -> pd.Series:
    """Return per-line discount amount.

    discount_mode:
      - auto: use numeric `discount` if present; otherwise compute gross_line - line_total
      - amount: treat `discount` as an absolute line discount amount
      - per_unit: treat `discount` as per-unit discount amount (multiplied by quantity)
      - percent: treat `discount` as a percent off unit_price (0-1 or 0-100)
    """
    gross_line = df["gross_line"]
    if "discount" not in df.columns or df["discount"].isna().all():
        if discount_mode in {"amount", "per_unit", "percent"}:
            print("Warning: discount_mode is set but transaction_lines.discount is missing/empty; falling back to computed discount.")
        return (gross_line - df["line_total"]).clip(lower=0.0).fillna(0.0)

    disc = pd.to_numeric(df["discount"], errors="coerce")
    coerced = int(disc.isna().sum() - df["discount"].isna().sum())
    if coerced > 0:
        print(f"Warning: coerced {coerced} non-numeric values in transaction_lines.discount to 0.")
    disc = disc.fillna(0.0)

    mode = discount_mode.lower().strip()
    if mode == "auto":
        # Align with bridge builder: treat discount as percent (0-1 or 0-100), then apply to gross_line.
        pct = disc.copy()
        if ((pct > 1) & (pct <= 100)).any():
            pct = pct / 100.0
        elif float(pct.max()) <= 1.5:
            pct = pct
        pct = pct.clip(lower=0.0)
        return (gross_line * pct).fillna(0.0)

    if mode == "amount":
        return disc

    if mode == "per_unit":
        return disc * df["quantity"]

    if mode == "percent":
        # Treat percent as 0-1 or 0-100.
        pct = disc.copy()
        if ((pct > 1) & (pct <= 100)).any():
            pct = pct / 100.0
        elif float(pct.max()) <= 1.5:
            pct = pct
        pct = pct.clip(lower=0.0)
        return (gross_line * pct).fillna(0.0)

    raise ValueError(f"Invalid discount_mode: {discount_mode}. Use auto|amount|per_unit|percent")


def load_inputs(input_dir: Path) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame | None]:
    transactions_path = input_dir / "transactions.csv"
    lines_path = input_dir / "transaction_lines.csv"
    stores_path = input_dir / "stores.csv"
    returns_path = input_dir / "returns.csv"

    for p in [transactions_path, lines_path, stores_path]:
        if not p.exists():
            raise FileNotFoundError(f"Required file not found: {p}")

    transactions = pd.read_csv(transactions_path)
    transaction_lines = pd.read_csv(lines_path)
    stores = pd.read_csv(stores_path)
    returns_df = pd.read_csv(returns_path) if returns_path.exists() else None

    transactions = _pick_columns(transactions, REQUIRED_TRANSACTIONS, "transactions.csv")
    transaction_lines = _pick_columns(transaction_lines, REQUIRED_LINES, "transaction_lines.csv")
    stores = _pick_columns(stores, REQUIRED_STORES, "stores.csv")

    if returns_df is not None:
        required_returns = ["return_id", "transaction_id", "sku_id", "refund_amount", "return_reason"]
        missing = [c for c in required_returns if c not in returns_df.columns]
        # Only transaction_id + refund_amount are strictly needed for aggregation.
        missing_critical = [c for c in missing if c in {"transaction_id", "refund_amount"}]
        if missing_critical:
            raise ValueError(f"returns.csv missing required columns: {missing_critical}")

    return transactions, transaction_lines, stores, returns_df


def transform(
    transactions: pd.DataFrame,
    transaction_lines: pd.DataFrame,
    stores: pd.DataFrame,
    returns_df: pd.DataFrame | None,
    discount_mode: str,
    reconcile_abs_tol: float,
    reconcile_rel_tol: float,
) -> pd.DataFrame:
    if transactions["transaction_id"].duplicated().any():
        dupes = int(transactions["transaction_id"].duplicated().sum())
        print(f"Warning: found {dupes} duplicate transaction_id rows in transactions.csv; keeping last row per transaction_id.")
        transactions = transactions.drop_duplicates(subset=["transaction_id"], keep="last")

    if stores["store_id"].duplicated().any():
        dupes = int(stores["store_id"].duplicated().sum())
        print(f"Warning: found {dupes} duplicate store_id rows in stores.csv; keeping last row per store_id.")
        stores = stores.drop_duplicates(subset=["store_id"], keep="last")

    transactions["transaction_ts"] = pd.to_datetime(transactions["transaction_ts"], errors="coerce", utc=False)
    bad_ts = int(transactions["transaction_ts"].isna().sum())
    if bad_ts > 0:
        raise ValueError(f"Found {bad_ts} rows with invalid transaction_ts in transactions.csv.")
    transactions["sales_date"] = transactions["transaction_ts"].dt.date
    # Keep online transactions in GOLD grain: online rows may not have a physical store_id.
    transactions["store_id"] = transactions["store_id"].fillna("ONLINE")

    transaction_lines["quantity"] = _to_numeric(transaction_lines["quantity"], "transaction_lines.quantity")
    transaction_lines["unit_price"] = _to_numeric(transaction_lines["unit_price"], "transaction_lines.unit_price")
    transaction_lines["line_total"] = _to_numeric(transaction_lines["line_total"], "transaction_lines.line_total")
    transaction_lines["gross_line"] = transaction_lines["unit_price"] * transaction_lines["quantity"]

    transaction_lines["discount_amount_line"] = _compute_discount_amount_line(
        transaction_lines,
        discount_mode=discount_mode,
    )

    line_level = transaction_lines.merge(
        transactions[["transaction_id", "sales_date", "channel_type", "store_id"]],
        on="transaction_id",
        how="inner",
        validate="many_to_one",
    )

    dropped_lines = len(transaction_lines) - len(line_level)
    if dropped_lines > 0:
        print(f"Warning: dropped {dropped_lines} line rows with no matching transaction_id in transactions.csv.")

    # Reconcile per-transaction totals (sanity check): sum(line_total) vs transactions.total_amount
    # This does not fail the build by default; it warns if many transactions exceed tolerance.
    tx_lines_sum = (
        line_level.groupby("transaction_id", as_index=False)["line_total"].sum().rename(columns={"line_total": "lines_total"})
    )
    tx_totals = transactions[["transaction_id", "total_amount"]].copy()
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
        # Print a small sample to help debugging.
        sample = tx_check.loc[bad_mask, ["transaction_id", "total_amount", "lines_total", "abs_diff", "rel_diff"]].head(5)
        print("Sample mismatches:\n" + sample.to_string(index=False))

    group_cols = ["sales_date", "channel_type", "store_id"]
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

    gold["avg_order_value"] = np.where(gold["orders"] > 0, gold["net_sales"] / gold["orders"], 0.0)
    gold["discount_ratio"] = np.where(gold["gross_sales"] > 0, gold["discount_amount"] / gold["gross_sales"], 0.0)

    if returns_df is not None and not returns_df.empty:
        returns_work = returns_df.copy()
        if "refund_amount" not in returns_work.columns or "transaction_id" not in returns_work.columns:
            raise ValueError("returns.csv must contain transaction_id and refund_amount.")
        returns_work["refund_amount"] = _to_numeric(returns_work["refund_amount"], "returns.refund_amount")
        returns_joined = returns_work.merge(
            transactions[["transaction_id", "sales_date", "channel_type", "store_id"]],
            on="transaction_id",
            how="left",
            validate="many_to_one",
        )
        unmatched_returns = int(returns_joined["sales_date"].isna().sum())
        if unmatched_returns > 0:
            print(f"Warning: {unmatched_returns} return rows have no matching transaction_id; excluded from returns aggregation.")
        returns_agg = (
            returns_joined.dropna(subset=["sales_date", "channel_type", "store_id"])
            .groupby(group_cols, as_index=False)["refund_amount"]
            .sum()
            .rename(columns={"refund_amount": "returns_amount"})
        )
        gold = gold.merge(returns_agg, on=group_cols, how="left")
        gold["returns_amount"] = gold["returns_amount"].fillna(0.0)
    else:
        gold["returns_amount"] = 0.0

    stores_keep = ["store_id", "city", "region", "store_type"]
    gold = gold.merge(stores[stores_keep], on="store_id", how="left", validate="many_to_one")

    missing_store_meta = int(gold["city"].isna().sum())
    if missing_store_meta > 0:
        print(f"Warning: {missing_store_meta} gold rows have store_id not found in stores.csv (city/region/store_type are null).")

    gold["net_sales_after_returns"] = gold["net_sales"] - gold["returns_amount"]

    output_cols = [
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
        "avg_order_value",
        "discount_ratio",
        "returns_amount",
        "net_sales_after_returns",
    ]
    gold = gold[output_cols]

    # DQ checks
    null_keys = gold[["sales_date", "channel_type", "store_id"]].isna().any(axis=1)
    if null_keys.any():
        raise ValueError(f"DQ failed: found {int(null_keys.sum())} rows with null sales_date/channel_type/store_id.")

    if (gold["orders"] <= 0).any():
        bad = int((gold["orders"] <= 0).sum())
        raise ValueError(f"DQ failed: found {bad} rows where orders <= 0.")

    if (gold["net_sales"] < 0).any():
        bad = int((gold["net_sales"] < 0).sum())
        raise ValueError(f"DQ failed: found {bad} rows where net_sales < 0.")

    if (gold["discount_amount"] < 0).any():
        bad = int((gold["discount_amount"] < 0).sum())
        raise ValueError(f"DQ failed: found {bad} rows where discount_amount < 0.")

    ratio_outside = ~gold["discount_ratio"].between(0, 1.5, inclusive="both")
    if ratio_outside.any():
        print(
            f"Warning: found {int(ratio_outside.sum())} rows where discount_ratio is outside [0, 1.5]."
        )

    # Stable numeric dtypes for output and optional DB upload.
    gold["orders"] = gold["orders"].astype(int)
    for col in [
        "units",
        "gross_sales",
        "discount_amount",
        "net_sales",
        "avg_order_value",
        "discount_ratio",
        "returns_amount",
        "net_sales_after_returns",
    ]:
        gold[col] = pd.to_numeric(gold[col], errors="coerce").fillna(0.0)

    return gold


def print_summary(gold: pd.DataFrame) -> None:
    print("\nBuild summary")
    print("-------------")
    print(f"Rows: {len(gold):,}")
    print(f"Sales date min: {gold['sales_date'].min()}")
    print(f"Sales date max: {gold['sales_date'].max()}")
    print("\nTop 5 stores by net_sales:")
    top5 = (
        gold.groupby("store_id", as_index=False)["net_sales"]
        .sum()
        .sort_values("net_sales", ascending=False)
        .head(5)
    )
    print(top5.to_string(index=False))


def maybe_load_to_postgres(gold: pd.DataFrame) -> None:
    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        return

    try:
        from sqlalchemy import Date, Float, Integer, String, create_engine, text
    except ImportError as exc:
        raise RuntimeError(
            "DATABASE_URL is set but SQLAlchemy is not installed. Install sqlalchemy and psycopg2-binary."
        ) from exc

    print("\nDATABASE_URL detected; loading into Postgres table gold.gold_sales_daily...")
    engine = create_engine(db_url)

    to_db = gold.copy()
    to_db["sales_date"] = pd.to_datetime(to_db["sales_date"]).dt.date

    dtype_map = {
        "sales_date": Date(),
        "channel_type": String(),
        "store_id": String(),
        "city": String(),
        "region": String(),
        "store_type": String(),
        "orders": Integer(),
        "units": Float(),
        "gross_sales": Float(),
        "discount_amount": Float(),
        "net_sales": Float(),
        "avg_order_value": Float(),
        "discount_ratio": Float(),
        "returns_amount": Float(),
        "net_sales_after_returns": Float(),
    }

    with engine.begin() as conn:
        conn.execute(text("CREATE SCHEMA IF NOT EXISTS gold"))

    to_db.to_sql(
        "gold_sales_daily",
        con=engine,
        schema="gold",
        if_exists="replace",
        index=False,
        dtype=dtype_map,
        method="multi",
        chunksize=1000,
    )
    print("Loaded table: gold.gold_sales_daily")


def main() -> None:
    parser = argparse.ArgumentParser(description="Build gold_sales_daily from SILVER CSVs.")
    parser.add_argument(
        "--input-dir",
        default="./silver_csv",
        help="Folder containing SILVER CSV files (default: ./silver_csv).",
    )
    parser.add_argument(
        "--output-dir",
        default="./gold_csv",
        help="Folder for GOLD output CSV (default: ./gold_csv).",
    )
    parser.add_argument(
        "--discount-mode",
        default=DEFAULT_DISCOUNT_MODE,
        help="Discount mode: auto|amount|per_unit|percent (default: auto).",
    )
    parser.add_argument(
        "--reconcile-abs-tol",
        default=DEFAULT_RECONCILE_ABS_TOL,
        type=float,
        help=f"Absolute tolerance for transaction total reconciliation (default: {DEFAULT_RECONCILE_ABS_TOL}).",
    )
    parser.add_argument(
        "--reconcile-rel-tol",
        default=DEFAULT_RECONCILE_REL_TOL,
        type=float,
        help=f"Relative tolerance for transaction total reconciliation (default: {DEFAULT_RECONCILE_REL_TOL}).",
    )
    args = parser.parse_args()

    input_dir = Path(args.input_dir)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / "gold_sales_daily.csv"

    transactions, transaction_lines, stores, returns_df = load_inputs(input_dir)
    gold = transform(
        transactions,
        transaction_lines,
        stores,
        returns_df,
        discount_mode=args.discount_mode,
        reconcile_abs_tol=args.reconcile_abs_tol,
        reconcile_rel_tol=args.reconcile_rel_tol,
    )
    gold.to_csv(output_path, index=False)

    print(f"\nWrote: {output_path}")
    print_summary(gold)
    maybe_load_to_postgres(gold)


if __name__ == "__main__":
    main()
