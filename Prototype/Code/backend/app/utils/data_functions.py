from __future__ import annotations
from typing import Optional, Tuple, Dict, Any
from datetime import datetime, date
import numpy as np
import pandas as pd
import plotly.graph_objects as go
import plotly.io as pio

def _as_list(x):
    if x is None or x == "" or x == []:
        return []
    if isinstance(x, (list, tuple, set)):
        return list(x)
    if isinstance(x, dict):  # bad shape from UI; ignore
        return []
    return [x]

# --------------------
# Preprocess & Filters
# --------------------

def preprocess(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df.columns = [c.strip() for c in df.columns]

    # Flexible column normalizations for this project schema
    # (order_date may already be datetime; tolerate missing)
    for c in ("order_date","first_purchase_date","lead_date","close_date"):
        if c in df.columns:
            df[c] = pd.to_datetime(df[c], errors="coerce")

    # Numeric coercions if present
    for col in ["units","revenue","aov","sales_cycle_days","is_returning","discount","profit"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    # aov fallback
    if "aov" in df.columns:
        if df["aov"].isna().all() and "revenue" in df.columns:
            denom = df["units"].replace({0: np.nan}) if "units" in df.columns else np.nan
            with np.errstate(divide="ignore", invalid="ignore"):
                df["aov"] = df["revenue"] / denom
    elif "revenue" in df.columns and "units" in df.columns:
        denom = df["units"].replace({0: np.nan})
        with np.errstate(divide="ignore", invalid="ignore"):
            df["aov"] = df["revenue"] / denom

    # sales_cycle_days fallback
    if "sales_cycle_days" not in df.columns and {"lead_date","close_date"} <= set(df.columns):
        df["sales_cycle_days"] = (df["close_date"] - df["lead_date"]).dt.days

    # is_returning fallback
    if "is_returning" not in df.columns and {"first_purchase_date","order_date"} <= set(df.columns):
        df["is_returning"] = np.where(
            (~df["first_purchase_date"].isna())
            & (~df["order_date"].isna())
            & (df["first_purchase_date"] < df["order_date"]), 1, 0
        )

    for idcol in ["customer_id","order_id","product_id","opportunity_id"]:
        if idcol in df.columns:
            df[idcol] = df[idcol].astype(str)

    for cat in ["product_name","category","salesperson","region","country","city","channel"]:
        if cat in df.columns:
            df[cat] = df[cat].fillna("Unknown")

    if "order_date" in df.columns and df["order_date"].dtype.kind != "M":
        try:
            df["order_date"] = pd.to_datetime(df["order_date"], errors="coerce")
        except Exception:
            pass

    if "order_date" in df.columns:
        df["order_date_only"] = df["order_date"].dt.date
        df["order_month"] = df["order_date"].dt.to_period("M").dt.to_timestamp()
        df["order_week"] = df["order_date"].dt.to_period("W").dt.start_time

    return df

def apply_filters(
    df: pd.DataFrame,
    date_from: date | str | None = None,
    date_to: date | str | None = None,
    regions: list | str | None = None,
    reps: list | str | None = None,
    categories: list | str | None = None,
) -> pd.DataFrame:
    """Filter dataset by date range and optional lists. Accepts strings or lists; 'All' disables that filter."""
    
    print("DEBUG|apply_filters incoming:", {
        "date_from": date_from, "date_to": date_to,
        "regions": regions, "reps": reps, "categories": categories
    })

    out = df.copy()

    def _to_date(x):
        if isinstance(x, date):
            return x
        if isinstance(x, str) and x.strip():
            for fmt in ("%Y-%m-%d","%Y/%m/%d","%d-%m-%Y"):
                try:
                    return datetime.strptime(x.strip(), fmt).date()
                except Exception:
                    continue
        return None

    dfrom = _to_date(date_from)
    dto   = _to_date(date_to)

    if "order_date" in out.columns and (dfrom or dto):
        od = pd.to_datetime(out["order_date"], errors="coerce")
        mask = pd.Series(True, index=out.index)
        if dfrom is not None:
            mask &= (od.dt.date >= dfrom)
        if dto is not None:
            mask &= (od.dt.date <= dto)
        out = out.loc[mask]


    regions    = _as_list(regions)
    reps       = _as_list(reps)
    categories = _as_list(categories)

    region_col = "region" if "region" in out.columns else ("region_name" if "region_name" in out.columns else None)
    rep_col    = "salesperson" if "salesperson" in out.columns else ("rep_name" if "rep_name" in out.columns else None)
    cat_col    = "category" if "category" in out.columns else None

    if regions and "All" not in regions and region_col:
        out = out[out[region_col].isin(regions)]
    if reps and "All" not in reps and rep_col:
        out = out[out[rep_col].isin(reps)]
    if categories and "All" not in categories and cat_col:
        out = out[out[cat_col].isin(categories)]


    return out

# --- tool metadata decorator ---
def tool(meta: dict):
    def wrap(fn):
        setattr(fn, "__tool_meta__", meta or {})
        return fn
    return wrap

def _to_json(fig: go.Figure) -> dict:
    return fig.to_plotly_json()


# ---------- KPI functions (return Plotly Indicator JSON) ----------

@tool({"requires": ["revenue"], "returns": "indicator", "intent": ["total revenue", "overall sales", "sum of revenue"]})
def total_revenue(df: pd.DataFrame, revenue_col: str = "revenue") -> dict:
    if revenue_col not in df.columns:
        return {"type": "error", "error": f"Missing column '{revenue_col}'"}
    value = float(df[revenue_col].sum())
    fig = go.Figure(
        go.Indicator(
            mode="number",
            value=value,
            title={"text": "Total Revenue"},
            number={"prefix": "$", "valueformat": ",.2f"},
        )
    )
    fig.update_layout(height=140, margin=dict(t=10, b=10, l=10, r=10))
    return _to_json(fig)

@tool({"requires": ["order_id"], "returns": "indicator", "intent": ["total orders", "number of orders", "order count"]})
def total_orders(df: pd.DataFrame, order_id_col: str = "order_id") -> dict:
    if order_id_col not in df.columns:
        return {"type": "error", "error": f"Missing column '{order_id_col}'"}
    value = int(df[order_id_col].nunique())
    fig = go.Figure(
        go.Indicator(
            mode="number",
            value=value,
            title={"text": "Total Orders"},
            number={"valueformat": ","},
        )
    )
    fig.update_layout(height=120, margin=dict(t=8, b=8, l=8, r=8))
    return _to_json(fig)

@tool({"requires": ["aov", "revenue"], "returns": "indicator", "intent": ["average order value", "aov", "mean order value"]})
def avg_aov(df: pd.DataFrame, aov_col: str = "aov") -> dict:
    if aov_col in df.columns and not df[aov_col].isna().all():
        value = float(df[aov_col].mean())
    elif "revenue" in df.columns:
        orders = df["order_id"].nunique() if "order_id" in df.columns else len(df)
        value = float(df["revenue"].sum() / orders) if orders else 0.0
    else:
        return {"type": "error", "error": "Missing columns 'aov' or 'revenue'"}
    fig = go.Figure(
        go.Indicator(
            mode="number",
            value=value,
            title={"text": "Avg AOV"},
            number={"prefix": "$", "valueformat": ",.2f"},
        )
    )
    fig.update_layout(height=120, margin=dict(t=8, b=8, l=8, r=8))
    return _to_json(fig)

@tool({"requires": ["opportunity_id", "stage"], "returns": "gauge", "intent": ["conversion rate", "win rate", "deal closure rate"]})
def conversion_rate(
    df: pd.DataFrame, opp_col: str = "opportunity_id", stage_col: str = "stage"
) -> dict:
    if opp_col not in df.columns or stage_col not in df.columns:
        return {
            "type": "error",
            "error": f"Missing columns '{opp_col}' or '{stage_col}'",
        }
    total_opps = df[opp_col].nunique()
    closed_mask = df[stage_col].str.lower().str.contains("closed|won", na=False)
    closed_opps = df[closed_mask][opp_col].nunique()
    value = (closed_opps / total_opps) if total_opps else 0.0
    fig = go.Figure(
        go.Indicator(
            mode="gauge+number",
            value=value * 100,
            title={"text": "Conversion Rate (%)"},
            gauge={"axis": {"range": [0, 100]}},
        )
    )
    fig.update_layout(height=180, margin=dict(t=8, b=8, l=8, r=8))
    return _to_json(fig)

@tool({"requires": ["customer_id", "is_returning"], "returns": "indicator", "intent": ["new customers", "customer acquisition", "first time buyers"]})
def new_customers_count(
    df: pd.DataFrame,
    customer_col: str = "customer_id",
    returning_flag_col: str = "is_returning",
) -> dict:
    if customer_col not in df.columns:
        return {"type": "error", "error": f"Missing column '{customer_col}'"}
    cust_unique = df.drop_duplicates(subset=[customer_col])
    returning = (
        int(cust_unique[returning_flag_col].sum())
        if returning_flag_col in cust_unique.columns
        else 0
    )
    new = len(cust_unique) - returning
    fig = go.Figure(
        go.Indicator(
            mode="number",
            value=new,
            title={"text": "New Customers (unique)"},
            number={"valueformat": ","},
        )
    )
    fig.update_layout(height=120, margin=dict(t=8, b=8, l=8, r=8))
    return _to_json(fig)

@tool({"requires": ["customer_id", "is_returning"], "returns": "indicator", "intent": ["returning customers", "repeat customers", "loyalty"]})
def returning_customers_count(
    df: pd.DataFrame,
    customer_col: str = "customer_id",
    returning_flag_col: str = "is_returning",
) -> dict:
    if customer_col not in df.columns:
        return {"type": "error", "error": f"Missing column '{customer_col}'"}
    cust_unique = df.drop_duplicates(subset=[customer_col])
    returning = (
        int(cust_unique[returning_flag_col].sum())
        if returning_flag_col in cust_unique.columns
        else 0
    )
    fig = go.Figure(
        go.Indicator(
            mode="number",
            value=returning,
            title={"text": "Returning Customers (unique)"},
            number={"valueformat": ","},
        )
    )
    fig.update_layout(height=120, margin=dict(t=8, b=8, l=8, r=8))
    return _to_json(fig)


# ---------- Time series & trends ----------

@tool({"requires": ["order_date", "revenue"], "returns": "timeseries", "intent": ["sales over time", "revenue trend", "time series of revenue"]})
def sales_over_time(
    df: pd.DataFrame,
    resample: str = "W",
    revenue_col: str = "revenue",
    rolling_window: Optional[int] = None,
) -> dict:
    if "order_date" not in df.columns or revenue_col not in df.columns:
        return {"type": "error", "error": "Missing 'order_date' or revenue column"}
    tmp = (
        df.set_index("order_date")
        .resample(resample)[revenue_col]
        .sum()
        .reset_index()
        .rename(columns={revenue_col: "revenue"})
    )
    tmp = tmp.sort_values("order_date")
    date_strs = tmp["order_date"].dt.strftime("%Y-%m-%d").tolist()
    revenue_vals = tmp["revenue"].tolist()

    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=date_strs,
            y=revenue_vals,
            mode="lines",
            name="Revenue",
            line=dict(shape="spline", smoothing=0.3),
        )
    )
    if rolling_window:
        tmp["rolling"] = tmp["revenue"].rolling(rolling_window, min_periods=1).mean()
        rolling_vals = tmp["rolling"].tolist()
        fig.add_trace(
            go.Scatter(
                x=date_strs,
                y=rolling_vals,
                name=f"{rolling_window}-period rolling",
                mode="lines",
                line=dict(shape="spline", smoothing=0.3),
            )
        )
    fig.update_layout(
        title="Sales Over Time",
        xaxis_title="Date",
        yaxis_title="Revenue",
        template="plotly_white",
        height=480,
        xaxis=dict(tickformat="%b %Y", dtick="M1"),
    )
    return _to_json(fig)

