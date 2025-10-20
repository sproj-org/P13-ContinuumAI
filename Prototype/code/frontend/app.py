# app_api.py
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime
import io

# Import the API client
from api_client import ContinuumAPIClient

# --- Page Configuration ---
st.set_page_config(
    page_title="ContinuumAI Sales Dashboard (API Version)", layout="wide"
)


# --- Initialize API Client ---
@st.cache_resource
def get_api_client():
    return ContinuumAPIClient()


api_client = get_api_client()

# --- API Health Check ---
if not api_client.health_check():
    st.error(
        "❌ Backend API is not available. Please ensure the backend server is running."
    )
    st.stop()

# --- Main Application ---
st.title("ContinuumAI Sales Dashboard (API-Powered)")

# --- Session State for API Integration ---
if "dataset_id" not in st.session_state:
    st.session_state.dataset_id = None
if "analysis_result" not in st.session_state:
    st.session_state.analysis_result = None
if "dataset_info" not in st.session_state:
    st.session_state.dataset_info = None

# --- Data Loading Section ---
st.subheader("Data Management")

# Show existing datasets
datasets = api_client.get_datasets()
if datasets:
    st.write("**Existing Datasets:**")
    for dataset in datasets:
        col1, col2, col3 = st.columns([3, 1, 1])
        with col1:
            # Fix: Use 'record_count' instead of 'records' to match backend
            record_count = dataset.get("total_records", 0)
            st.write(f"📊 {dataset['name']} ({record_count} records)")
        with col2:
            if st.button("Load", key=f"load_{dataset['id']}"):
                st.session_state.dataset_id = dataset["id"]
                st.session_state.analysis_result = None
                st.rerun()
        with col3:
            if st.button("Delete", key=f"delete_{dataset['id']}"):
                if api_client.delete_dataset(dataset["id"]):
                    st.success("Dataset deleted!")
                    st.rerun()

# File upload section
uploaded_file = st.file_uploader("Upload New CSV File", type=["csv"])

col1, col2 = st.columns([3, 1])
with col2:
    use_demo = st.button("Use Demo Data", type="secondary")

# Handle demo data
if use_demo:
    # Check if demo data was already uploaded in this session
    if "demo_uploaded" not in st.session_state:
        # Upload demo data from backend
        demo_data = """order_date,customer_id,product_name,category,units,revenue,aov,region,salesperson,channel
2024-01-15,C001,Product A,Electronics,5,2500,500,North,John Doe,Online
2024-01-16,C002,Product B,Clothing,3,450,150,South,Jane Smith,Retail
2024-01-17,C003,Product C,Electronics,2,1200,600,East,Bob Johnson,Online"""

        demo_buffer = io.StringIO(demo_data)
        dataset_id = api_client.upload_csv(
            demo_buffer, "demo_data.csv", "Demo Sales Data"
        )
        if dataset_id:
            st.session_state.dataset_id = dataset_id
            st.session_state.analysis_result = None
            st.session_state.demo_uploaded = True
            st.success("Demo data loaded!")
            st.rerun()
    else:
        st.success("Demo data already loaded!")

# Handle file upload
if uploaded_file is not None:
    # Check if this file has already been processed to prevent re-upload loops
    if f"uploaded_{uploaded_file.name}" not in st.session_state:
        dataset_id = api_client.upload_csv(uploaded_file, uploaded_file.name)
        if dataset_id:
            st.session_state.dataset_id = dataset_id
            st.session_state.analysis_result = None
            # Mark this file as processed to prevent re-upload
            st.session_state[f"uploaded_{uploaded_file.name}"] = True
            st.success(f"File '{uploaded_file.name}' uploaded successfully!")
            st.rerun()
    else:
        # File already processed, just show success message
        st.success(f"File '{uploaded_file.name}' already uploaded!")

# --- Analysis Section ---
if st.session_state.dataset_id is None:
    st.info("👆 Please upload a CSV file or use demo data to begin analysis.")
    st.stop()

# Get analysis results
if st.session_state.analysis_result is None:
    with st.spinner("Analyzing dataset..."):
        st.session_state.analysis_result = api_client.analyze_dataset(
            st.session_state.dataset_id
        )

analysis = st.session_state.analysis_result
if not analysis:
    st.error("Failed to analyze dataset")
    st.stop()

kpis = analysis.get("kpis", {})

# --- Display Current Dataset Info ---
st.success(
    f"📊 Currently analyzing: Dataset {st.session_state.dataset_id} ({analysis.get('total_records', 0)} records)"
)

