# app.py
from __future__ import annotations

import io
import json
import os
import hashlib
import binascii
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Optional, Tuple

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import plotly.io as pio
import streamlit as st
from streamlit.components.v1 import html as st_html

# -----------------------
# Config / Users storage
# -----------------------
USERS_FILE = Path("users.json")

# -----------------------
# Auth helper functions
# -----------------------

# put near other helper functions (top of file)
def safe_rerun():
    try:
        # recent stable API
        st.rerun()
        return
    except Exception:
        pass

    try:
        # older / experimental API
        safe_rerun()
        return
    except Exception:
        pass

    # last resort: try raising Streamlit's internal RerunException (may work)
    try:
        from streamlit.runtime.state import RerunException  # type: ignore
        raise RerunException()
    except Exception:
        # best-effort fallback: set current page (no-op) and stop execution
        st.session_state.page = st.session_state.get("page", "home")
        st.stop()


def _ensure_users_file():
    if not USERS_FILE.exists():
        save_users({})

def load_users():
    _ensure_users_file()
    try:
        with open(USERS_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data if isinstance(data, dict) else {}
    except Exception:
        return {}

def save_users(users_dict):
    USERS_FILE.parent.mkdir(parents=True, exist_ok=True)
    temp_fd, temp_path = tempfile.mkstemp(prefix="users_", suffix=".json", dir=".")
    with os.fdopen(temp_fd, "w", encoding="utf-8") as tmpf:
        json.dump(users_dict, tmpf, indent=2)
    os.replace(temp_path, USERS_FILE)

def hash_password(password: str, salt: str) -> str:
    h = hashlib.sha256()
    h.update((salt + password).encode("utf-8"))
    return h.hexdigest()

def gen_salt(n_bytes: int = 16) -> str:
    return binascii.hexlify(os.urandom(n_bytes)).decode("ascii")

def create_user(username: str, password: str) -> tuple[bool, str]:
    username = username.strip()
    if not username:
        return False, "Username cannot be empty."
    if len(password) < 6:
        return False, "Password must be at least 6 characters."

    users = load_users()
    if username in users:
        return False, f"Username '{username}' already exists."

    salt = gen_salt()
    users[username] = {
        "salt": salt,
        "password_hash": hash_password(password, salt),
        "created_at": datetime.utcnow().isoformat() + "Z",
    }
    save_users(users)
    return True, "User created successfully."

def verify_user(username: str, password: str) -> tuple[bool, str]:
    users = load_users()
    if username not in users:
        return False, "Invalid username or password."
    user = users[username]
    if hash_password(password, user["salt"]) == user["password_hash"]:
        return True, "Login successful."
    return False, "Invalid username or password."

# -----------------------
# Session state defaults
# -----------------------
if "page" not in st.session_state:
    st.session_state.page = "home"
if "user" not in st.session_state:
    st.session_state.user = None
if "message" not in st.session_state:
    st.session_state.message = ""

# -----------------------
# Navigation helpers
# -----------------------
def go_to(page: str):
    st.session_state.page = page
    # ensure UI updates immediately
    safe_rerun()

def logout():
    st.session_state.user = None
    st.session_state.page = "home"
    st.session_state.message = "You have been signed out."
    safe_rerun()

# ---------------------------
# Dashboard (main app) helpers
# ---------------------------
PRIMARY_BLUE = "#5bc0ff"
SECONDARY = "#2a9df4"

def _register_plotly_template() -> None:
    template = go.layout.Template(
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
    pio.templates["continuum"] = template
    pio.templates.default = "continuum"
    px.defaults.color_discrete_sequence = template.layout.colorway

CSS = """
:root{--card-bg:#e6f7ff;--card-border:#cceeff;--header-bg:#f5f5f5;--footer-bg:#f5f5f5}
.app-header{background-color:var(--header-bg);border:1px solid var(--card-border);padding:12px 18px;border-radius:10px;margin-bottom:12px;display:flex;align-items:center;gap:12px}
.header-left{width:1px;flex:0 0 1px}
.app-title{flex:1 1 auto;text-align:center;margin:0;font-size:32px;font-weight:800}
.app-sub{flex:0 0 auto;text-align:right;margin:0;color:#333;font-style:italic}
.card{background-color:var(--card-bg);border:1px solid var(--card-border);border-radius:8px;padding:14px;margin-bottom:12px}
.card-title{font-weight:800;font-size:16px;margin-bottom:8px}
.kpi-value{font-size:22px;font-weight:700;color:#111}
.footer{background-color:var(--footer-bg);border-top:1px solid var(--card-border);padding:16px;border-radius:8px;text-align:center;margin-top:18px;font-weight:600}
"""

@st.cache_data
def load_data_from_buffer(buffer: io.BytesIO) -> pd.DataFrame:
    df = pd.read_csv(buffer)
    return preprocess(df)

@st.cache_data
def preprocess(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df.columns = [c.strip() for c in df.columns]

    date_mapping = {
        "order_date": ["order_date", "order date", "date", "orderdate"],
        "first_purchase_date": ["first_purchase_date", "first purchase date", "first_purchase"],
        "lead_date": ["lead_date", "lead date", "leaddate"],
        "close_date": ["close_date", "close date", "closed_date"],
    }
    for canon, variants in date_mapping.items():
        found = None
        for v in variants:
            if v in df.columns:
                found = v
                break
        df[canon] = pd.to_datetime(df[found], errors="coerce") if found else pd.NaT

    for col in ["units", "revenue", "aov", "sales_cycle_days", "is_returning"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    if "aov" not in df.columns or df["aov"].isna().all():
        if "revenue" in df.columns and "units" in df.columns:
            with np.errstate(divide="ignore", invalid="ignore"):
                df["aov"] = df["revenue"] / df["units"]
        else:
            df["aov"] = np.nan

    if "sales_cycle_days" not in df.columns or df["sales_cycle_days"].isna().all():
        if (not df["lead_date"].isna().all()) and (not df["close_date"].isna().all()):
            df["sales_cycle_days"] = (df["close_date"] - df["lead_date"]).dt.days
        else:
            df["sales_cycle_days"] = np.nan

    if "is_returning" not in df.columns or df["is_returning"].isna().all():
        if "first_purchase_date" in df.columns:
            df["is_returning"] = np.where(
                (~df["first_purchase_date"].isna())
                & (~df["order_date"].isna())
                & (df["first_purchase_date"] < df["order_date"]),
                1,
                0,
            )
        else:
            df["is_returning"] = 0

    for idcol in ["customer_id", "order_id", "product_id", "opportunity_id"]:
        if idcol in df.columns:
            df[idcol] = df[idcol].astype(str)

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

    if df["order_date"].isna().all():
        df["order_date"] = pd.to_datetime("today") - pd.to_timedelta(np.arange(len(df)), unit="d")

    df["order_date_only"] = df["order_date"].dt.date
    df["order_month"] = df["order_date"].dt.to_period("M").dt.to_timestamp()
    df["order_week"] = df["order_date"].dt.to_period("W").dt.start_time

    return df

def apply_filters(
    df: pd.DataFrame,
    date_from: datetime.date,
    date_to: datetime.date,
    regions: Optional[list] = None,
    reps: Optional[list] = None,
    categories: Optional[list] = None,
) -> pd.DataFrame:
    df2 = df.copy()
    df2 = df2[(df2["order_date"].dt.date >= date_from) & (df2["order_date"].dt.date <= date_to)]

    if regions and "All" not in regions:
        df2 = df2[df2["region"].isin(regions)]
    if reps and "All" not in reps:
        df2 = df2[df2["salesperson"].isin(reps)]
    if categories and "All" not in categories:
        df2 = df2[df2["category"].isin(categories)]

    return df2

def compute_kpis(df: pd.DataFrame) -> dict:
    total_revenue = float(df["revenue"].sum()) if "revenue" in df.columns else 0.0
    total_orders = df["order_id"].nunique() if "order_id" in df.columns else len(df)
    avg_aov = float(df["aov"].mean()) if "aov" in df.columns else (total_revenue / total_orders if total_orders else 0)

    conversion_rate = np.nan
    if "opportunity_id" in df.columns and "stage" in df.columns:
        total_opps = df["opportunity_id"].nunique()
        closed_opp_mask = df["stage"].str.lower().str.contains("closed|won", na=False)
        closed_opps = df[closed_opp_mask]["opportunity_id"].nunique()
        conversion_rate = (closed_opps / total_opps) if total_opps else np.nan

    new_count = returning_count = 0
    if "customer_id" in df.columns:
        cust_counts = df.drop_duplicates(subset=["customer_id"])
        returning_count = int(cust_counts["is_returning"].sum()) if "is_returning" in cust_counts.columns else 0
        new_count = len(cust_counts) - returning_count

    return {
        "total_revenue": total_revenue,
        "total_orders": int(total_orders),
        "avg_aov": avg_aov,
        "conversion_rate": conversion_rate,
        "new_count": int(new_count),
        "returning_count": int(returning_count),
    }

def render_kpi_card(title: str, value: str) -> None:
    st.markdown(f"<div class='card'><div class='card-title'>{title}</div><div class='kpi-value'>{value}</div></div>", unsafe_allow_html=True)

def render_fig_in_card(title: str, fig, height: int = 420) -> None:
    fig_html = fig.to_html(full_html=False, include_plotlyjs="cdn")
    wrapper = f"<div class='card'><div class='card-title'>{title}</div>{fig_html}</div>"
    st_html(wrapper, height=height)

# ---------------------------
# Combined App pages
# ---------------------------

# single set_page_config (only call once)
st.set_page_config(page_title="ContinuumAi", page_icon="⚡", layout="wide", initial_sidebar_state="expanded")

# top header (shared across pages)

st.markdown(f"<style>{CSS}</style>", unsafe_allow_html=True)

if st.session_state.page == "home":
    
    st.markdown("<h1 style='text-align:center'>ContinuumAi</h1>", unsafe_allow_html=True)
    
    st.markdown(
        "<h4 style='text-align: center;'>The Future of Business Intelligence</h4>",
        unsafe_allow_html=True,
    )
    st.write("---")

    # Center buttons using columns
    col1, col2, col3 = st.columns([1, 1, 1])
    with col2:
        st.write("")  # small spacing
        if st.button("Sign In", use_container_width=True):
            go_to("signin")
        if st.button("Sign Up", use_container_width=True):
            go_to("signup")

    st.write("")
    st.info("Sign in to access the protected Sales Dashboard.")
    if st.session_state.message:
        st.success(st.session_state.message)
        st.session_state.message = ""

# -----------------------
# Sign Up
# -----------------------
elif st.session_state.page == "signup":
    # st.write("---")
    st.subheader("Sign Up")
    with st.form("signup_form"):
        username = st.text_input("Username")
        password = st.text_input("Password", type="password")
        confirm = st.text_input("Confirm password", type="password")
        submitted = st.form_submit_button("Create account")
        if submitted:
            if password != confirm:
                st.error("Passwords do not match.")
            else:
                ok, msg = create_user(username, password)
                if ok:
                    st.success(msg)
                    st.session_state.user = username
                    st.session_state.message = f"Welcome, {username}!"
                    # go to dashboard (main app) instead of a static page
                    go_to("dashboard")
                else:
                    st.error(msg)
    if st.button("Back to Home"):
        go_to("home")

# -----------------------
# Sign In
# -----------------------
elif st.session_state.page == "signin":
    # st.write("---")
    st.subheader("Sign In")
    with st.form("signin_form"):
        username = st.text_input("Username")
        password = st.text_input("Password", type="password")
        submitted = st.form_submit_button("Sign in")
        if submitted:
            ok, msg = verify_user(username, password)
            if ok:
                st.success("Signed in successfully!")
                st.session_state.user = username
                st.session_state.message = f"Welcome back, {username}!"
                go_to("dashboard")
            else:
                st.error(msg)
    if st.button("Back to Home"):
        go_to("home")

# -----------------------
# Dashboard (protected)
# -----------------------
elif st.session_state.page == "dashboard":
    # if not signed in, prevent viewing and redirect to signin
    if st.session_state.user is None:
        st.warning("You must be signed in to view the dashboard.")
        if st.button("Go to Sign In"):
            go_to("signin")
        st.stop()

    # Dashboard header with sign out
    st.markdown("""
    <div class='app-header'>
      <div class='header-left'></div>
      <h1 class='app-title'>ContinuumAi - Sales Dashboard</h1>
    </div>
    """.format(st.session_state.user), unsafe_allow_html=True)

    # Sign out button
    right_col, _ = st.columns([1, 4])
    with right_col:
        if st.button("Sign Out"):
            logout()

    # Register plotly colors/templates
    _register_plotly_template()

    # File uploader and main dashboard flow (copied/adapted from your app)
    uploaded_file = st.file_uploader("Upload CSV File to Get Started...", type=["csv"])
    if uploaded_file is None:
        st.info("Upload your sales CSV (common schema: order_date, revenue, order_id, product_name, customer_id, etc.)")
        st.stop()

    with st.spinner("Loading and preprocessing dataset..."):
        try:
            df = load_data_from_buffer(uploaded_file)
        except Exception as exc:
            st.error(f"Couldn't read file: {exc}")
            st.stop()

    # Sidebar controls
    st.sidebar.header("Controls & Data")
    if st.sidebar.button("Reset Filters"):
        safe_rerun()

    min_date = df["order_date"].min().date() if not df["order_date"].isna().all() else datetime.today().date()
    max_date = df["order_date"].max().date() if not df["order_date"].isna().all() else datetime.today().date()

    date_range = st.sidebar.date_input("Order Date Range", value=(min_date, max_date), min_value=min_date, max_value=max_date)
    if isinstance(date_range, (list, tuple)) and len(date_range) == 2:
        date_from, date_to = date_range
    else:
        date_from, date_to = min_date, max_date

    def _options_with_all(col: str) -> list:
        return ["All"] + sorted(df[col].dropna().unique().tolist()) if col in df.columns else ["All"]

    selected_regions = st.sidebar.multiselect("Region", options=_options_with_all("region"), default=["All"]) 
    selected_reps = st.sidebar.multiselect("Salesperson", options=_options_with_all("salesperson"), default=["All"]) 
    selected_categories = st.sidebar.multiselect("Product Category", options=_options_with_all("category"), default=["All"]) 

    df_filtered = apply_filters(df, date_from, date_to, selected_regions, selected_reps, selected_categories)

    csv_buffer = df_filtered.to_csv(index=False).encode("utf-8")
    st.sidebar.download_button(label="Download Filtered Dataset (CSV)", data=csv_buffer, file_name="filtered_sales.csv", mime="text/csv")

    # KPIs
    kpis = compute_kpis(df_filtered)
    st.markdown("---")
    st.markdown("<h2 style='text-align:left; color:#000000;'>Quick Insights</h2>", unsafe_allow_html=True)

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        render_kpi_card("Total Revenue", f"${kpis['total_revenue']:,.2f}")
    with c2:
        render_kpi_card("Total Orders", f"{kpis['total_orders']:,}")
    with c3:
        render_kpi_card("Average Order Value (AOV)", f"${kpis['avg_aov']:,.2f}")
    with c4:
        conv_display = f"{kpis['conversion_rate']:.1%}" if not np.isnan(kpis['conversion_rate']) else "N/A"
        render_kpi_card("Conversion Rate", conv_display)

    ncol, rcol = st.columns(2)
    with ncol:
        render_kpi_card("New customers (unique)", f"{kpis['new_count']:,}")
    with rcol:
        render_kpi_card("Returning customers (unique)", f"{kpis['returning_count']:,}")

    tabs = st.tabs(["Time Trends", "Products", "Geography", "People", "Conversion / Pipeline"])

    # Time Trends
    with tabs[0]:
        st.header("Time Trends")
        control_col, _ = st.columns([1, 2])
        with control_col:
            resample_option = st.selectbox("Aggregation", options=["D", "W", "M"], index=2, help="D=day, W=week, M=month")
            rolling_window = st.number_input("Rolling window (periods)", min_value=1, max_value=90, value=3)

        st.subheader("Sales Over Time")
        grp = df_filtered.set_index("order_date").resample(resample_option)["revenue"].sum().reset_index()
        grp["rolling"] = grp["revenue"].rolling(rolling_window).mean()
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=grp["order_date"], y=grp["revenue"], mode="lines", name="Revenue"))
        fig.add_trace(go.Scatter(x=grp["order_date"], y=grp["rolling"], mode="lines", name=f"{rolling_window}-period rolling"))
        fig.update_layout(yaxis_title="Revenue", xaxis_title="Date", height=450)
        render_fig_in_card("Sales Over Time", fig, height=450)

        st.subheader("AOV Over Time")
        if "aov" in df_filtered.columns:
            aov_grp = df_filtered.set_index("order_date").resample(resample_option)["aov"].mean().reset_index()
            fig2 = px.line(aov_grp, x="order_date", y="aov", title="AOV Over Time")
            render_fig_in_card("AOV Over Time", fig2, height=420)

            if "region" in df_filtered.columns:
                fig3 = px.box(df_filtered, x="region", y="aov", title="AOV Distribution by Region")
                render_fig_in_card("AOV Distribution by Region", fig3, height=420)
        else:
            st.info("AOV not available in dataset.")

        st.subheader("Repeat vs New customers Over Time")
        tmp = df_filtered.copy()
        tmp["is_returning"] = tmp["is_returning"].fillna(0).astype(int)
        grp2 = (tmp.groupby([pd.Grouper(key="order_date", freq=resample_option), "is_returning"])["customer_id"].nunique().reset_index())
        grp2["order_date"] = grp2["order_date"].dt.date
        fig4 = px.area(grp2, x="order_date", y="customer_id", color="is_returning", labels={"customer_id": "unique customers", "is_returning": "is_returning"})
        render_fig_in_card("Repeat vs New customers Over Time", fig4, height=420)

    # Products
    with tabs[1]:
        st.header("Products")
        control_col, _ = st.columns([1, 3])
        with control_col:
            top_n = st.number_input("Top N Products", min_value=5, max_value=200, value=20)

        st.subheader("Sales by Product")
        prod = df_filtered.groupby("product_name", as_index=False)["revenue"].sum().sort_values("revenue", ascending=False)
        prod_top = prod.head(int(top_n))
        fig = px.bar(prod_top, x="revenue", y="product_name", orientation="h", title=f"Top {top_n} Products by Revenue")
        render_fig_in_card(f"Top {top_n} Products by Revenue", fig, height=480)

        prod["cumperc"] = prod["revenue"].cumsum() / prod["revenue"].sum() * 100
        fig_pareto = go.Figure()
        fig_pareto.add_trace(go.Bar(x=prod["product_name"].head(50), y=prod["revenue"].head(50), name="Revenue"))
        fig_pareto.add_trace(go.Scatter(x=prod["product_name"].head(50), y=prod["cumperc"].head(50), name="Cumulative %", yaxis="y2"))
        fig_pareto.update_layout(yaxis2=dict(overlaying="y", side="right", range=[0, 110]), xaxis_tickangle=-45, height=500)
        render_fig_in_card("Pareto: Product Revenue vs Cumulative", fig_pareto, height=500)

        st.subheader("Units vs Revenue")
        if "units" in df_filtered.columns:
            agg = df_filtered.groupby("product_name", as_index=False).agg({"units": "sum", "revenue": "sum"})
            agg["aov"] = agg["revenue"] / agg["units"].replace(0, np.nan)
            fig3 = px.scatter(agg, x="units", y="revenue", size="revenue", hover_name="product_name", title="Units vs Revenue (bubble)")
            render_fig_in_card("Units vs Revenue (bubble)", fig3, height=480)
        else:
            st.info("units column not available in dataset.")

        st.subheader("Revenue by Category")
        cat = df_filtered.groupby("category", as_index=False)["revenue"].sum().sort_values("revenue", ascending=False)
        fig4 = px.treemap(cat, path=["category"], values="revenue", title="Revenue by Category (treemap)")
        render_fig_in_card("Revenue by Category", fig4, height=480)

    # Geography
    with tabs[2]:
        st.header("Geography")
        if "region" in df_filtered.columns:
            region_agg = df_filtered.groupby("region", as_index=False)["revenue"].sum().sort_values("revenue", ascending=False)
            fig = px.bar(region_agg, x="region", y="revenue", title="Revenue by Region")
            render_fig_in_card("Revenue by Region", fig, height=420)

        if "country" in df_filtered.columns:
            country_agg = df_filtered.groupby("country", as_index=False)["revenue"].sum().sort_values("revenue", ascending=False)
            fig2 = px.bar(country_agg.head(50), x="country", y="revenue", title="Top Countries by Revenue")
            render_fig_in_card("Top Countries by Revenue", fig2, height=420)

        if "city" in df_filtered.columns:
            city_agg = df_filtered.groupby("city", as_index=False)["revenue"].sum().sort_values("revenue", ascending=False).head(30)
            fig3 = px.bar(city_agg, x="city", y="revenue", title="Top Cities by Revenue")
            render_fig_in_card("Top Cities by Revenue", fig3, height=420)

        if "region" in df_filtered.columns:
            region_agg = df_filtered.groupby("region", as_index=False)["revenue"].sum().sort_values("revenue", ascending=False)
            figp = px.pie(region_agg, values="revenue", names="region", title="Revenue Share by Region")
            render_fig_in_card("Revenue Share by Region", figp, height=420)

        if "country" in df_filtered.columns:
            country_agg = df_filtered.groupby("country", as_index=False)["revenue"].sum()
            try:
                fgc = px.choropleth(country_agg, locations="country", locationmode="country names", color="revenue", title="Revenue by Country")
                render_fig_in_card("Choropleth: Revenue by Country", fgc, height=520)
            except Exception as e:
                st.error("Choropleth failed, maybe country names are non-standard. Error: " + str(e))

    # People
    with tabs[3]:
        st.header("People (Sales Team)")
        control_col, _ = st.columns([1, 3])
        with control_col:
            top_k_rep = st.number_input("Top K reps to show", min_value=3, max_value=100, value=10)

        if "salesperson" in df_filtered.columns:
            rep_agg = df_filtered.groupby("salesperson", as_index=False)["revenue"].sum().sort_values("revenue", ascending=False).head(int(top_k_rep))
            fig = px.bar(rep_agg, x="revenue", y="salesperson", orientation="h", title="Top Salespeople by Revenue")
            render_fig_in_card("Top Salespeople by Revenue", fig, height=480)

            leaderboard = df_filtered.groupby("salesperson", as_index=False).agg(total_revenue=("revenue", "sum"), total_orders=("order_id", "nunique"))
            leaderboard = leaderboard.sort_values("total_revenue", ascending=False).reset_index(drop=True)
            st.markdown("<div class='card'><div class='card-title'>Leaderboard</div></div>", unsafe_allow_html=True)
            st.dataframe(leaderboard.head(50))
        else:
            st.info("No salesperson column in dataset")

        if "sales_cycle_days" in df_filtered.columns:
            fig = px.histogram(df_filtered, x="sales_cycle_days", nbins=40, title="Sales Cycle Days Distribution")
            render_fig_in_card("Sales Cycle Days Distribution", fig, height=420)

            if "salesperson" in df_filtered.columns:
                avg_rep = df_filtered.groupby("salesperson", as_index=False)["sales_cycle_days"].mean().sort_values("sales_cycle_days")
                st.markdown("<div class='card'><div class='card-title'>Average Sales Cycle by Rep</div></div>", unsafe_allow_html=True)
                st.dataframe(avg_rep.head(50))
        else:
            st.info("sales_cycle_days not available in dataset")

    # Conversion / Pipeline
    with tabs[4]:
        st.header("Conversion & Pipeline")
        if "stage" in df_filtered.columns and "opportunity_id" in df_filtered.columns:
            stage_counts = df_filtered.groupby("stage")["opportunity_id"].nunique().reset_index()
            stage_counts = stage_counts.sort_values("opportunity_id", ascending=False)
            fig = go.Figure(go.Funnel(y=stage_counts["stage"], x=stage_counts["opportunity_id"]))
            fig.update_layout(title="Opportunity Funnel")
            render_fig_in_card("Opportunity Funnel", fig, height=420)
        else:
            st.info("stage or opportunity_id not available")

        if "opportunity_id" in df_filtered.columns:
            opps = df_filtered.groupby("opportunity_id").agg(stage=("stage", "last"), lead_date=("lead_date", "min"), close_date=("close_date", "min"), revenue=("revenue", "sum")).reset_index()
            st.markdown("<div class='card'><div class='card-title'>Pipeline table</div></div>", unsafe_allow_html=True)
            st.dataframe(opps.head(200))
        else:
            st.info("opportunity_id not found")

    st.markdown("<div class='footer'>ContinuumAi - The Future of Business Intelligence</div>", unsafe_allow_html=True)

# End of file