@tool({"requires": ["order_date", "aov"], "returns": "timeseries", "intent": ["aov over time", "average order value trend", "pricing trend"]})
def aov_over_time(df: pd.DataFrame, resample: str = "M", aov_col: str = "aov") -> dict:
    if "order_date" not in df.columns or aov_col not in df.columns:
        return {"type": "error", "error": "Missing 'order_date' or aov column"}
    tmp = (
        df.set_index("order_date")
        .resample(resample)[aov_col]
        .mean()
        .reset_index()
        .rename(columns={aov_col: "aov"})
    )
    tmp = tmp.dropna(subset=["aov"])
    date_strs = tmp["order_date"].dt.strftime("%Y-%m-%d").tolist()
    aov_vals = [float(x) if not pd.isna(x) else 0.0 for x in tmp["aov"].tolist()]

    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=date_strs,
            y=aov_vals,
            mode="lines+markers",
            name="AOV",
            line=dict(shape="spline", smoothing=0.3),
        )
    )
    fig.update_layout(
        title="AOV Over Time",
        xaxis_title="Date",
        yaxis_title="AOV",
        template="plotly_white",
        height=420,
        xaxis=dict(tickformat="%b %Y", dtick="M1"),
    )
    return _to_json(fig)

@tool({"requires": ["order_date", "customer_id", "is_returning"], "returns": "stacked area", "intent": ["new vs returning over time", "customer cohorts", "repeat customer trend"]})
def repeat_new_customers_over_time(df: pd.DataFrame, resample: str = "M") -> dict:
    if (
        "order_date" not in df.columns
        or "customer_id" not in df.columns
        or "is_returning" not in df.columns
    ):
        return {
            "type": "error",
            "error": "Missing one of 'order_date','customer_id','is_returning'",
        }

    tmp = df.copy()
    tmp["order_date"] = pd.to_datetime(tmp["order_date"], errors="coerce")
    tmp["is_returning"] = tmp["is_returning"].fillna(0).astype(int)

    grp = (
        tmp.groupby([pd.Grouper(key="order_date", freq=resample), "is_returning"])[
            "customer_id"
        ]
        .nunique()
        .reset_index()
    )
    grp = grp.rename(columns={"customer_id": "unique_customers"})

    wide = (
        grp.pivot(index="order_date", columns="is_returning", values="unique_customers")
        .fillna(0)
        .rename(columns={0: "new", 1: "returning"})
    )

    date_strs = wide.index.strftime("%Y-%m-%d").tolist()
    new_vals = wide["new"].tolist() if "new" in wide.columns else []
    returning_vals = wide["returning"].tolist() if "returning" in wide.columns else []

    fig = go.Figure()
    if "new" in wide.columns:
        fig.add_trace(
            go.Scatter(
                x=date_strs,
                y=new_vals,
                stackgroup="one",
                name="New",
                mode="lines",
                line=dict(shape="spline", smoothing=0.3),
            )
        )
    if "returning" in wide.columns:
        fig.add_trace(
            go.Scatter(
                x=date_strs,
                y=returning_vals,
                stackgroup="one",
                name="Returning",
                mode="lines",
                line=dict(shape="spline", smoothing=0.3),
            )
        )

    fig.update_layout(
        title="New vs Returning Customers Over Time",
        xaxis_title="Date",
        yaxis_title="Unique customers",
        template="plotly_white",
        height=420,
        xaxis=dict(tickformat="%b %Y", dtick="M1"),
    )
    return _to_json(fig)