# --- Filtering Section ---
st.markdown("---")
st.subheader("🎛️ Filters")

# Get filter options
filter_options = api_client.get_filter_options(st.session_state.dataset_id)

# Initialize session state for filters
if "filter_reset_counter" not in st.session_state:
    st.session_state.filter_reset_counter = 0

# Reset button
if st.button("Reset All Filters"):
    st.session_state.filter_reset_counter += 1
    st.rerun()

reset_suffix = f"_{st.session_state.filter_reset_counter}"

# Create filter controls
col1, col2 = st.columns(2)

with col1:
    # Date range filter
    if "data_preview" in analysis:
        df_preview = pd.DataFrame(analysis["data_preview"])
        if "order_date" in df_preview.columns:
            df_preview["order_date"] = pd.to_datetime(
                df_preview["order_date"], errors="coerce"
            )
            min_date = (
                df_preview["order_date"].min().date()
                if not df_preview["order_date"].isna().all()
                else datetime.today().date()
            )
            max_date = (
                df_preview["order_date"].max().date()
                if not df_preview["order_date"].isna().all()
                else datetime.today().date()
            )

            date_range = st.date_input(
                "Order Date Range",
                value=(min_date, max_date),
                min_value=min_date,
                max_value=max_date,
                key=f"date_filter{reset_suffix}",
            )
        else:
            date_range = None
    else:
        date_range = None

with col2:
    # Regions filter
    regions_options = ["All"] + filter_options.get("regions", [])
    selected_regions = st.multiselect(
        "Region",
        options=regions_options,
        default=["All"],
        key=f"region_filter{reset_suffix}",
    )

# Salespeople filter (full width)
reps_options = ["All"] + filter_options.get("reps", [])
selected_reps = st.multiselect(
    "Salesperson",
    options=reps_options,
    default=["All"],
    key=f"salesperson_filter{reset_suffix}",
)

# Categories filter (full width)
if "categories" in filter_options:
    categories_options = ["All"] + filter_options.get("categories", [])
    selected_categories = st.multiselect(
        "Categories",
        options=categories_options,
        default=["All"],
        key=f"categories_filter{reset_suffix}",
    )
else:
    selected_categories = ["All"]

# Apply filters button
apply_filters = st.button("Apply Filters", type="primary")

# --- Get Filtered Analysis ---
filtered_analysis = analysis  # Default to unfiltered

if apply_filters or any(
    [
        selected_regions != ["All"],
        selected_reps != ["All"],
        selected_categories != ["All"],
        date_range,
    ]
):
    # Build filter parameters
    filter_params = {}

    if date_range and isinstance(date_range, (list, tuple)) and len(date_range) == 2:
        filter_params["date_from"] = date_range[0]
        filter_params["date_to"] = date_range[1]

    if selected_regions != ["All"]:
        filter_params["regions"] = selected_regions
    if selected_reps != ["All"]:
        filter_params["reps"] = selected_reps
    if selected_categories != ["All"]:
        filter_params["categories"] = selected_categories

    # Get filtered analysis
    with st.spinner("Applying filters..."):
        filtered_analysis = api_client.analyze_dataset_filtered(
            st.session_state.dataset_id, **filter_params
        )
        if not filtered_analysis:
            filtered_analysis = analysis

# Use filtered KPIs
filtered_kpis = filtered_analysis.get("kpis", kpis)

# --- KPIs Display ---
st.markdown("---")
st.markdown(
    "<h2 style='text-align:left; color:#000000;'>Quick Insights</h2>",
    unsafe_allow_html=True,
)

col1, col2, col3, col4 = st.columns(4)
col1.metric("Total Revenue", f"${filtered_kpis.get('total_revenue', 0):,.2f}")
col2.metric("Total Orders", f"{filtered_kpis.get('total_orders', 0):,}")
col3.metric("Average Order Value (AOV)", f"${filtered_kpis.get('avg_aov', 0):,.2f}")

conv_rate = filtered_kpis.get("conversion_rate", 0)
conv_display = f"{conv_rate:.1%}" if conv_rate and not pd.isna(conv_rate) else "N/A"
col4.metric("Conversion Rate", conv_display)

ncol, rcol = st.columns(2)
ncol.metric("New customers (unique)", f"{filtered_kpis.get('new_count', 0):,}")
rcol.metric(
    "Returning customers (unique)", f"{filtered_kpis.get('returning_count', 0):,}"
)

