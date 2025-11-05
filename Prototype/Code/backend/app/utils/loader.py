from __future__ import annotations
from typing import Any, Dict, Optional, Tuple, Iterable
import os
import pandas as pd
from sqlalchemy import create_engine, text
from app.core.config import settings

# Env-configurable view names for DB mode
DEFAULT_SALES_VIEW = os.getenv("SALES_VIEW", "SalesSummary")
DEFAULT_OPP_VIEW   = os.getenv("OPPORTUNITY_VIEW", "OpportunitySummary")

# ---------------------------
# Helpers: dtypes & renaming
# ---------------------------

def _safe_left_merge(left: pd.DataFrame, right: pd.DataFrame, left_key: str, right_key: str, suffixes=("", "")) -> pd.DataFrame:
    """
    Merge `left` with `right` if both the left_key exists in left and right_key exists in right
    and right is non-empty. Otherwise, return left unchanged.
    Never raises KeyError on missing keys; never blocks the load.
    """
    if left is None or left.empty:
        return left
    if right is None or right.empty:
        return left
    if left_key not in left.columns:
        return left
    if right_key not in right.columns:
        return left
    return left.merge(right, left_on=left_key, right_on=right_key, how="left", suffixes=suffixes)

def _coalesce_to(df: pd.DataFrame, target: str, candidates: list[str]) -> pd.DataFrame:
    """
    Create/normalize a single canonical `target` column by coalescing values
    from the first available candidates (in order). Drop the extra columns.
    Works even if none are present (creates target with NA).
    """
    exist = []
    seen = set()
    for c in candidates:
        if c in df.columns and c not in seen:
            exist.append(c)
            seen.add(c)

    if not exist:
        if target not in df.columns:
            df[target] = pd.NA
        return df

    s = df[exist[0]].copy()
    for c in exist[1:]:
        s = s.combine_first(df[c])

    df[target] = s

    for c in exist:
        if c != target and c in df.columns:
            df.drop(columns=[c], inplace=True, errors="ignore")
    return df

def _dedup_columns_inplace(df: pd.DataFrame) -> None:
    """
    If the same label appears more than once, keep the first occurrence.
    """
    if df.columns.duplicated().any():
        df.drop(columns=df.columns[df.columns.duplicated(keep='first')], inplace=True)

def _ensure_col(df: pd.DataFrame, target: str, candidates: list[str]) -> pd.DataFrame:
    if target in df.columns:
        return df
    low = {c.lower(): c for c in df.columns}
    for cand in candidates:
        if cand.lower() in low:
            return df.rename(columns={low[cand.lower()]: target})
    df[target] = pd.NA
    return df

def _to_str_id(s: pd.Series) -> pd.Series:
    # tolerate accidental DataFrame
    if isinstance(s, pd.DataFrame):
        s = s.iloc[:, 0]
    if s.dtype.kind in ("i", "u", "f", "b"):
        s = s.astype("string")
    else:
        s = s.astype("string", copy=False)
    s = s.str.strip()
    s = s.str.replace(r"\.0$", "", regex=True)
    return s.fillna(pd.NA)

def _to_num(s: pd.Series) -> pd.Series:
    return pd.to_numeric(s, errors="coerce")

def _read_sql(engine, sql: str) -> pd.DataFrame:
    with engine.connect() as conn:
        return pd.read_sql(text(sql), conn)

