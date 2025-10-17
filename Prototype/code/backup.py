# streamlit_sales_dashboard.py
# ContinuumAi - Sales Analytics Dashboard (Streamlit)
# Single-file Streamlit app intended for use locally.

import io
from datetime import datetime, timedelta

import numpy as np
import pandas as pd
import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
import plotly.io as pio
from streamlit.components.v1 import html as st_html

# --------------------------- Plotly global template (light-blue theme) ---------------------------
# Global default so all charts pick the light-blue colorway and blue axis/font colors
PRIMARY_BLUE = "#5bc0ff"  # main line/bar color
SECONDARY = "#2a9df4"

continuum_template = go.layout.Template(
    layout=go.Layout(
        colorway=[PRIMARY_BLUE, SECONDARY, "#0b67c2", "#0077cc"],
        paper_bgcolor="white",
        plot_bgcolor="white",
        font=dict(color="#0b3b66"),
        xaxis=dict(color="#0b3b66", title_font=dict(color="#0b3b66")),
        yaxis=dict(color="#0b3b66", title_font=dict(color="#0b3b66")),
        legend=dict(font=dict(color="#0b3b66")),
    )
)

pio.templates["continuum"] = continuum_template
pio.templates.default = "continuum"
px.defaults.color_discrete_sequence = continuum_template.layout.colorway

# --------------------------- Helpers & Defaults ---------------------------
st.set_page_config(
    page_title="ContinuumAi", layout="wide", initial_sidebar_state="expanded"
)

# Inject minimal CSS for cards / background and header/footer
st.markdown(
    """
<style>

:root {
  --card-bg: #e6f7ff;
  --card-border: #cceeff;
  --header-bg: #f5f5f5; /* <-- light gray for header background */
  --footer-bg: #f5f5f5;
}

.app-header {
  background-color: var(--header-bg);
  border: 1px solid var(--card-border);
  padding: 12px 18px;
  border-radius: 10px;
  margin-bottom: 12px;

  display: flex;           /* layout as 3 columns: left spacer, centered title, right subtitle */
  align-items: center;
  gap: 12px;
}

/* left spacer—keeps title centered */
.header-left {
  width: 1px;              /* tiny spacer, can be 0 */
  flex: 0 0 1px;
}

/* title centered */
.app-title {
  flex: 1 1 auto;
  text-align: center;      /* center the H1 */
  margin: 0;
  font-size: 32px;
  font-weight: 800;
}

/* subtitle aligned to right */
.app-sub {
  flex: 0 0 auto;
  text-align: right;       /* right-align tagline */
  margin: 0;
  color: #333;
  font-style: italic;
}

body { background-color: white; }
.card { background-color: var(--card-bg); border: 1px solid var(--card-border); border-radius: 8px; padding: 14px; margin-bottom: 12px; }
.card-title { font-weight: 800; font-size: 16px; margin-bottom: 8px; }
.kpi-value { font-size: 22px; font-weight: 700; color: #111; }
.kpi-sub { font-size: 14px; color: #333; }
.footer { background-color: var(--footer-bg); border-top: 1px solid var(--card-border); padding: 16px; border-radius: 8px; text-align:center; margin-top:18px; font-weight:600; }

</style>
""",
    unsafe_allow_html=True,
)


@st.cache_data
def load_data_from_buffer(buffer) -> pd.DataFrame:
    df = pd.read_csv(buffer)
    return preprocess(df)