# ---------- Products & Pareto ----------

@tool({"requires": ["product_name", "revenue"], "returns": "bar", "intent": ["top products by revenue", "bestselling products", "product ranking"]})
def top_products_by_revenue(df: pd.DataFrame, top_n: int = 20) -> dict:
    if "product_name" not in df.columns or "revenue" not in df.columns:
        return {"type": "error", "error": "Missing 'product_name' or 'revenue'"}
    prod = (
        df.groupby("product_name", as_index=False)["revenue"]
        .sum()
        .sort_values("revenue", ascending=False)
        .head(int(top_n))
    )
    prod = prod.iloc[::-1]

    prod_names = prod["product_name"].tolist()
    revenue_vals = prod["revenue"].tolist()
    revenue_labels = [f"${x:,.0f}" for x in revenue_vals]

    fig = go.Figure(
        go.Bar(
            x=revenue_vals,
            y=prod_names,
            orientation="h",
            text=revenue_labels,
            textposition="auto",
        )
    )
    fig.update_layout(
        title=f"Top {top_n} Products by Revenue",
        xaxis_title="Revenue",
        yaxis_title="Product",
        height=480,
        template="plotly_white",
    )
    return _to_json(fig)

@tool({"requires": ["product_name", "revenue"], "returns": "dual-axis", "intent": ["pareto analysis", "80/20 rule", "cumulative revenue by product"]})
def pareto_product_revenue(df: pd.DataFrame, top_n: int = 50) -> dict:
    if "product_name" not in df.columns or "revenue" not in df.columns:
        return {"type": "error", "error": "Missing 'product_name' or 'revenue'"}
    prod = (
        df.groupby("product_name", as_index=False)["revenue"]
        .sum()
        .sort_values("revenue", ascending=False)
    )
    prod["cumperc"] = prod["revenue"].cumsum() / prod["revenue"].sum() * 100
    prod_head = prod.head(int(top_n))

    prod_names = prod_head["product_name"].tolist()
    revenue_vals = prod_head["revenue"].tolist()
    cumperc_vals = prod_head["cumperc"].tolist()

    fig = go.Figure()
    fig.add_trace(go.Bar(x=prod_names, y=revenue_vals, name="Revenue"))
    fig.add_trace(
        go.Scatter(
            x=prod_names,
            y=cumperc_vals,
            name="Cumulative %",
            yaxis="y2",
            mode="lines+markers",
        )
    )
    fig.update_layout(
        title="Pareto: Product Revenue vs Cumulative %",
        xaxis_title="Product",
        yaxis_title="Revenue",
        yaxis2=dict(title="Cumulative %", overlaying="y", side="right", range=[0, 110]),
        xaxis=dict(tickangle=-45),
        height=520,
        template="plotly_white",
    )
    return _to_json(fig)