# --- Tabs for Different Views ---
tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs(
    [
        "📈 Sales Overview",
        "🏆 Top Performers",
        "📦 Product Analysis",
        "👥 Customer Insights",
        "🌍 Regional Analysis",
        "📋 Raw Data",
    ]
)

# Get current filter params for chart calls
chart_filters = {}
if date_range and isinstance(date_range, (list, tuple)) and len(date_range) == 2:
    chart_filters["date_from"] = date_range[0]
    chart_filters["date_to"] = date_range[1]
if selected_regions != ["All"]:
    chart_filters["regions"] = selected_regions
if selected_reps != ["All"]:
    chart_filters["reps"] = selected_reps
if selected_categories != ["All"]:
    chart_filters["categories"] = selected_categories

# --- TAB 1: Sales Overview ---
with tab1:
    st.subheader("📈 Sales Overview")

    # Sales by Region
    col1, col2 = st.columns(2)

    with col1:
        st.markdown("**Sales by Region**")
        sales_by_region = api_client.get_sales_by_region(
            st.session_state.dataset_id, **chart_filters
        )
        if (
            sales_by_region
            and sales_by_region.get("labels")
            and sales_by_region.get("values")
        ):
            fig_region = px.pie(
                values=sales_by_region["values"],
                names=sales_by_region["labels"],
                title="Revenue Distribution by Region",
            )
            st.plotly_chart(fig_region, use_container_width=True)
        else:
            st.info("No regional data available")

    with col2:
        st.markdown("**Sales by Channel**")
        sales_by_channel = api_client.get_sales_by_channel(
            st.session_state.dataset_id, **chart_filters
        )
        if (
            sales_by_channel
            and sales_by_channel.get("labels")
            and sales_by_channel.get("values")
        ):
            fig_channel = px.bar(
                x=sales_by_channel["labels"],
                y=sales_by_channel["values"],
                title="Sales by Channel",
            )
            fig_channel.update_layout(xaxis_title="Channel", yaxis_title="Revenue ($)")
            st.plotly_chart(fig_channel, use_container_width=True)
        else:
            st.info("No channel data available")

    # Sales Over Time
    st.markdown("**Sales Over Time**")
    sales_over_time = api_client.get_sales_over_time(
        st.session_state.dataset_id, **chart_filters
    )
    if (
        sales_over_time
        and sales_over_time.get("labels")
        and sales_over_time.get("values")
    ):
        df_time = pd.DataFrame(
            {
                "Date": pd.to_datetime(sales_over_time["labels"]),
                "Revenue": sales_over_time["values"],
            }
        )

        fig_time = px.line(
            df_time, x="Date", y="Revenue", title="Sales Trend Over Time"
        )
        fig_time.update_layout(yaxis_title="Revenue ($)")
        st.plotly_chart(fig_time, use_container_width=True)
    else:
        st.info("No time series data available")

    # Revenue Distribution
    st.markdown("**Revenue Distribution**")
    revenue_dist = api_client.get_revenue_distribution(
        st.session_state.dataset_id, **chart_filters
    )
    if revenue_dist and revenue_dist.get("labels") and revenue_dist.get("values"):
        fig_hist = px.bar(
            x=revenue_dist["labels"],
            y=revenue_dist["values"],
            title="Revenue Distribution",
        )
        fig_hist.update_layout(xaxis_title="Revenue Range", yaxis_title="Count")
        st.plotly_chart(fig_hist, use_container_width=True)
    else:
        st.info("No revenue distribution data available")

