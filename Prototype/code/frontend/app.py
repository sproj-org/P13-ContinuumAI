import streamlit as st
import sys
import os
import pandas as pd
import numpy as np
from datetime import datetime

# Add the backend directory to the Python path
backend_path = os.path.join(os.path.dirname(__file__), '..', 'backend')
if backend_path not in sys.path:
    sys.path.insert(0, backend_path)

# Import the functions directly
import data_logic

# --- Page Configuration ---
st.set_page_config(page_title="ContinuumAI Sales Dashboard", layout="wide")

# --- Main Application ---
st.title("ContinuumAI Sales Dashboard")

# --- Data Loading ---

# Initialize session state for demo data
if 'using_demo_data' not in st.session_state:
    st.session_state.using_demo_data = False

uploaded_file = st.file_uploader("Upload CSV File to Get Started...", type=["csv"])

col1, col2 = st.columns([3, 1])
with col2:
    use_demo = st.button("Use Demo Data", help="Load sample sales data for testing")

# If user clicks "Use Demo Data", set session state
if use_demo:
    st.session_state.using_demo_data = True

# If user uploads a file, clear demo data state
if uploaded_file is not None:
    st.session_state.using_demo_data = False

# Determine data source
if uploaded_file is None and not st.session_state.using_demo_data:
    st.info("Please upload your sales CSV file to begin analyzing your data.")
    st.stop()
elif st.session_state.using_demo_data:
    # Load demo data
    default_data_path = os.path.join(os.path.dirname(__file__), '..', 'data', 'demo_sales.csv')
    if os.path.exists(default_data_path):
        try:
            df = data_logic.load_data_from_file(default_data_path)
            st.success(f"Demo data loaded successfully! ({len(df)} records)")
        except Exception as e:
            st.error(f"Error loading demo data: {e}")
            st.stop()
    else:
        st.error("Demo data file not found.")
        st.stop()
else:
    # Load uploaded file
    try:
        df = data_logic.load_data_from_buffer(uploaded_file)
        st.success(f"Successfully loaded {len(df)} records from your file!")
    except Exception as e:
        st.error(f"Error loading uploaded file: {e}")
        st.stop()

# --- Sidebar Filters ---
st.sidebar.header("Controls & Data")

# Show current data source
if st.session_state.using_demo_data:
    st.sidebar.success("Using Demo Data")
    if st.sidebar.button("Clear Demo Data"):
        st.session_state.using_demo_data = False
        st.rerun()
else:
    st.sidebar.info("Using Uploaded Data")

# Show available date range to user
if not df["order_date"].isna().all():
    actual_min = df["order_date"].min().date()
    actual_max = df["order_date"].max().date()
    st.sidebar.info(f"Data available: {actual_min} to {actual_max}")

# Initialize session state for filters if not exists
if 'filter_reset_counter' not in st.session_state:
    st.session_state.filter_reset_counter = 0

# Reset button - force widget recreation with new keys
if st.sidebar.button("Reset All Filters"):
    # Increment counter to generate new widget keys
    st.session_state.filter_reset_counter += 1
    st.rerun()

min_date = df["order_date"].min().date() if not df["order_date"].isna().all() else datetime.today().date()
max_date = df["order_date"].max().date() if not df["order_date"].isna().all() else datetime.today().date()

# Create unique widget keys that change when reset
reset_suffix = f"_{st.session_state.filter_reset_counter}"

date_range = st.sidebar.date_input(
    "Order Date Range", 
    value=(min_date, max_date),
    min_value=min_date, 
    max_value=max_date,
    key=f"date_filter{reset_suffix}"
)

if isinstance(date_range, (list, tuple)) and len(date_range) == 2:
    date_from, date_to = date_range
else:
    date_from, date_to = min_date, max_date

def _options_with_all(col: str) -> list:
    return ["All"] + sorted(df[col].dropna().unique().tolist()) if col in df.columns else ["All"]

# Create multiselect widgets with reset-aware keys
selected_regions = st.sidebar.multiselect(
    "Region", 
    options=_options_with_all("region"), 
    default=["All"],
    key=f"region_filter{reset_suffix}"
)

selected_reps = st.sidebar.multiselect(
    "Salesperson", 
    options=_options_with_all("salesperson"), 
    default=["All"],
    key=f"salesperson_filter{reset_suffix}"
)