# ---------------------------
# CSV loader (processed dir)
# ---------------------------
def _load_from_csv(base_dir: str) -> Tuple[pd.DataFrame, pd.DataFrame]:
    def p(name: str) -> str:
        return os.path.join(base_dir, name)

    # --- load
    sales     = pd.read_csv(p("sales_transactions_enriched.csv"))
    products  = pd.read_csv(p("products.csv"))
    customers = pd.read_csv(p("customers.csv"))
    salesreps = pd.read_csv(p("salesreps.csv"))
    regions   = pd.read_csv(p("regions.csv"))
    opp_path  = p("opportunities.csv")
    opp       = pd.read_csv(opp_path) if os.path.exists(opp_path) else pd.DataFrame()

    # --- normalize column names: strip + lowercase
    for df in (sales, products, customers, salesreps, regions, opp):
        if not df.empty:
            df.columns = [c.strip().lower() for c in df.columns]
            _dedup_columns_inplace(df)

    # ----- normalize dimension IDs -----
    def _ensure_dim_id(df_dim: pd.DataFrame, candidates: list[str]) -> pd.DataFrame:
        if df_dim.empty:
            return df_dim
        # rename one of the candidates to 'id' or synthesize
        low = {c.lower(): c for c in df_dim.columns}
        found = None
        for cand in candidates:
            if cand.lower() in low:
                found = low[cand.lower()]
                break
        if found and found != "id":
            df_dim.rename(columns={found: "id"}, inplace=True)
        if "id" not in df_dim.columns:
            df_dim["id"] = range(1, len(df_dim) + 1)
        df_dim["id"] = _to_str_id(df_dim["id"])
        return df_dim

    products  = _ensure_dim_id(products,  ["product id","product_id","prod_id","id"])
    customers = _ensure_dim_id(customers, ["customer id","customer_id","cust_id","id"])
    salesreps = _ensure_dim_id(salesreps, ["salesrep id","sales_rep_id","salesrep_id","rep_id","id"])
    regions   = _ensure_dim_id(regions,   ["region id","region_id","id","region"])

    # friendly labels in dims (if present)
    def _alias(df, mapping):
        low = {c.lower(): c for c in df.columns}
        ren = {}
        for src, dst in mapping.items():
            if src in low and low[src] != dst:
                ren[low[src]] = dst
        return df.rename(columns=ren)

    products  = _alias(products,  {"product name":"product_name", "category":"category", "sub-category":"sub_category"})
    customers = _alias(customers, {"customer name":"customer_name", "segment":"segment"})
    salesreps = _alias(salesreps, {"salesrep name":"rep_name", "rep name":"rep_name"})
    regions   = _alias(regions,   {"region":"region_name"})  # keep region_name even if no state/city

    # If regions.csv lacks state/city, add empty
    for col in ("state","city"):
        if col not in regions.columns:
            regions[col] = None

    # ----- normalize sales fact -----
    sales = _alias(sales, {
        "order date":"order_date",
        "quantity":"quantity",
        "sales":"sales_amount",
        "discount":"discount",
        "profit":"profit",
        "product id":"product_id",
        "customer id":"customer_id",
        "salesrep id":"sales_rep_id",
        "rep_id":"sales_rep_id",
        "region id":"region_id"
    })

    # Coalesce FK synonyms and guarantee presence
    sales = _coalesce_to(sales, "product_id",   ["product_id","product id","prod_id","sku","item_id"])
    sales = _coalesce_to(sales, "customer_id",  ["customer_id","customer id","cust_id","client_id"])
    sales = _coalesce_to(sales, "sales_rep_id", ["sales_rep_id","salesrep id","salesrep_id","rep_id","sales rep id"])
    sales = _coalesce_to(sales, "region_id",    ["region_id","region id","region"])  # fall back to 'region' label

    # If any still missing, create it
    for fk in ("product_id","customer_id","sales_rep_id","region_id"):
        if fk not in sales.columns:
            sales[fk] = pd.NA

    # Coerce FK columns to clean strings (prevents int/str merges)
    for fk in ("product_id","customer_id","sales_rep_id","region_id"):
        sales[fk] = _to_str_id(sales[fk])

    # Numerics (optional)
    for col in ("sales_amount","quantity","discount","profit"):
        if col in sales.columns:
            sales[col] = _to_num(sales[col]).fillna(0)

    # Build SalesSummary-like frame (tolerant left joins)
    # --- guarantee FK columns exist before any merge (even if all NA)
    for fk in ("product_id", "customer_id", "sales_rep_id", "region_id"):
        if fk not in sales.columns:
            sales[fk] = pd.NA

    # Coerce FKs to strings (prevents int/str merge mismatches)
    for fk in ("product_id", "customer_id", "sales_rep_id", "region_id"):
        sales[fk] = _to_str_id(sales[fk])

    # Build SalesSummary-like frame with SAFE merges
    sales_summary = sales.copy()

    sales_summary = _safe_left_merge(sales_summary, products,  "product_id",   "id", suffixes=("", "_p"))
    sales_summary = _safe_left_merge(sales_summary, customers, "customer_id",  "id", suffixes=("", "_c"))
    sales_summary = _safe_left_merge(sales_summary, salesreps, "sales_rep_id", "id", suffixes=("", "_sr"))
    sales_summary = _safe_left_merge(sales_summary, regions,   "region_id",    "id", suffixes=("", "_r"))

    # Columns the tools expect
    needed = [
        "order_date","quantity","sales_amount","discount","profit",
        "product_name","category","sub_category",
        "customer_name","segment",
        "rep_name",
        "region_name","state","city",
        # convenience aliases many tool funcs infer:
        "revenue","units","order_id","salesperson","country","channel","aov","sales_cycle_days","is_returning",
        "lead_date","close_date","opportunity_id","stage","first_purchase_date","city"  # some already above
    ]
    # derive a couple of helpful aliases if missing
    if "revenue" not in sales_summary.columns and "sales_amount" in sales_summary.columns:
        sales_summary["revenue"] = sales_summary["sales_amount"]
    if "salesperson" not in sales_summary.columns and "rep_name" in sales_summary.columns:
        sales_summary["salesperson"] = sales_summary["rep_name"]

    for col in needed:
        if col not in sales_summary.columns:
            sales_summary[col] = None

    sales_summary = sales_summary[needed]

    # ----- OpportunitySummary-like (optional) -----
    opp_summary = pd.DataFrame()
    if not opp.empty:
        opp = _alias(opp, {
            "created date":"created_date",
            "probability":"probability",
            "amount":"deal_amount",
            "salesrep id":"sales_rep_id",
            "rep_id":"sales_rep_id",
            "region id":"region_id"
        })
        opp = _coalesce_to(opp, "sales_rep_id", ["sales_rep_id","salesrep id","salesrep_id","rep_id","sales rep id"])
        opp = _coalesce_to(opp, "region_id",    ["region_id","region id","region"])
        for fk in ("sales_rep_id","region_id"):
            if fk not in opp.columns:
                opp[fk] = pd.NA
            opp[fk] = _to_str_id(opp[fk])

        opp_summary = (
            opp
            .merge(salesreps, left_on="sales_rep_id", right_on="id", how="left")
            .merge(regions,   left_on="region_id",    right_on="id", how="left")
        )
        need_opp = ["created_date","stage","probability","deal_amount","rep_name","region_name","state","city"]
        for c in need_opp:
            if c not in opp_summary.columns:
                opp_summary[c] = None
        opp_summary = opp_summary[need_opp]

    return sales_summary, opp_summary