@tool({"requires": ["product_name", "units", "revenue"], "returns": "scatter", "intent": ["units vs revenue", "bubble chart", "product performance"]})
def units_vs_revenue_agg(df: pd.DataFrame) -> dict:
    if (
        "product_name" not in df.columns
        or "revenue" not in df.columns
        or "units" not in df.columns
    ):
        return {"type": "error", "error": "Missing 'product_name','revenue' or 'units'"}
    agg = df.groupby("product_name", as_index=False).agg(
        {"units": "sum", "revenue": "sum"}
    )
    agg["aov"] = agg["revenue"] / agg["units"].replace(0, np.nan)
    fig = go.Figure(
        go.Scatter(
            x=agg["units"],
            y=agg["revenue"],
            mode="markers",
            marker={"size": (agg["revenue"] / agg["revenue"].max() * 40).clip(5, 60)},
            text=agg["product_name"],
        )
    )
    fig.update_layout(
        title="Units vs Revenue (bubble)",
        xaxis_title="Units",
        yaxis_title="Revenue",
        height=480,
        template="plotly_white",
    )
    return _to_json(fig)


# ---------- Geography ----------


@tool({"requires": ["region", "revenue"], "returns": "bar", "intent": ["revenue by region", "regional performance", "sales by region"]})
def revenue_by_region(df: pd.DataFrame) -> dict:
    if "region" not in df.columns or "revenue" not in df.columns:
        return {"type": "error", "error": "Missing 'region' or 'revenue'"}
    region_agg = (
        df.groupby("region", as_index=False)["revenue"]
        .sum()
        .sort_values("revenue", ascending=False)
    )

    regions = region_agg["region"].tolist()
    revenue_vals = region_agg["revenue"].tolist()
    revenue_labels = [f"${x:,.0f}" for x in revenue_vals]

    fig = go.Figure(
        go.Bar(
            x=regions,
            y=revenue_vals,
            text=revenue_labels,
            textposition="auto",
        )
    )
    fig.update_layout(
        title="Revenue by Region",
        xaxis_title="Region",
        yaxis_title="Revenue",
        height=420,
        template="plotly_white",
    )
    return _to_json(fig)


