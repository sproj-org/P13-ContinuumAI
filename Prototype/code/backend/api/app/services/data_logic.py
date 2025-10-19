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


def compute_kpis(df):
    """Compute a small set of KPIs used by the UI."""
    total_revenue = float(df["revenue"].sum()) if "revenue" in df.columns else 0.0
    total_orders = df["order_id"].nunique() if "order_id" in df.columns else len(df)
    avg_aov = (
        float(df["aov"].mean())
        if "aov" in df.columns
        else (total_revenue / total_orders if total_orders else 0)
    )

    conversion_rate = np.nan
    if "opportunity_id" in df.columns and "stage" in df.columns:
        total_opps = df["opportunity_id"].nunique()
        closed_opp_mask = df["stage"].str.lower().str.contains("closed|won", na=False)
        closed_opps = df[closed_opp_mask]["opportunity_id"].nunique()
        conversion_rate = (closed_opps / total_opps) if total_opps else np.nan

    new_count = returning_count = 0
    if "customer_id" in df.columns:
        cust_counts = df.drop_duplicates(subset=["customer_id"])
        returning_count = (
            int(cust_counts["is_returning"].sum())
            if "is_returning" in cust_counts.columns
            else 0
        )
        new_count = len(cust_counts) - returning_count

    return {
        "total_revenue": total_revenue,
        "total_orders": int(total_orders),
        "avg_aov": avg_aov,
        "conversion_rate": conversion_rate,
        "new_count": int(new_count),
        "returning_count": int(returning_count),
    }
