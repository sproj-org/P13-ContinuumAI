import pandas as pd
import numpy as np


def load_data_from_buffer(buffer):
    """Read CSV from uploaded buffer and preprocess."""
    df = pd.read_csv(buffer)
    return preprocess(df)


def load_data_from_file(file_path):
    """Load CSV from file path and preprocess."""
    df = pd.read_csv(file_path)
    return preprocess(df)


def preprocess(df: pd.DataFrame) -> pd.DataFrame:
    """Normalize column names, parse dates, coerce numerics, and add useful grouping columns."""
    df = df.copy()

    # normalize column names
    df.columns = [c.strip() for c in df.columns]

    # try parsing common date columns into canonical names
    date_mapping = {
        "order_date": ["order_date", "order date", "date", "orderdate"],
        "first_purchase_date": [
            "first_purchase_date",
            "first purchase date",
            "first_purchase",
        ],
        "lead_date": ["lead_date", "lead date", "leaddate"],
        "close_date": ["close_date", "close date", "closed_date"],
    }
    for canon, variants in date_mapping.items():
        for variant in variants:
            if variant in df.columns:
                df[canon] = pd.to_datetime(df[variant], errors="coerce")
                break

    # numeric coercion
    for col in ["units", "revenue", "aov", "sales_cycle_days", "is_returning"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    # compute aov if missing
    if "aov" not in df.columns or df["aov"].isna().all():
        if "revenue" in df.columns and "units" in df.columns:
            df["aov"] = df["revenue"] / df["units"].replace(0, np.nan)
        elif "revenue" in df.columns:
            df["aov"] = df["revenue"]

    # sales cycle days
    if "sales_cycle_days" not in df.columns or df["sales_cycle_days"].isna().all():
        if "close_date" in df.columns and "lead_date" in df.columns:
            df["sales_cycle_days"] = (
                pd.to_datetime(df["close_date"]) - pd.to_datetime(df["lead_date"])
            ).dt.days
        else:
            df["sales_cycle_days"] = 0

    # is_returning fallback
    if "is_returning" not in df.columns or df["is_returning"].isna().all():
        if "first_purchase_date" in df.columns and "order_date" in df.columns:
            df["is_returning"] = (
                pd.to_datetime(df["order_date"])
                > pd.to_datetime(df["first_purchase_date"])
            ).astype(int)
        else:
            df["is_returning"] = 0

    # cast IDs to strings
    for idcol in ["customer_id", "order_id", "product_id", "opportunity_id"]:
        if idcol in df.columns:
            df[idcol] = df[idcol].astype(str)

    # fill categories
    for cat in [
        "product_name",
        "category",
        "salesperson",
        "region",
        "country",
        "city",
        "channel",
    ]:
        if cat in df.columns:
            df[cat] = df[cat].fillna("Unknown")

    # fallback order_date -> synthetic increasing dates if completely missing
    if "order_date" not in df.columns or df["order_date"].isna().all():
        df["order_date"] = pd.date_range(start="2024-01-01", periods=len(df), freq="D")

    # helper grouping columns
    if "order_date" in df.columns:
        df["order_date_only"] = df["order_date"].dt.date
        df["order_month"] = df["order_date"].dt.to_period("M").dt.to_timestamp()
        df["order_week"] = df["order_date"].dt.to_period("W").dt.start_time

    return df


def apply_filters(df, date_from, date_to, regions=None, reps=None, categories=None):
    """Return filtered dataframe based on provided UI selections."""
    df2 = df.copy()

    # Handle date filtering with proper date comparison
    if "order_date" in df2.columns:
        # Ensure order_date is datetime
        if not pd.api.types.is_datetime64_any_dtype(df2["order_date"]):
            df2["order_date"] = pd.to_datetime(df2["order_date"])

        if date_from:
            # Convert to same type for comparison
            if hasattr(date_from, "date"):
                date_from = date_from.date()
            df2 = df2[df2["order_date"].dt.date >= date_from]

        if date_to:
            # Convert to same type for comparison
            if hasattr(date_to, "date"):
                date_to = date_to.date()
            df2 = df2[df2["order_date"].dt.date <= date_to]

    if regions and len(regions) > 0 and "All" not in regions:
        df2 = df2[df2["region"].isin(regions)]
    if reps and len(reps) > 0 and "All" not in reps:
        df2 = df2[df2["salesperson"].isin(reps)]
    if categories and len(categories) > 0 and "All" not in categories:
        df2 = df2[df2["category"].isin(categories)]

    return df2

def _apply_filters_from_params(df, date_from, date_to, regions, reps, categories):
    """Helper to parse and apply filters from query parameters"""
    regions_list = regions.split(",") if regions else None
    reps_list = reps.split(",") if reps else None
    categories_list = categories.split(",") if categories else None
    
    date_from_dt = pd.to_datetime(date_from).date() if date_from else None
    date_to_dt = pd.to_datetime(date_to).date() if date_to else None
    
    return apply_filters(df, date_from_dt, date_to_dt, regions_list, reps_list, categories_list)

def compute_kpis(df):
    """Compute key performance indicators with proper NaN handling"""
    kpis = {}
    
    # Basic metrics
    kpis["total_revenue"] = float(df["revenue"].sum()) if not df["revenue"].isna().all() else 0.0
    kpis["total_orders"] = len(df)
    
    # Handle NaN values explicitly
    avg_aov = df["aov"].mean()
    kpis["avg_aov"] = float(avg_aov) if not pd.isna(avg_aov) else 0.0
    
    # Conversion rate with NaN handling
    if "is_returning" in df.columns:
        returning_customers = df["is_returning"].sum()
        total_customers = len(df["customer_id"].unique())
        conversion_rate = returning_customers / total_customers if total_customers > 0 else 0.0
        kpis["conversion_rate"] = float(conversion_rate) if not pd.isna(conversion_rate) else 0.0
    else:
        kpis["conversion_rate"] = 0.0
    
    # Customer counts
    kpis["new_count"] = len(df[df.get("is_returning", 0) == 0])
    kpis["returning_count"] = len(df[df.get("is_returning", 0) == 1])
    
    return kpis

#to Help with charts data travelling from backend to frontend over fastapi
def make_json_serializable(obj):
    """Convert pandas/numpy objects to JSON-serializable Python types"""
    if isinstance(obj, dict):
        return {key: make_json_serializable(value) for key, value in obj.items()}
    elif isinstance(obj, list):
        return [make_json_serializable(item) for item in obj]
    elif isinstance(obj, (np.integer, np.int64, np.int32)):
        return int(obj)
    elif isinstance(obj, (np.floating, np.float64, np.float32)):
        return float(obj) if not np.isnan(obj) else 0.0
    elif isinstance(obj, np.ndarray):
        return [make_json_serializable(item) for item in obj.tolist()]
    elif pd.isna(obj):
        return None
    else:
        return obj