@tool({"requires": ["country", "revenue"], "returns": "bar", "intent": ["revenue by country", "country performance", "top countries"]})
def revenue_by_country_top(df: pd.DataFrame, top_n: int = 50) -> dict:
    if "country" not in df.columns or "revenue" not in df.columns:
        return {"type": "error", "error": "Missing 'country' or 'revenue'"}
    country_agg = (
        df.groupby("country", as_index=False)["revenue"]
        .sum()
        .sort_values("revenue", ascending=False)
        .head(int(top_n))
    )

    countries = country_agg["country"].tolist()
    revenue_vals = country_agg["revenue"].tolist()
    revenue_labels = [f"${x:,.0f}" for x in revenue_vals]

    fig = go.Figure(
        go.Bar(
            x=countries,
            y=revenue_vals,
            text=revenue_labels,
            textposition="auto",
        )
    )
    fig.update_layout(
        title="Top Countries by Revenue",
        xaxis_title="Country",
        yaxis_title="Revenue",
        xaxis=dict(tickangle=-45),
        height=420,
        template="plotly_white",
    )
    return _to_json(fig)


@tool({"requires": ["city", "revenue"], "returns": "bar", "intent": ["revenue by city", "city performance", "top cities"]})
def revenue_by_city_top(df: pd.DataFrame, top_n: int = 30) -> dict:
    if "city" not in df.columns or "revenue" not in df.columns:
        return {"type": "error", "error": "Missing 'city' or 'revenue'"}
    city_agg = (
        df.groupby("city", as_index=False)["revenue"]
        .sum()
        .sort_values("revenue", ascending=False)
        .head(int(top_n))
    )

    cities = city_agg["city"].tolist()
    revenue_vals = city_agg["revenue"].tolist()
    revenue_labels = [f"${x:,.0f}" for x in revenue_vals]

    fig = go.Figure(
        go.Bar(
            x=cities,
            y=revenue_vals,
            text=revenue_labels,
            textposition="auto",
        )
    )
    fig.update_layout(
        title="Top Cities by Revenue",
        xaxis_title="City",
        yaxis_title="Revenue",
        xaxis=dict(tickangle=-45),
        height=420,
        template="plotly_white",
    )
    return _to_json(fig)