@st.cache_data
def preprocess(df: pd.DataFrame) -> pd.DataFrame:
    # Make a working copy
    df = df.copy()

    # Standardize column names (strip)
    df.columns = [c.strip() for c in df.columns]

    # Parse dates - try many common names
    date_cols = {
        "order_date": ["order_date", "order date", "date", "orderdate"],
        "first_purchase_date": [
            "first_purchase_date",
            "first purchase date",
            "first_purchase",
            "first_purchase_date",
        ],
        "lead_date": ["lead_date", "lead date", "leaddate"],
        "close_date": ["close_date", "close date", "closed_date", "closed date"],
    }
    for key, variants in date_cols.items():
        for v in variants:
            if v in df.columns:
                df[key] = pd.to_datetime(df[v], errors="coerce")
                break
        else:
            # create column with NaT if missing
            df[key] = pd.NaT

    # Numeric conversions
    for col in ["units", "revenue", "aov", "sales_cycle_days", "is_returning"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    # Fill missing aov: revenue / units where possible
    if "aov" not in df.columns or df["aov"].isna().all():
        if "revenue" in df.columns and "units" in df.columns:
            with np.errstate(divide="ignore", invalid="ignore"):
                df["aov"] = df["revenue"] / df["units"]
        else:
            df["aov"] = np.nan

    # sales_cycle_days: try compute if missing
    if "sales_cycle_days" not in df.columns or df["sales_cycle_days"].isna().all():
        if not df["lead_date"].isna().all() and not df["close_date"].isna().all():
            df["sales_cycle_days"] = (df["close_date"] - df["lead_date"]).dt.days
        else:
            df["sales_cycle_days"] = np.nan

    # is_returning fallback: treat first_purchase_date
    if "is_returning" not in df.columns or df["is_returning"].isna().all():
        if "first_purchase_date" in df.columns:
            # if first_purchase_date < order_date -> returning
            df["is_returning"] = np.where(
                (~df["first_purchase_date"].isna())
                & (~df["order_date"].isna())
                & (df["first_purchase_date"] < df["order_date"]),
                1,
                0,
            )
        else:
            df["is_returning"] = 0

    # Standardize stage column to string
    if "stage" in df.columns:
        df["stage"] = df["stage"].astype(str)

    # Ensure IDs are strings
    for idcol in ["customer_id", "order_id", "product_id", "opportunity_id"]:
        if idcol in df.columns:
            df[idcol] = df[idcol].astype(str)

    # Fill missing categorical columns
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

    # Order date fallback: if totally missing, create synthetic index
    if df["order_date"].isna().all():
        df["order_date"] = pd.to_datetime("today") - pd.to_timedelta(
            np.arange(len(df)), unit="d"
        )

    # Create additional columns useful for grouping
    df["order_date_only"] = df["order_date"].dt.date
    df["order_month"] = df["order_date"].dt.to_period("M").dt.to_timestamp()
    df["order_week"] = df["order_date"].dt.to_period("W").dt.start_time

    return df


# --------------------------- UI: Header & Upload ---------------------------
# Styled header with border/background
# st.markdown("<div class='app-header'><h1>ContinuumAi</h1><div class='app-sub'>Your Personal Business Analyst for Sales.</div></div>", unsafe_allow_html=True)
# st.markdown(
#     "<div class='app-header'><h1>ContinuumAi</h1>"
#     "<div class='app-sub'><em>Your Personal Business Analyst for Sales.</em></div>"
#     "</div>",
#     unsafe_allow_html=True,
# )

st.markdown(
    "<div class='app-header'>"
    "  <div class='header-left'></div>"
    "  <h1 class='app-title'>ContinuumAi</h1>"
    # "  <div class='app-sub'>Your Personal Business Analyst for Sales.</div>"
    "</div>",
    unsafe_allow_html=True
)

uploaded_file = st.file_uploader("Upload CSV File to Get Started...", type=["csv"])

if uploaded_file is None:
    # st.info("Upload your sales CSV (schema in the prompt). You can also drag & drop here.")
    st.stop()
st.markdown("---")
# Load dataset
with st.spinner("Loading and preprocessing dataset..."):
    try:
        df = load_data_from_buffer(uploaded_file)
    except Exception as e:
        st.error(f"Couldn't read file: {e}")
        st.stop()

# --------------------------- Sidebar Filters ---------------------------
# Keep only reset button and download in sidebar to reduce clutter
st.sidebar.header("Controls & Data")
if st.sidebar.button("Reset Filters"):
    st.experimental_rerun()

# Provide download in sidebar as well
# (We'll compute filtered CSV later after filters are applied)

min_date = (
    df["order_date"].min().date()
    if not df["order_date"].isna().all()
    else datetime.today().date()
)
max_date = (
    df["order_date"].max().date()
    if not df["order_date"].isna().all()
    else datetime.today().date()
)

date_range = st.sidebar.date_input(
    "Order Date Range",
    value=(min_date, max_date),
    min_value=min_date,
    max_value=max_date,
)

# Defensive: ensure tuple
if isinstance(date_range, (list, tuple)) and len(date_range) == 2:
    date_from, date_to = date_range
else:
    date_from, date_to = min_date, max_date

# Multiselects in sidebar remain
regions = (
    ["All"] + sorted(df["region"].dropna().unique().tolist())
    if "region" in df.columns
    else ["All"]
)
selected_regions = st.sidebar.multiselect("Region", options=regions, default=["All"])

sales_reps = (
    ["All"] + sorted(df["salesperson"].dropna().unique().tolist())
    if "salesperson" in df.columns
    else ["All"]
)
selected_reps = st.sidebar.multiselect(
    "Salesperson", options=sales_reps, default=["All"]
)

categories = (
    ["All"] + sorted(df["category"].dropna().unique().tolist())
    if "category" in df.columns
    else ["All"]
)
selected_categories = st.sidebar.multiselect(
    "Product Category", options=categories, default=["All"]
)

# Apply filters
df_filtered = df.copy()

# Date filter
df_filtered = df_filtered[
    (df_filtered["order_date"].dt.date >= date_from)
    & (df_filtered["order_date"].dt.date <= date_to)
]

# Region filter
if "All" not in selected_regions and len(selected_regions) > 0:
    df_filtered = df_filtered[df_filtered["region"].isin(selected_regions)]

# Sales rep filter
if "All" not in selected_reps and len(selected_reps) > 0:
    df_filtered = df_filtered[df_filtered["salesperson"].isin(selected_reps)]

# Category filter
if "All" not in selected_categories and len(selected_categories) > 0:
    df_filtered = df_filtered[df_filtered["category"].isin(selected_categories)]

# --------------------------- KPIs ---------------------------
# Some safe aggregations
total_revenue = (
    float(df_filtered["revenue"].sum()) if "revenue" in df_filtered.columns else 0.0
)
total_orders = (
    df_filtered["order_id"].nunique()
    if "order_id" in df_filtered.columns
    else len(df_filtered)
)
avg_aov = (
    float(df_filtered["aov"].mean())
    if "aov" in df_filtered.columns
    else (total_revenue / total_orders if total_orders else 0)
)

# Conversion rate: unique opportunity that closed won / unique opportunities
if "opportunity_id" in df_filtered.columns and "stage" in df_filtered.columns:
    total_opps = df_filtered["opportunity_id"].nunique()
    closed_opp_mask = df_filtered["stage"].str.lower().str.contains("closed|won")
    closed_opps = df_filtered[closed_opp_mask]["opportunity_id"].nunique()
    conversion_rate = (closed_opps / total_opps) if total_opps else np.nan
else:
    conversion_rate = np.nan

# New vs returning customers
if "customer_id" in df_filtered.columns:
    cust_counts = df_filtered.drop_duplicates(subset=["customer_id"])
    returning_count = (
        cust_counts["is_returning"].sum()
        if "is_returning" in cust_counts.columns
        else 0
    )
    new_count = len(cust_counts) - returning_count
else:
    new_count, returning_count = 0, 0
st.markdown(
    "<h2 style='text-align:left; color:#000000;'>Quick Insights</h2>",
    unsafe_allow_html=True
)

# Render KPI cards using HTML so we can style them consistently
k1, k2, k3, k4 = st.columns(4)
with k1:
    st.markdown(
        f"<div class='card'><div class='card-title'>Total Revenue</div><div class='kpi-value'>${total_revenue:,.2f}</div></div>",
        unsafe_allow_html=True,
    )
with k2:
    st.markdown(
        f"<div class='card'><div class='card-title'>Total Orders</div><div class='kpi-value'>{int(total_orders):,}</div></div>",
        unsafe_allow_html=True,
    )
with k3:
    st.markdown(
        f"<div class='card'><div class='card-title'>Average Order Value (AOV)</div><div class='kpi-value'>${avg_aov:,.2f}</div></div>",
        unsafe_allow_html=True,
    )
with k4:
    conv_display = f"{conversion_rate:.1%}" if not np.isnan(conversion_rate) else "N/A"
    st.markdown(
        f"<div class='card'><div class='card-title'>Conversion Rate</div><div class='kpi-value'>{conv_display}</div></div>",
        unsafe_allow_html=True,
    )

# New vs Returning small cards
# st.markdown("---")
coln, colr = st.columns(2)
with coln:
    st.markdown(
        f"<div class='card'><div class='card-title'>New customers (unique)</div><div class='kpi-value'>{int(new_count):,}</div></div>",
        unsafe_allow_html=True,
    )
with colr:
    st.markdown(
        f"<div class='card'><div class='card-title'>Returning customers (unique)</div><div class='kpi-value'>{int(returning_count):,}</div></div>",
        unsafe_allow_html=True,
    )

# Download filtered dataset
csv_buffer = df_filtered.to_csv(index=False).encode("utf-8")
st.sidebar.download_button(
    label="Download Filtered Dataset (CSV)",
    data=csv_buffer,
    file_name="filtered_sales.csv",
    mime="text/csv",
)

# --------------------------- Tabs for Visualizations ---------------------------
tabs = st.tabs(
    ["Time Trends", "Products", "Geography", "People", "Conversion / Pipeline"]
)


# Helper to render plotly figure inside a styled card
def render_fig_in_card(title: str, fig, height: int = 420):
    fig_html = fig.to_html(full_html=False, include_plotlyjs="cdn")
    wrapper = f"<div class='card'><div class='card-title'>{title}</div>{fig_html}</div>"
    st_html(wrapper, height=height)


# --------------------------- Tab 1: Time Trends (all displayed) ---------------------------
with tabs[0]:
    st.header("Time Trends")
    # controls for this tab placed next to charts
    ctrl_col, _ = st.columns([1, 2])
    with ctrl_col:
        resample_option = st.selectbox(
            "Aggregation",
            options=["D", "W", "M"],
            index=2,
            help="D=day, W=week, M=month",
        )
        rolling_window = st.number_input(
            "Rolling window (periods)", min_value=1, max_value=90, value=3
        )

    # Sales over time
    st.subheader("Sales Over Time")
    grp = (
        df_filtered.set_index("order_date")
        .resample(resample_option)["revenue"]
        .sum()
        .reset_index()
    )
    grp["rolling"] = grp["revenue"].rolling(rolling_window).mean()
    fig = go.Figure()
    fig.add_trace(
        go.Scatter(x=grp["order_date"], y=grp["revenue"], mode="lines", name="Revenue")
    )
    fig.add_trace(
        go.Scatter(
            x=grp["order_date"],
            y=grp["rolling"],
            mode="lines",
            name=f"{rolling_window}-period rolling",
        )
    )
    fig.update_layout(yaxis_title="Revenue", xaxis_title="Date", height=450)
    render_fig_in_card("Sales Over Time", fig, height=450)

    # AOV over time + boxplot
    st.subheader("AOV Over Time")
    if "aov" in df_filtered.columns:
        aov_grp = (
            df_filtered.set_index("order_date")
            .resample(resample_option)["aov"]
            .mean()
            .reset_index()
        )
        fig = px.line(aov_grp, x="order_date", y="aov", title="AOV Over Time")
        render_fig_in_card("AOV Over Time", fig, height=420)

        # boxplot
        st.subheader("AOV Distribution (by region)")
        if "region" in df_filtered.columns:
            fig2 = px.box(
                df_filtered, x="region", y="aov", title="AOV Distribution by region"
            )
            render_fig_in_card("AOV Distribution by region", fig2, height=420)
    else:
        st.info("AOV not available in dataset.")

    # Repeat vs new over time
    st.subheader("Repeat vs New customers Over Time")
    tmp = df_filtered.copy()
    tmp["is_returning"] = tmp["is_returning"].fillna(0).astype(int)
    grp2 = (
        tmp.groupby(
            [pd.Grouper(key="order_date", freq=resample_option), "is_returning"]
        )["customer_id"]
        .nunique()
        .reset_index()
    )
    grp2["order_date"] = grp2["order_date"].dt.date
    fig3 = px.area(
        grp2,
        x="order_date",
        y="customer_id",
        color="is_returning",
        labels={"customer_id": "unique customers", "is_returning": "is_returning"},
    )
    render_fig_in_card("Repeat vs New customers Over Time", fig3, height=420)

# --------------------------- Tab 2: Products (all displayed) ---------------------------
with tabs[1]:
    st.header("Products")
    # place Top N control next to product visuals
    ctrl_col, _ = st.columns([1, 3])
    with ctrl_col:
        top_n = st.number_input("Top N Products", min_value=5, max_value=200, value=20)

    # Sales by product
    st.subheader("Sales by Product")
    prod = (
        df_filtered.groupby("product_name", as_index=False)["revenue"]
        .sum()
        .sort_values("revenue", ascending=False)
    )
    prod_top = prod.head(top_n)
    fig = px.bar(
        prod_top,
        x="revenue",
        y="product_name",
        orientation="h",
        title=f"Top {top_n} Products by Revenue",
    )
    render_fig_in_card(f"Top {top_n} Products by Revenue", fig, height=480)

    # Pareto
    prod["cumperc"] = prod["revenue"].cumsum() / prod["revenue"].sum() * 100
    fig2 = go.Figure()
    fig2.add_trace(
        go.Bar(
            x=prod["product_name"].head(50), y=prod["revenue"].head(50), name="Revenue"
        )
    )
    fig2.add_trace(
        go.Scatter(
            x=prod["product_name"].head(50),
            y=prod["cumperc"].head(50),
            name="Cumulative %",
            yaxis="y2",
        )
    )
    fig2.update_layout(
        yaxis2=dict(overlaying="y", side="right", range=[0, 110]),
        xaxis_tickangle=-45,
        height=500,
    )
    render_fig_in_card("Pareto: Product Revenue vs Cumulative", fig2, height=500)

    # Units vs Revenue
    st.subheader("Units vs Revenue")
    if "units" in df_filtered.columns:
        agg = df_filtered.groupby("product_name", as_index=False).agg(
            {"units": "sum", "revenue": "sum"}
        )
        agg["aov"] = agg["revenue"] / agg["units"].replace(0, np.nan)
        fig3 = px.scatter(
            agg,
            x="units",
            y="revenue",
            size="revenue",
            hover_name="product_name",
            title="Units vs Revenue (bubble)",
        )
        render_fig_in_card("Units vs Revenue (bubble)", fig3, height=480)
    else:
        st.info("units column not available in dataset.")

    # Category breakdown
    st.subheader("Revenue by Category")
    cat = (
        df_filtered.groupby("category", as_index=False)["revenue"]
        .sum()
        .sort_values("revenue", ascending=False)
    )
    fig4 = px.treemap(
        cat, path=["category"], values="revenue", title="Revenue by Category (treemap)"
    )
    render_fig_in_card("Revenue by Category", fig4, height=480)

# --------------------------- Tab 3: Geography (all displayed) ---------------------------
with tabs[2]:
    st.header("Geography")

    # Region / country / city bars
    st.subheader("Revenue by Region / Country / City")
    if "region" in df_filtered.columns:
        region_agg = (
            df_filtered.groupby("region", as_index=False)["revenue"]
            .sum()
            .sort_values("revenue", ascending=False)
        )
        fig = px.bar(region_agg, x="region", y="revenue", title="Revenue by Region")
        render_fig_in_card("Revenue by Region", fig, height=420)

    if "country" in df_filtered.columns:
        country_agg = (
            df_filtered.groupby("country", as_index=False)["revenue"]
            .sum()
            .sort_values("revenue", ascending=False)
        )
        fig2 = px.bar(
            country_agg.head(50),
            x="country",
            y="revenue",
            title="Top Countries by Revenue",
        )
        render_fig_in_card("Top Countries by Revenue", fig2, height=420)

    if "city" in df_filtered.columns:
        city_agg = (
            df_filtered.groupby("city", as_index=False)["revenue"]
            .sum()
            .sort_values("revenue", ascending=False)
            .head(30)
        )
        fig3 = px.bar(city_agg, x="city", y="revenue", title="Top Cities by Revenue")
        render_fig_in_card("Top Cities by Revenue", fig3, height=420)

    # Pie
    if "region" in df_filtered.columns:
        region_agg = (
            df_filtered.groupby("region", as_index=False)["revenue"]
            .sum()
            .sort_values("revenue", ascending=False)
        )
        figp = px.pie(
            region_agg,
            values="revenue",
            names="region",
            title="Revenue Share by Region",
        )
        render_fig_in_card("Revenue Share by Region", figp, height=420)

    # Choropleth
    if "country" in df_filtered.columns:
        country_agg = df_filtered.groupby("country", as_index=False)["revenue"].sum()
        try:
            fgc = px.choropleth(
                country_agg,
                locations="country",
                locationmode="country names",
                color="revenue",
                title="Revenue by Country",
            )
            render_fig_in_card("Choropleth: Revenue by Country", fgc, height=520)
        except Exception as e:
            st.error(
                "Choropleth failed, maybe country names are non-standard. Error: "
                + str(e)
            )

# --------------------------- Tab 4: People (all displayed) ---------------------------
with tabs[3]:
    st.header("People (Sales Team)")
    # place Top K control next to people visuals
    ctrl_col, _ = st.columns([1, 3])
    with ctrl_col:
        top_k_rep = st.number_input(
            "Top K reps to show", min_value=3, max_value=100, value=10
        )

    # Sales by salesperson
    st.subheader("Revenue by Salesperson")
    if "salesperson" in df_filtered.columns:
        rep_agg = (
            df_filtered.groupby("salesperson", as_index=False)["revenue"]
            .sum()
            .sort_values("revenue", ascending=False)
            .head(top_k_rep)
        )
        fig = px.bar(
            rep_agg,
            x="revenue",
            y="salesperson",
            orientation="h",
            title="Top Salespeople by Revenue",
        )
        render_fig_in_card("Top Salespeople by Revenue", fig, height=480)

        st.markdown(
            "<div class='card'><div class='card-title'>Leaderboard</div></div>",
            unsafe_allow_html=True,
        )
        leaderboard = df_filtered.groupby("salesperson", as_index=False).agg(
            total_revenue=("revenue", "sum"), total_orders=("order_id", "nunique")
        )
        leaderboard = leaderboard.sort_values(
            "total_revenue", ascending=False
        ).reset_index(drop=True)
        st.dataframe(leaderboard.head(50))
    else:
        st.info("No salesperson column in dataset")

    # Sales cycle duration
    st.subheader("Sales Cycle Duration")
    if "sales_cycle_days" in df_filtered.columns:
        fig = px.histogram(
            df_filtered,
            x="sales_cycle_days",
            nbins=40,
            title="Sales Cycle Days Distribution",
        )
        render_fig_in_card("Sales Cycle Days Distribution", fig, height=420)

        if "salesperson" in df_filtered.columns:
            avg_rep = (
                df_filtered.groupby("salesperson", as_index=False)["sales_cycle_days"]
                .mean()
                .sort_values("sales_cycle_days")
            )
            st.markdown(
                "<div class='card'><div class='card-title'>Average Sales Cycle by Rep</div></div>",
                unsafe_allow_html=True,
            )
            st.dataframe(avg_rep.head(50))
    else:
        st.info("sales_cycle_days not available in dataset")

# --------------------------- Tab 5: Conversion / Pipeline (all displayed) ---------------------------
with tabs[4]:
    st.header("Conversion & Pipeline")

    # Funnel
    st.subheader("Conversion Funnel")
    if "stage" in df_filtered.columns and "opportunity_id" in df_filtered.columns:
        stage_counts = (
            df_filtered.groupby("stage")["opportunity_id"].nunique().reset_index()
        )
        stage_counts = stage_counts.sort_values("opportunity_id", ascending=False)
        fig = go.Figure(
            go.Funnel(y=stage_counts["stage"], x=stage_counts["opportunity_id"])
        )
        fig.update_layout(title="Opportunity Funnel")
        render_fig_in_card("Opportunity Funnel", fig, height=420)
    else:
        st.info("stage or opportunity_id not available")

    # Pipeline table
    st.subheader("Pipeline Table")
    if "opportunity_id" in df_filtered.columns:
        opps = (
            df_filtered.groupby("opportunity_id")
            .agg(
                stage=("stage", "last"),
                lead_date=("lead_date", "min"),
                close_date=("close_date", "min"),
                revenue=("revenue", "sum"),
            )
            .reset_index()
        )
        st.markdown(
            "<div class='card'><div class='card-title'>Pipeline table</div></div>",
            unsafe_allow_html=True,
        )
        st.dataframe(opps.head(200))
    else:
        st.info("opportunity_id not found")

# --------------------------- Footer / Tips ---------------------------
st.markdown(
    "<div class='footer'>ContinuumAi - The Future of Business Intelligence</div>",
    unsafe_allow_html=True,
)

# End of app