# --- TAB 2: Top Performers ---
with tab2:
    st.subheader("🏆 Top Performers")

    col1, col2 = st.columns(2)

    with col1:
        st.markdown("**Top Salespeople**")
        top_salespeople = api_client.get_top_salespeople(
            st.session_state.dataset_id, limit=10, **chart_filters
        )
        if top_salespeople and top_salespeople.get("leaderboard"):
            # Display leaderboard table
            leaderboard_data = top_salespeople["leaderboard"]
            df_salespeople = pd.DataFrame.from_dict(leaderboard_data, orient="index")
            df_salespeople.index.name = "Salesperson"
            df_salespeople = df_salespeople.reset_index()
            df_salespeople["Total Revenue"] = df_salespeople["Total Revenue"].apply(
                lambda x: f"${x:,.2f}"
            )
            st.dataframe(df_salespeople, use_container_width=True)

            # Chart using chart_data
            if top_salespeople.get("labels") and top_salespeople.get("values"):
                fig_sales = px.bar(
                    x=top_salespeople["labels"][:10],
                    y=top_salespeople["values"][:10],
                    title="Top Salespeople by Revenue",
                )
                fig_sales.update_layout(
                    xaxis_title="Salesperson", yaxis_title="Total Revenue ($)"
                )
                fig_sales.update_xaxes(tickangle=45)
                st.plotly_chart(fig_sales, use_container_width=True)
        else:
            st.info("No salesperson data available")

    with col2:
        st.markdown("**Top Products**")
        top_products = api_client.get_top_products(
            st.session_state.dataset_id, limit=10, **chart_filters
        )
        if top_products and top_products.get("chart_data"):
            # Create DataFrame from chart_data
            chart_data = top_products["chart_data"]
            df_products = pd.DataFrame(
                list(chart_data.items()), columns=["Product Name", "Total Revenue"]
            )
            df_products["Total Revenue"] = df_products["Total Revenue"].apply(
                lambda x: f"${x:,.2f}"
            )
            st.dataframe(df_products, use_container_width=True)

            # Chart
            if top_products.get("labels") and top_products.get("values"):
                fig_products = px.bar(
                    x=top_products["labels"][:10],
                    y=top_products["values"][:10],
                    title="Top Products by Revenue",
                )
                fig_products.update_layout(
                    xaxis_title="Product Name", yaxis_title="Total Revenue ($)"
                )
                fig_products.update_xaxes(tickangle=45)
                st.plotly_chart(fig_products, use_container_width=True)
        else:
            st.info("No product data available")

# --- TAB 3: Product Analysis ---
with tab3:
    st.subheader("📦 Product Analysis")

    # Product analysis by category
    product_analysis = api_client.get_product_analysis_by_category(
        st.session_state.dataset_id, **chart_filters
    )
    if product_analysis:
        col1, col2 = st.columns(2)

        with col1:
            # Sales by category
            if "sales_by_category" in product_analysis:
                st.markdown("**Revenue by Category**")
                sales_data = product_analysis["sales_by_category"]
                fig_sales_cat = px.bar(
                    x=sales_data["labels"],
                    y=sales_data["values"],
                    title="Revenue by Product Category",
                )
                fig_sales_cat.update_layout(
                    xaxis_title="Category", yaxis_title="Total Revenue ($)"
                )
                st.plotly_chart(fig_sales_cat, use_container_width=True)

        with col2:
            # Units by category
            if "units_by_category" in product_analysis:
                st.markdown("**Units Sold by Category**")
                units_data = product_analysis["units_by_category"]
                fig_units_cat = px.bar(
                    x=units_data["labels"],
                    y=units_data["values"],
                    title="Units Sold by Product Category",
                )
                fig_units_cat.update_layout(
                    xaxis_title="Category", yaxis_title="Units Sold"
                )
                st.plotly_chart(fig_units_cat, use_container_width=True)
    else:
        st.info("No product category data available")

    # Product performance table
    product_table = api_client.get_product_performance_table(
        st.session_state.dataset_id, **chart_filters
    )
    if product_table and product_table.get("data"):
        st.markdown("**Detailed Product Performance**")
        # Convert from indexed dictionary to DataFrame
        df_prod_table = pd.DataFrame.from_dict(product_table["data"], orient="index")
        df_prod_table.index.name = "Product Name"
        df_prod_table = df_prod_table.reset_index()
        # Format revenue columns
        df_prod_table["Total Revenue"] = df_prod_table["Total Revenue"].apply(
            lambda x: f"${x:,.2f}"
        )
        df_prod_table["Avg Revenue per Order"] = df_prod_table[
            "Avg Revenue per Order"
        ].apply(lambda x: f"${x:,.2f}")
        st.dataframe(df_prod_table, use_container_width=True)

