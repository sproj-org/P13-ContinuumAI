import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime
import os

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
        "⚠️ Backend API is not responding. Please ensure the API server is running on http://localhost:8000"
    )
    st.info("To start the API: cd backend/api && python main.py")
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
    st.write("**Available Datasets:**")
    for dataset in datasets:
        col1, col2, col3 = st.columns([3, 1, 1])
        with col1:
            st.write(f"📊 {dataset['name']} ({dataset['total_records']} records)")
        with col2:
            if st.button(f"Load", key=f"load_{dataset['id']}"):
                st.session_state.dataset_id = dataset["id"]
                st.session_state.dataset_info = dataset
                st.rerun()

        with col3:
            if st.button(f"Delete", key=f"delete_{dataset['id']}"):
                if api_client.delete_dataset(dataset["id"]):
                    st.success("Dataset deleted successfully!")
                    st.rerun()


# File upload section
uploaded_file = st.file_uploader("Upload New CSV File", type=["csv"])

col1, col2 = st.columns([3, 1])
with col2:
    use_demo = st.button("Use Demo Data", help="Load sample sales data for testing")

# Handle demo data
if use_demo:
    demo_path = os.path.join(os.path.dirname(__file__), "..", "data", "demo_sales.csv")
    if os.path.exists(demo_path):
        with open(demo_path, "rb") as f:
            dataset_id = api_client.upload_csv(f, "demo_sales.csv", "Demo Sales Data")
            if dataset_id:
                st.session_state.dataset_id = dataset_id
                st.success("✅ Demo data uploaded successfully!")
                st.rerun()
    else:
        st.error("Demo data file not found")

# Handle file upload
if uploaded_file is not None:
    uploaded_file.seek(0)  # Reset file pointer
    dataset_id = api_client.upload_csv(uploaded_file, uploaded_file.name)
    if dataset_id:
        st.session_state.dataset_id = dataset_id
        st.success(f"✅ File uploaded successfully! Dataset ID: {dataset_id}")
        st.rerun()

# --- Analysis Section ---
if st.session_state.dataset_id is None:
    st.info("Please upload a CSV file or load an existing dataset to begin analysis.")
    st.stop()

# Get analysis results
if st.session_state.analysis_result is None:
    with st.spinner("Analyzing dataset..."):
        analysis_result = api_client.analyze_dataset(st.session_state.dataset_id)
        if analysis_result:
            st.session_state.analysis_result = analysis_result
        else:
            st.error("Failed to analyze dataset")
            st.stop()

analysis = st.session_state.analysis_result
kpis = analysis.get("kpis", {})

# --- Display Current Dataset Info ---
st.success(
    f"📊 Currently analyzing: Dataset {st.session_state.dataset_id} ({analysis.get('total_records', 0)} records)"
)

# --- KPIs Display ---
st.markdown("---")
st.markdown(
    "<h2 style='text-align:left; color:#000000;'>Quick Insights</h2>",
    unsafe_allow_html=True,
)

col1, col2, col3, col4 = st.columns(4)
col1.metric("Total Revenue", f"${kpis.get('total_revenue', 0):,.2f}")
col2.metric("Total Orders", f"{kpis.get('total_orders', 0):,}")
col3.metric("Average Order Value (AOV)", f"${kpis.get('avg_aov', 0):,.2f}")

conv_rate = kpis.get("conversion_rate", 0)
conv_display = f"{conv_rate:.1%}" if conv_rate and not pd.isna(conv_rate) else "N/A"
col4.metric("Conversion Rate", conv_display)

ncol, rcol = st.columns(2)
ncol.metric("New customers (unique)", f"{kpis.get('new_count', 0):,}")
rcol.metric("Returning customers (unique)", f"{kpis.get('returning_count', 0):,}")

# --- Filtering Section ---
st.markdown("---")
st.subheader("🎛️ Filters")

# Get filter options
filter_options = api_client.get_filter_options(st.session_state.dataset_id)

# Create filter controls
col1, col2 = st.columns(2)

with col1:
    # Date filters
    st.write("**Date Range:**")
    date_from = st.date_input("From Date", value=None, key="date_from")
    date_to = st.date_input("To Date", value=None, key="date_to")

with col2:
    # Dropdown filters
    if "regions" in filter_options:
        selected_regions = st.multiselect("Regions", filter_options["regions"])
    else:
        selected_regions = []

    if "reps" in filter_options:
        selected_reps = st.multiselect("Sales Representatives", filter_options["reps"])
    else:
        selected_reps = []

# Categories filter (full width)
if "categories" in filter_options:
    selected_categories = st.multiselect(
        "Product Categories", filter_options["categories"]
    )
else:
    selected_categories = []

# Apply filters button
col1, col2, col3 = st.columns([1, 1, 2])
with col1:
    apply_filters = st.button("🔍 Apply Filters", type="primary")
with col2:
    clear_filters = st.button("🗑️ Clear Filters")

# Handle filter actions
if apply_filters or clear_filters:
    if clear_filters:
        # Reset all filters
        st.session_state.filtered_analysis = None
        for key in ["date_from", "date_to", "regions", "reps", "categories"]:
            if key in st.session_state:
                del st.session_state[key]
        st.rerun()
    else:
        # Apply filters
        with st.spinner("Applying filters..."):
            filtered_result = api_client.analyze_dataset_filtered(
                st.session_state.dataset_id,
                date_from=date_from,
                date_to=date_to,
                regions=selected_regions if selected_regions else None,
                reps=selected_reps if selected_reps else None,
                categories=selected_categories if selected_categories else None,
            )
            if filtered_result:
                st.session_state.filtered_analysis = filtered_result
                st.success("✅ Filters applied successfully!")
                st.rerun()

# Update KPIs to use filtered data if available
if "filtered_analysis" in st.session_state and st.session_state.filtered_analysis:
    st.info(
        f"📊 Showing filtered results: {st.session_state.filtered_analysis['total_records']} of {st.session_state.filtered_analysis['original_records']} records"
    )
    analysis = st.session_state.filtered_analysis  # Use filtered data
    kpis = analysis.get("kpis", {})
else:
    analysis = st.session_state.analysis_result  # Use original data
    kpis = analysis.get("kpis", {})

st.markdown("---")

# --- Data Preview ---
st.subheader("Data Preview")
if "data_preview" in analysis:
    preview_df = pd.DataFrame(analysis["data_preview"])
    st.dataframe(preview_df)
else:
    st.warning("No data preview available")

# --- Dataset Columns Info ---
st.subheader("Dataset Information")
if "columns" in analysis:
    st.write(
        f"**Columns ({len(analysis['columns'])}):** {', '.join(analysis['columns'])}"
    )

# --- Actions ---
st.subheader("Actions")
col1, col2 = st.columns(2)
with col1:
    if st.button("🔄 Refresh Analysis"):
        st.session_state.analysis_result = None
        st.rerun()

with col2:
    if st.button("📤 Upload Different Dataset"):
        st.session_state.dataset_id = None
        st.session_state.analysis_result = None
        st.session_state.dataset_info = None
        st.rerun()

# Note about filtering
st.info(
    "🚧 Advanced filtering and detailed charts will be added in the next phase. This version focuses on core API integration."
)