selected_categories = st.sidebar.multiselect(
    "Product Category", 
    options=_options_with_all("category"), 
    default=["All"],
    key=f"category_filter{reset_suffix}"
) 

if len(selected_regions) > 1 and "All" in selected_regions:
    selected_regions = [r for r in selected_regions if r != "All"]
if len(selected_reps) > 1 and "All" in selected_reps:
    selected_reps = [r for r in selected_reps if r != "All"]
if len(selected_categories) > 1 and "All" in selected_categories:
    selected_categories = [c for c in selected_categories if c != "All"] 

# Apply filters
df_filtered = data_logic.apply_filters(df, date_from, date_to, selected_regions, selected_reps, selected_categories)

# Download filtered data
csv_buffer = df_filtered.to_csv(index=False).encode("utf-8")
st.sidebar.download_button(label="Download Filtered Dataset (CSV)", data=csv_buffer, file_name="filtered_sales.csv", mime="text/csv")

# --- KPIs ---
kpis = data_logic.compute_kpis(df_filtered)

st.markdown("---")
st.markdown("<h2 style='text-align:left; color:#000000;'>Quick Insights</h2>", unsafe_allow_html=True)

col1, col2, col3, col4 = st.columns(4)
col1.metric("Total Revenue", f"${kpis['total_revenue']:,.2f}")
col2.metric("Total Orders", f"{kpis['total_orders']:,}")
col3.metric("Average Order Value (AOV)", f"${kpis['avg_aov']:,.2f}")

conv_display = f"{kpis['conversion_rate']:.1%}" if not pd.isna(kpis['conversion_rate']) else "N/A"
col4.metric("Conversion Rate", conv_display)

ncol, rcol = st.columns(2)
ncol.metric("New customers (unique)", f"{kpis['new_count']:,}")
rcol.metric("Returning customers (unique)", f"{kpis['returning_count']:,}")

st.markdown("---")

# --- Tabs for Different Chart Categories ---
tab1, tab2, tab3, tab4 = st.tabs(["Sales Overview", "Top Performers", "Product Analysis", "Customer Insights"])

with tab1:
    st.header("Sales Overview")
    
    # Main charts in columns
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("Sales by Region")
        if "region" in df_filtered.columns and "revenue" in df_filtered.columns:
            sales_by_region = df_filtered.groupby('region')['revenue'].sum().sort_values(ascending=True)
            st.bar_chart(sales_by_region)
        else:
            st.warning("Region or Revenue data not available")
    
    with col2:
        st.subheader("Sales over Time")
        if "order_date" in df_filtered.columns and "revenue" in df_filtered.columns:
            sales_over_time = df_filtered.set_index('order_date')['revenue'].resample('ME').sum()
            st.line_chart(sales_over_time)
        else:
            st.warning("Order Date or Revenue data not available")
    
    # Additional charts
    col3, col4 = st.columns(2)
    
    with col3:
        st.subheader("Sales by Channel")
        if "channel" in df_filtered.columns and "revenue" in df_filtered.columns:
            sales_by_channel = df_filtered.groupby('channel')['revenue'].sum()
            st.bar_chart(sales_by_channel)
    
    with col4:
        st.subheader("Revenue Distribution")
        if "revenue" in df_filtered.columns and len(df_filtered) > 0:
            # Create histogram data
            hist_values, bin_edges = np.histogram(df_filtered['revenue'], bins=20)
            # Create a DataFrame for the histogram
            hist_data = pd.DataFrame({
                'Revenue Range': [f"${bin_edges[i]:.0f}-${bin_edges[i+1]:.0f}" for i in range(len(hist_values))],
                'Count': hist_values
            })
            st.bar_chart(hist_data.set_index('Revenue Range')['Count'])
        else:
            st.warning("No revenue data available")