# --- TAB 4: Customer Insights ---
with tab4:
    st.subheader("👥 Customer Insights")

    customer_insights = api_client.get_customer_insights(
        st.session_state.dataset_id, **chart_filters
    )
    if customer_insights:
        # New vs Returning customers chart
        if "new_vs_returning" in customer_insights:
            st.markdown("**New vs Returning Customers**")
            new_vs_ret = customer_insights["new_vs_returning"]
            fig_new_ret = px.pie(
                values=new_vs_ret["values"],
                names=new_vs_ret["labels"],
                title="Customer Type Distribution",
            )
            st.plotly_chart(fig_new_ret, use_container_width=True)

        # AOV by customer type
        if "aov_by_type" in customer_insights:
            st.markdown("**Average Order Value by Customer Type**")
            aov_data = customer_insights["aov_by_type"]
            fig_aov = px.bar(
                x=aov_data["labels"],
                y=aov_data["values"],
                title="AOV: New vs Returning Customers",
            )
            fig_aov.update_layout(
                xaxis_title="Customer Type", yaxis_title="Average Order Value ($)"
            )
            st.plotly_chart(fig_aov, use_container_width=True)

        # Top customers
        if "top_customers" in customer_insights:
            st.markdown("**Top Customers by Revenue**")
            top_cust = customer_insights["top_customers"]
            if top_cust.get("data"):
                # Convert to DataFrame for display
                df_top_customers = pd.DataFrame(
                    list(top_cust["data"].items()),
                    columns=["Customer ID", "Total Revenue"],
                )
                df_top_customers["Total Revenue"] = df_top_customers[
                    "Total Revenue"
                ].apply(lambda x: f"${x:,.2f}")
                st.dataframe(df_top_customers, use_container_width=True)

        # Order frequency
        if "order_frequency" in customer_insights:
            st.markdown("**Order Frequency Distribution**")
            order_freq = customer_insights["order_frequency"]
            fig_freq = px.bar(
                x=order_freq["labels"],
                y=order_freq["values"],
                title="Customer Order Frequency",
            )
            fig_freq.update_layout(
                xaxis_title="Orders per Customer", yaxis_title="Number of Customers"
            )
            st.plotly_chart(fig_freq, use_container_width=True)
    else:
        st.info("No customer insights available")

# --- TAB 5: Regional Analysis ---
with tab5:
    st.subheader("🌍 Regional Analysis")

    regional_performance = api_client.get_regional_performance(
        st.session_state.dataset_id, **chart_filters
    )
    if regional_performance and regional_performance.get("data"):
        # Convert from indexed dictionary to DataFrame
        df_regional = pd.DataFrame.from_dict(
            regional_performance["data"], orient="index"
        )
        df_regional.index.name = "Region"
        df_regional = df_regional.reset_index()

        # Format revenue column
        df_regional_display = df_regional.copy()
        df_regional_display["Total Revenue"] = df_regional_display[
            "Total Revenue"
        ].apply(lambda x: f"${x:,.2f}")

        st.markdown("**Regional Performance Summary**")
        st.dataframe(df_regional_display, use_container_width=True)

        # Regional charts
        if len(df_regional) > 0:
            col1, col2 = st.columns(2)

            with col1:
                fig_reg_rev = px.bar(
                    df_regional,
                    x="Region",
                    y="Total Revenue",
                    title="Revenue by Region",
                )
                fig_reg_rev.update_layout(yaxis_title="Total Revenue ($)")
                st.plotly_chart(fig_reg_rev, use_container_width=True)

            with col2:
                fig_reg_orders = px.bar(
                    df_regional, x="Region", y="Total Orders", title="Orders by Region"
                )
                fig_reg_orders.update_layout(yaxis_title="Total Orders")
                st.plotly_chart(fig_reg_orders, use_container_width=True)
    else:
        st.info("No regional performance data available")

# --- TAB 6: Raw Data ---
with tab6:
    st.subheader("📋 Raw Data")

    # Pagination controls
    col1, col2, col3 = st.columns([1, 1, 2])
    with col1:
        page_size = st.selectbox("Rows per page", [50, 100, 500, 1000], index=1)
    with col2:
        current_page = st.number_input("Page", min_value=1, value=1)

    offset = (current_page - 1) * page_size

    # Get raw data
    raw_data = api_client.get_raw_data(
        st.session_state.dataset_id, limit=page_size, offset=offset, **chart_filters
    )

    if raw_data:
        st.info(
            f"Showing {raw_data['returned_records']} of {raw_data['total_records']} total records"
        )

        if raw_data.get("data"):
            df_raw = pd.DataFrame(raw_data["data"])
            st.dataframe(df_raw, use_container_width=True)

            # Export option
            if st.button("Export Filtered Data to CSV"):
                csv_data = api_client.export_filtered_csv(
                    st.session_state.dataset_id, **chart_filters
                )
                if csv_data:
                    st.download_button(
                        label="Download CSV",
                        data=csv_data,
                        file_name=f"filtered_data_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                        mime="text/csv",
                    )
        else:
            st.info("No data available for the selected filters")
    else:
        st.error("Failed to load raw data")

# --- Footer ---
st.markdown("---")
st.markdown("*Powered by ContinuumAI Backend API*")