# ---------------------------
# Filter normalization (fail-soft)
# ---------------------------
def _as_list(x):
    if x is None or x == "" or x == []:
        return []
    if isinstance(x, (list, tuple, set)):
        return list(x)
    if isinstance(x, dict):
        return []
    return [x]


def _validate_filters(filters: dict | None) -> dict:
    """Strict validation for supported filters only."""
    allowed = {"date_from": (str, type(None)),
               "date_to":   (str, type(None)),
               "regions":   ((list, tuple, set), type(None), str),
               "reps":      ((list, tuple, set), type(None), str),
               "categories":((list, tuple, set), type(None), str)}
    f = dict(filters or {})
    unknown = sorted([k for k in f.keys() if k not in allowed])
    if unknown:
        raise ValueError(f"Unsupported filter key(s): {', '.join(unknown)}. "
                         "Allowed: date_from, date_to, regions, reps, categories.")
    # type checks
    for k, types in allowed.items():
        v = f.get(k)
        if v is None:
            continue
        if isinstance(types, tuple):
            valid_types = types
        else:
            valid_types = (types,)
        if not isinstance(v, valid_types):
            raise TypeError(f"{k} has invalid type {type(v).__name__}.")
    # date sanity if both provided
    from datetime import datetime
    def _parse(d):
        if d is None: return None
        for fmt in ("%Y-%m-%d","%Y/%m/%d","%d-%m-%Y"):
            try:
                return datetime.strptime(str(d), fmt).date()
            except Exception:
                continue
        raise ValueError(f"{d} is not a valid date (use YYYY-MM-DD).")
    dfrom = _parse(f.get("date_from")) if f.get("date_from") else None
    dto   = _parse(f.get("date_to")) if f.get("date_to") else None
    if dfrom and dto and dfrom > dto:
        raise ValueError("date_from must be ≤ date_to.")
    return f


def _normalize_filters_for_loader(filters: dict | None) -> dict:
    f = dict(filters or {})
    f["regions"]    = _as_list(f.get("regions"))
    f["reps"]       = _as_list(f.get("reps"))
    f["categories"] = _as_list(f.get("categories"))
    return f



def load_frames(filters: Optional[Dict[str, Any]] = None) -> pd.DataFrame:
    """
    Load data from demo_sales.csv, preprocess it, and apply filters.
    """
    csv_path = os.path.join("database", "data", "demo_sales.csv")
    try:
        # Load the CSV file
        df = pd.read_csv(csv_path)
        print(f"[DEBUG] Loaded demo_sales.csv with columns: {df.columns}")  # Debug: Check loaded columns

        # Preprocess the DataFrame
        from app.utils.data_functions import preprocess, apply_filters
        df = preprocess(df)

        # Apply filters
        if filters:
            filters = _validate_filters(filters)
            filters = _normalize_filters_for_loader(filters)
            df = apply_filters(
                df,
                filters.get("date_from"),
                filters.get("date_to"),
                filters.get("regions"),
                filters.get("reps"),
                filters.get("categories"),
            )

        return df  # Return the single DataFrame
    except Exception as e:
        raise RuntimeError(f"Failed to load or process demo_sales.csv: {e}")

def load_dataframe_for_tool(tool_name: str, filters: Optional[Dict[str, Any]] = None) -> pd.DataFrame:
    """
    Load the preprocessed and filtered DataFrame for any tool.
    The tool_name parameter is ignored in this simplified version.
    """
    try:
        df = load_frames(filters)  # Call the updated load_frames function
        print(f"[DEBUG] DataFrame loaded for tool {tool_name} with columns: {df.columns}")  # Debug: Check loaded columns
        return df  # Return the single DataFrame
    except Exception as e:
        raise RuntimeError(f"Failed to load DataFrame for tool {tool_name}: {e}")