# ---------- People & leaderboard ----------


@tool({"requires": ["salesperson", "revenue"], "returns": "bar", "intent": ["top salespeople", "sales rep leaderboard", "rep performance"]})
def top_salespeople(df: pd.DataFrame, top_k: int = 10) -> dict:
    if "salesperson" not in df.columns or "revenue" not in df.columns:
        return {"type": "error", "error": "Missing 'salesperson' or 'revenue'"}
    rep_agg = (
        df.groupby("salesperson", as_index=False)["revenue"]
        .sum()
        .sort_values("revenue", ascending=False)
        .head(int(top_k))
    )
    rep_agg = rep_agg.iloc[::-1]

    rep_names = rep_agg["salesperson"].tolist()
    revenue_vals = rep_agg["revenue"].tolist()
    revenue_labels = [f"${x:,.0f}" for x in revenue_vals]

    fig = go.Figure(
        go.Bar(
            x=revenue_vals,
            y=rep_names,
            orientation="h",
            text=revenue_labels,
            textposition="auto",
        )
    )
    fig.update_layout(
        title=f"Top {top_k} Salespeople by Revenue",
        xaxis_title="Revenue",
        yaxis_title="Salesperson",
        height=480,
        template="plotly_white",
    )
    return _to_json(fig)


@tool({"requires": ["salesperson", "revenue", "order_id"], "returns": "table", "intent": ["leaderboard table", "rep ranking", "sales summary table"]})
def leaderboard(df: pd.DataFrame) -> dict:
    if (
        "salesperson" not in df.columns
        or "revenue" not in df.columns
        or "order_id" not in df.columns
    ):
        return {
            "type": "error",
            "error": "Missing 'salesperson','revenue' or 'order_id'",
        }
    leaderboard_df = (
        df.groupby("salesperson", as_index=False)
        .agg(total_revenue=("revenue", "sum"), total_orders=("order_id", "nunique"))
        .sort_values("total_revenue", ascending=False)
    )
    leaderboard_df["total_revenue"] = leaderboard_df["total_revenue"].apply(
        lambda x: f"${x:,.2f}"
    )
    header = list(leaderboard_df.columns)
    cells = [leaderboard_df[c].tolist() for c in header]
    fig = go.Figure(
        data=[go.Table(header=dict(values=header), cells=dict(values=cells))]
    )
    fig.update_layout(title="Leaderboard", height=600)
    return _to_json(fig)