with tab2:
    st.header("Top Performers")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("Top Salespeople by Revenue")
        if "salesperson" in df_filtered.columns and "revenue" in df_filtered.columns:
            top_sales = df_filtered.groupby('salesperson')['revenue'].sum().sort_values(ascending=False).head(10)
            st.bar_chart(top_sales)
    
    with col2:
        st.subheader("Top Products by Revenue")
        if "product_name" in df_filtered.columns and "revenue" in df_filtered.columns:
            top_products = df_filtered.groupby('product_name')['revenue'].sum().sort_values(ascending=False).head(10)
            st.bar_chart(top_products)
    
    # Leaderboard tables
    col3, col4 = st.columns(2)
    
    with col3:
        st.subheader("Salesperson Leaderboard")
        if "salesperson" in df_filtered.columns and "revenue" in df_filtered.columns:
            leaderboard = df_filtered.groupby('salesperson').agg({
                'revenue': 'sum',
                'order_id': 'count'
            }).sort_values('revenue', ascending=False).head(10)
            leaderboard.columns = ['Total Revenue', 'Total Orders']
            leaderboard['Total Revenue'] = leaderboard['Total Revenue'].apply(lambda x: f"${x:,.2f}")
            st.dataframe(leaderboard)
    
    with col4:
        st.subheader("Regional Performance")
        if "region" in df_filtered.columns and "revenue" in df_filtered.columns:
            regional_perf = df_filtered.groupby('region').agg({
                'revenue': 'sum',
                'order_id': 'count',
                'customer_id': 'nunique'
            }).sort_values('revenue', ascending=False)
            regional_perf.columns = ['Total Revenue', 'Total Orders', 'Unique Customers']
            regional_perf['Total Revenue'] = regional_perf['Total Revenue'].apply(lambda x: f"${x:,.2f}")
            st.dataframe(regional_perf)

with tab3:
    st.header("Product Analysis")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("Sales by Product Category")
        if "category" in df_filtered.columns and "revenue" in df_filtered.columns:
            cat_sales = df_filtered.groupby('category')['revenue'].sum()
            st.bar_chart(cat_sales)
    
    with col2:
        st.subheader("Units Sold by Category")
        if "category" in df_filtered.columns and "units" in df_filtered.columns:
            cat_units = df_filtered.groupby('category')['units'].sum()
            st.bar_chart(cat_units)
    
    # Product performance table
    st.subheader("Product Performance Table")
    if "product_name" in df_filtered.columns and "revenue" in df_filtered.columns:
        product_analysis = df_filtered.groupby('product_name').agg({
            'revenue': 'sum',
            'units': 'sum',
            'order_id': 'count'
        }).sort_values('revenue', ascending=False)
        product_analysis.columns = ['Total Revenue', 'Units Sold', 'Number of Orders']
        product_analysis['Avg Revenue per Order'] = product_analysis['Total Revenue'] / product_analysis['Number of Orders']
        product_analysis['Total Revenue'] = product_analysis['Total Revenue'].apply(lambda x: f"${x:,.2f}")
        product_analysis['Avg Revenue per Order'] = product_analysis['Avg Revenue per Order'].apply(lambda x: f"${x:,.2f}")
        st.dataframe(product_analysis)

with tab4:
    st.header("Customer Insights")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("New vs Returning Customers")
        if "is_returning" in df_filtered.columns:
            customer_type = df_filtered.groupby('is_returning')['customer_id'].nunique()
            customer_type.index = customer_type.index.map({0: 'New', 1: 'Returning'})
            st.bar_chart(customer_type)
    
    with col2:
        st.subheader("Average Order Value by Customer Type")
        if "is_returning" in df_filtered.columns and "aov" in df_filtered.columns:
            aov_by_type = df_filtered.groupby('is_returning')['aov'].mean()
            aov_by_type.index = aov_by_type.index.map({0: 'New', 1: 'Returning'})
            st.bar_chart(aov_by_type)
    
    # Customer behavior analysis
    col3, col4 = st.columns(2)
    
    with col3:
        st.subheader("Top Customers by Revenue")
        if "customer_id" in df_filtered.columns and "revenue" in df_filtered.columns:
            top_customers = df_filtered.groupby('customer_id')['revenue'].sum().sort_values(ascending=False).head(10)
            st.bar_chart(top_customers)
    
    with col4:
        st.subheader("Customer Order Frequency")
        if "customer_id" in df_filtered.columns:
            order_freq = df_filtered.groupby('customer_id')['order_id'].count().value_counts().sort_index()
            order_freq.index = order_freq.index.astype(str) + ' orders'
            st.bar_chart(order_freq)

# --- Raw Data ---
st.markdown("---")
st.subheader("Raw Data")
st.dataframe(df_filtered)