# ---------- Distribution & histogram ----------


@tool({"requires": ["sales_cycle_days"], "returns": "histogram", "intent": ["sales cycle distribution", "sales duration histogram", "deal length distribution"]})
def sales_cycle_histogram(df: pd.DataFrame, nbins: int = 40) -> dict:
    if "sales_cycle_days" not in df.columns:
        return {"type": "error", "error": "Missing 'sales_cycle_days'"}
    data = df["sales_cycle_days"].dropna().astype(float).values
    if len(data) == 0:
        return {"type": "error", "error": "No sales_cycle_days data"}
    fig = go.Figure(go.Histogram(x=data, nbinsx=nbins))
    fig.update_layout(
        title="Sales Cycle Days Distribution",
        xaxis_title="Days",
        yaxis_title="Count",
        height=420,
        template="plotly_white",
    )
    return _to_json(fig)


@tool({"requires": ["salesperson", "sales_cycle_days"], "returns": "table", "intent": ["average sales cycle by rep", "sales efficiency", "rep performance duration"]})
def avg_sales_cycle_by_rep(df: pd.DataFrame) -> dict:
    if "salesperson" not in df.columns or "sales_cycle_days" not in df.columns:
        return {"type": "error", "error": "Missing 'salesperson' or 'sales_cycle_days'"}
    avg_rep = (
        df.groupby("salesperson", as_index=False)["sales_cycle_days"]
        .mean()
        .rename(columns={"sales_cycle_days": "avg_sales_cycle_days"})
        .sort_values("avg_sales_cycle_days")
    )
    avg_rep["avg_sales_cycle_days"] = avg_rep["avg_sales_cycle_days"].apply(
        lambda x: f"{x:.2f}"
    )
    header = list(avg_rep.columns)
    cells = [avg_rep[c].tolist() for c in header]
    fig = go.Figure(
        data=[go.Table(header=dict(values=header), cells=dict(values=cells))]
    )
    fig.update_layout(title="Average Sales Cycle by Rep", height=600)
    return _to_json(fig)


# ---------- Pipeline & funnel ----------


@tool({"requires": ["stage", "opportunity_id"], "returns": "funnel", "intent": ["opportunity funnel", "pipeline funnel", "stage analysis"]})
def opportunity_funnel(df: pd.DataFrame) -> dict:
    if "stage" not in df.columns or "opportunity_id" not in df.columns:
        return {"type": "error", "error": "Missing 'stage' or 'opportunity_id'"}
    stage_counts = (
        df.groupby("stage")["opportunity_id"]
        .nunique()
        .reset_index()
        .sort_values("opportunity_id", ascending=False)
    )

    stages = stage_counts["stage"].tolist()
    counts = stage_counts["opportunity_id"].tolist()

    fig = go.Figure(
        go.Funnel(
            y=stages,
            x=counts,
            textinfo="value+percent initial",
        )
    )
    fig.update_layout(
        title="Opportunity Funnel",
        height=420,
        template="plotly_white",
    )
    return _to_json(fig)


@tool({"requires": ["opportunity_id", "stage", "lead_date", "close_date", "revenue"], "returns": "table", "intent": ["pipeline table", "opportunity table", "deal summary"]})
def pipeline_table(df: pd.DataFrame) -> dict:
    if "opportunity_id" not in df.columns:
        return {"type": "error", "error": "Missing 'opportunity_id'"}
    agg = df.groupby("opportunity_id").agg(
        stage=("stage", "last"),
        lead_date=("lead_date", "min"),
        close_date=("close_date", "min"),
        revenue=("revenue", "sum"),
    )
    agg = agg.reset_index()
    agg["revenue"] = agg["revenue"].apply(lambda x: f"${x:.2f}")
    header = list(agg.columns)
    cells = [agg[c].tolist() for c in header]
    fig = go.Figure(
        data=[go.Table(header=dict(values=header), cells=dict(values=cells))]
    )
    fig.update_layout(title="Pipeline Table", height=600)
    return _to_json(fig)