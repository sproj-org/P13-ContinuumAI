#data.py
from fastapi import APIRouter, Depends, UploadFile, File, HTTPException, Query
from sqlalchemy.orm import Session
from typing import Optional, List, Dict, Any
import pandas as pd
import numpy as np
import io

from ..core.database import get_db
from ..services.data_service import DataService
from ..services.data_logic import preprocess, compute_kpis, apply_filters, _apply_filters_from_params,make_json_serializable

router = APIRouter(prefix="/data", tags=["data"])


@router.post("/upload-csv/")
async def upload_csv(
    file: UploadFile = File(...),
    dataset_name: Optional[str] = None,
    db: Session = Depends(get_db),
):
    """
    Upload CSV file, preprocess it, and store in database.
    Returns dataset_id for future operations.
    """
    if not file.filename.endswith(".csv"):
        raise HTTPException(status_code=400, detail="Only CSV files allowed")

    try:
        # Read uploaded file
        contents = await file.read()
        df = pd.read_csv(io.StringIO(contents.decode("utf-8")))

        df = preprocess(df)

        # Store in database using data service
        data_service = DataService(db)
        dataset_id = data_service.import_csv_to_db(
            df, file.filename, dataset_name or file.filename.replace(".csv", "")
        )

        return {
            "success": True,
            "dataset_id": dataset_id,
            "message": f"CSV uploaded successfully. {len(df)} records processed.",
            "filename": file.filename,
            "columns": list(df.columns),
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error processing CSV: {str(e)}")


@router.get("/datasets/")
async def list_datasets(db: Session = Depends(get_db)):
    """List all available datasets"""
    data_service = DataService(db)
    datasets = data_service.list_datasets()
    return {"datasets": datasets}


@router.get("/datasets/{dataset_id}")
async def get_dataset_info(dataset_id: int, db: Session = Depends(get_db)):
    """Get dataset information without full data"""
    data_service = DataService(db)
    datasets = data_service.list_datasets()
    dataset = next((d for d in datasets if d["id"] == dataset_id), None)

    if not dataset:
        raise HTTPException(status_code=404, detail="Dataset not found")

    return dataset


@router.get("/datasets/{dataset_id}/analyze")
async def analyze_dataset(dataset_id: int, db: Session = Depends(get_db)):
    """
    Get KPIs and analysis using  existing data_logic functions.
    This endpoint returns what  Streamlit frontend currently shows.
    """
    try:
        data_service = DataService(db)
        df = data_service.get_dataframe_from_db(dataset_id)

        # Use  existing KPI computation
        kpis = compute_kpis(df)

        result = {
            "dataset_id": dataset_id,
            "kpis": kpis,
            "data_preview": df.head(10).to_dict("records"),  # First 10 rows for preview
            "total_records": len(df),
            "columns": list(df.columns),
        }
        return make_json_serializable(result)
    
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error analyzing dataset: {str(e)}"
        )


@router.get("/datasets/{dataset_id}/analyze-filtered")
async def analyze_dataset_filtered(
    dataset_id: int,
    date_from: Optional[str] = Query(None, description="Start date (YYYY-MM-DD)"),
    date_to: Optional[str] = Query(None, description="End date (YYYY-MM-DD)"),
    regions: Optional[str] = Query(None, description="Comma-separated regions"),
    reps: Optional[str] = Query(None, description="Comma-separated sales reps"),
    categories: Optional[str] = Query(None, description="Comma-separated categories"),
    db: Session = Depends(get_db),
):
    """Get filtered KPIs and analysis for a dataset"""
    try:
        data_service = DataService(db)
        df = data_service.get_dataframe_from_db(dataset_id)

        # Parse filter parameters
        regions_list = regions.split(",") if regions else None
        reps_list = reps.split(",") if reps else None
        categories_list = categories.split(",") if categories else None

        # Convert date strings to datetime - FIX THE COMPARISON ISSUE
        date_from_dt = None
        date_to_dt = None

        if date_from:
            date_from_dt = pd.to_datetime(date_from).date()  # Convert to date object
        if date_to:
            date_to_dt = pd.to_datetime(date_to).date()  # Convert to date object

        # Apply filters
        filtered_df = apply_filters(
            df, date_from_dt, date_to_dt, regions_list, reps_list, categories_list
        )

        kpis = compute_kpis(filtered_df)

        result = {
            "dataset_id": dataset_id,
            "filters_applied": {
                "date_from": date_from,
                "date_to": date_to,
                "regions": regions_list,
                "reps": reps_list,
                "categories": categories_list,
            },
            "kpis": kpis,
            "data_preview": filtered_df.head(10).to_dict("records"),
            "total_records": len(filtered_df),
            "original_records": len(df),
            "columns": list(filtered_df.columns),
        }

        return make_json_serializable(result)

    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error analyzing filtered dataset: {str(e)}"
        )


@router.delete("/datasets/{dataset_id}")
async def delete_dataset(dataset_id: int, db: Session = Depends(get_db)):
    """Delete a dataset"""
    data_service = DataService(db)
    success = data_service.delete_dataset(dataset_id)

    if not success:
        raise HTTPException(status_code=404, detail="Dataset not found")

    return {"message": "Dataset deleted successfully"}



# ============================================================================
# CHART ENDPOINTS - All support filtering
# ============================================================================


@router.get("/datasets/{dataset_id}/charts/sales-by-region")
async def get_sales_by_region(
    dataset_id: int,
    date_from: Optional[str] = Query(None),
    date_to: Optional[str] = Query(None),
    regions: Optional[str] = Query(None),
    reps: Optional[str] = Query(None),
    categories: Optional[str] = Query(None),
    db: Session = Depends(get_db)
):
    """Get sales aggregated by region with optional filters"""
    try:
        data_service = DataService(db)
        df = data_service.get_dataframe_from_db(dataset_id)
        
        
        df_filtered = _apply_filters_from_params(df, date_from, date_to, regions, reps, categories)
        
        if "region" not in df_filtered.columns or "revenue" not in df_filtered.columns:
            return {"chart_type": "bar", "data": {}, "labels": [], "values": []}
        
        # Use same logic as app.py
        sales_by_region = df_filtered.groupby('region')['revenue'].sum().sort_values(ascending=True)
        
        result = {
            "chart_type": "bar",
            "data": sales_by_region.to_dict(),
            "labels": list(sales_by_region.index),
            "values": list(sales_by_region.values)
        }
        return make_json_serializable(result)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error: {str(e)}")


@router.get("/datasets/{dataset_id}/charts/sales-over-time")
async def get_sales_over_time(
    dataset_id: int,
    date_from: Optional[str] = Query(None),
    date_to: Optional[str] = Query(None),
    regions: Optional[str] = Query(None),
    reps: Optional[str] = Query(None),
    categories: Optional[str] = Query(None),
    db: Session = Depends(get_db)
):
    """Get sales over time (monthly aggregation) with optional filters"""
    try:
        data_service = DataService(db)
        df = data_service.get_dataframe_from_db(dataset_id)
        
        # Apply filters
        df_filtered = _apply_filters_from_params(df, date_from, date_to, regions, reps, categories)
        
        if "order_date" not in df_filtered.columns or "revenue" not in df_filtered.columns:
            return {"chart_type": "line", "data": {}, "labels": [], "values": []}
        
        # Ensure order_date is datetime
        df_filtered['order_date'] = pd.to_datetime(df_filtered['order_date'])
        
        # Use same logic as app.py
        sales_over_time = df_filtered.set_index('order_date')['revenue'].resample('ME').sum()
        
        result = {
            "chart_type": "line",
            "data": {str(k.date()): float(v) for k, v in sales_over_time.items()},
            "labels": [str(d.date()) for d in sales_over_time.index],
            "values": [float(v) for v in sales_over_time.values]
        }
        return make_json_serializable(result)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error: {str(e)}")


@router.get("/datasets/{dataset_id}/charts/sales-by-channel")
async def get_sales_by_channel(
    dataset_id: int,
    date_from: Optional[str] = Query(None),
    date_to: Optional[str] = Query(None),
    regions: Optional[str] = Query(None),
    reps: Optional[str] = Query(None),
    categories: Optional[str] = Query(None),
    db: Session = Depends(get_db)
):
    """Get sales by channel with optional filters"""
    try:
        data_service = DataService(db)
        df = data_service.get_dataframe_from_db(dataset_id)
        
        # Apply filters
        df_filtered = _apply_filters_from_params(df, date_from, date_to, regions, reps, categories)
        
        if "channel" not in df_filtered.columns or "revenue" not in df_filtered.columns:
            return {"chart_type": "bar", "data": {}, "labels": [], "values": []}
        
        sales_by_channel = df_filtered.groupby('channel')['revenue'].sum()
        
        result = {
            "chart_type": "bar",
            "data": sales_by_channel.to_dict(),
            "labels": list(sales_by_channel.index),
            "values": list(sales_by_channel.values)
        }
        return make_json_serializable(result)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error: {str(e)}")


@router.get("/datasets/{dataset_id}/charts/revenue-distribution")
async def get_revenue_distribution(
    dataset_id: int,
    date_from: Optional[str] = Query(None),
    date_to: Optional[str] = Query(None),
    regions: Optional[str] = Query(None),
    reps: Optional[str] = Query(None),
    categories: Optional[str] = Query(None),
    db: Session = Depends(get_db)
):
    """Get revenue distribution histogram with optional filters"""
    try:
        data_service = DataService(db)
        df = data_service.get_dataframe_from_db(dataset_id)
        
        # Apply filters
        df_filtered = _apply_filters_from_params(df, date_from, date_to, regions, reps, categories)
        
        if "revenue" not in df_filtered.columns or len(df_filtered) == 0:
            return {"chart_type": "histogram", "data": {}, "labels": [], "values": []}
        
        # Use same logic as app.py
        hist_values, bin_edges = np.histogram(df_filtered['revenue'], bins=20)
        labels = [f"${bin_edges[i]:.0f}-${bin_edges[i+1]:.0f}" for i in range(len(hist_values))]
        
        result = {
            "chart_type": "histogram",
            "data": dict(zip(labels, hist_values.tolist())),
            "labels": labels,
            "values": hist_values.tolist()
        }
        return make_json_serializable(result)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error: {str(e)}")
    
@router.get("/datasets/{dataset_id}/charts/histogram-data")
async def get_histogram_data(
    dataset_id: int,
    column: str = Query("revenue", description="Column to create histogram for"),
    bins: int = Query(20, ge=5, le=100, description="Number of histogram bins"),
    date_from: Optional[str] = Query(None),
    date_to: Optional[str] = Query(None),
    regions: Optional[str] = Query(None),
    reps: Optional[str] = Query(None),
    categories: Optional[str] = Query(None),
    db: Session = Depends(get_db)
):
    """Get histogram data for any numeric column with optional filters"""
    try:
        
        data_service = DataService(db)
        df = data_service.get_dataframe_from_db(dataset_id)
        
        # Apply filters
        df_filtered = _apply_filters_from_params(df, date_from, date_to, regions, reps, categories)
        
        if column not in df_filtered.columns or len(df_filtered) == 0:
            return {"chart_type": "histogram", "data": {}, "labels": [], "values": []}
        
        # Ensure column is numeric
        df_filtered[column] = pd.to_numeric(df_filtered[column], errors='coerce')
        df_filtered = df_filtered.dropna(subset=[column])
        
        if len(df_filtered) == 0:
            return {"chart_type": "histogram", "data": {}, "labels": [], "values": []}
        
        # Create histogram - same logic as app.py
        hist_values, bin_edges = np.histogram(df_filtered[column], bins=bins)
        
        # Create labels based on column type
        if column == 'revenue':
            labels = [f"${bin_edges[i]:.0f}-${bin_edges[i+1]:.0f}" for i in range(len(hist_values))]
        else:
            labels = [f"{bin_edges[i]:.2f}-{bin_edges[i+1]:.2f}" for i in range(len(hist_values))]
        
        result = {
            "chart_type": "histogram",
            "column": column,
            "data": dict(zip(labels, hist_values.tolist())),
            "labels": labels,
            "values": hist_values.tolist(),
            "bin_edges": bin_edges.tolist()
        }
        return make_json_serializable(result)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error: {str(e)}")


# ============================================================================
# TOP PERFORMERS ENDPOINTS
# ============================================================================

@router.get("/datasets/{dataset_id}/top-performers/salespeople")
async def get_top_salespeople(
    dataset_id: int,
    limit: int = Query(10, ge=1, le=50),
    date_from: Optional[str] = Query(None),
    date_to: Optional[str] = Query(None),
    regions: Optional[str] = Query(None),
    reps: Optional[str] = Query(None),
    categories: Optional[str] = Query(None),
    db: Session = Depends(get_db)
):
    """Get top salespeople by revenue with optional filters"""
    try:
        data_service = DataService(db)
        df = data_service.get_dataframe_from_db(dataset_id)
        
        # Apply filters
        df_filtered = _apply_filters_from_params(df, date_from, date_to, regions, reps, categories)
        
        if "salesperson" not in df_filtered.columns or "revenue" not in df_filtered.columns:
            return {"chart_data": {}, "labels": [], "values": [], "leaderboard": {}}
        
        # Chart data 
        top_sales = df_filtered.groupby('salesperson')['revenue'].sum().sort_values(ascending=False).head(limit)
        
        # Leaderboard data 
        leaderboard = df_filtered.groupby('salesperson').agg({
            'revenue': 'sum',
            'order_id': 'count'
        }).sort_values('revenue', ascending=False).head(limit)
        leaderboard.columns = ['Total Revenue', 'Total Orders']
        
        result = {
            "chart_data": top_sales.to_dict(),
            "labels": list(top_sales.index),
            "values": [float(v) for v in top_sales.values],
            "leaderboard": leaderboard.to_dict('index')
        }
        return make_json_serializable(result)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error: {str(e)}")


@router.get("/datasets/{dataset_id}/top-performers/products")
async def get_top_products(
    dataset_id: int,
    limit: int = Query(10, ge=1, le=50),
    date_from: Optional[str] = Query(None),
    date_to: Optional[str] = Query(None),
    regions: Optional[str] = Query(None),
    reps: Optional[str] = Query(None),
    categories: Optional[str] = Query(None),
    db: Session = Depends(get_db)
):
    """Get top products by revenue with optional filters"""
    try:
        data_service = DataService(db)
        df = data_service.get_dataframe_from_db(dataset_id)
        
        # Apply filters
        df_filtered = _apply_filters_from_params(df, date_from, date_to, regions, reps, categories)
        
        if "product_name" not in df_filtered.columns or "revenue" not in df_filtered.columns:
            return {"chart_data": {}, "labels": [], "values": []}
        
        # Same logic as app.py
        top_products = df_filtered.groupby('product_name')['revenue'].sum().sort_values(ascending=False).head(limit)
        
        result = {
            "chart_data": top_products.to_dict(),
            "labels": list(top_products.index),
            "values": [float(v) for v in top_products.values]
        }
        return make_json_serializable(result)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error: {str(e)}")


@router.get("/datasets/{dataset_id}/regional-performance")
async def get_regional_performance(
    dataset_id: int,
    date_from: Optional[str] = Query(None),
    date_to: Optional[str] = Query(None),
    regions: Optional[str] = Query(None),
    reps: Optional[str] = Query(None),
    categories: Optional[str] = Query(None),
    db: Session = Depends(get_db)
):
    """Get regional performance metrics with optional filters"""
    try:
        data_service = DataService(db)
        df = data_service.get_dataframe_from_db(dataset_id)
        
        # Apply filters
        df_filtered = _apply_filters_from_params(df, date_from, date_to, regions, reps, categories)
        
        if "region" not in df_filtered.columns or "revenue" not in df_filtered.columns:
            return {"data": {}}
        
        # Same aggregation as app.py
        regional_perf = df_filtered.groupby('region').agg({
            'revenue': 'sum',
            'order_id': 'count',
            'customer_id': 'nunique'
        }).sort_values('revenue', ascending=False)
        regional_perf.columns = ['Total Revenue', 'Total Orders', 'Unique Customers']
        
        result = {
            "data": regional_perf.to_dict('index')
        }
        return make_json_serializable(result)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error: {str(e)}")


# ============================================================================
# PRODUCT ANALYSIS ENDPOINTS
# ============================================================================

@router.get("/datasets/{dataset_id}/product-analysis/by-category")
async def get_product_analysis_by_category(
    dataset_id: int,
    date_from: Optional[str] = Query(None),
    date_to: Optional[str] = Query(None),
    regions: Optional[str] = Query(None),
    reps: Optional[str] = Query(None),
    categories: Optional[str] = Query(None),
    db: Session = Depends(get_db)
):
    """Get product analysis by category with optional filters"""
    try:
        data_service = DataService(db)
        df = data_service.get_dataframe_from_db(dataset_id)
        
        # Apply filters
        df_filtered = _apply_filters_from_params(df, date_from, date_to, regions, reps, categories)
        
        result = {}
        
        # Sales by category 
        if "category" in df_filtered.columns and "revenue" in df_filtered.columns:
            cat_sales = df_filtered.groupby('category')['revenue'].sum()
            result['sales_by_category'] = {
                "data": cat_sales.to_dict(),
                "labels": list(cat_sales.index),
                "values": [float(v) for v in cat_sales.values]
            }
        
        # Units by category 
        if "category" in df_filtered.columns and "units" in df_filtered.columns:
            cat_units = df_filtered.groupby('category')['units'].sum()
            result['units_by_category'] = {
                "data": cat_units.to_dict(),
                "labels": list(cat_units.index),
                "values": [float(v) for v in cat_units.values]
            }
        
        return make_json_serializable(result)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error: {str(e)}")


@router.get("/datasets/{dataset_id}/product-analysis/performance-table")
async def get_product_performance_table(
    dataset_id: int,
    date_from: Optional[str] = Query(None),
    date_to: Optional[str] = Query(None),
    regions: Optional[str] = Query(None),
    reps: Optional[str] = Query(None),
    categories: Optional[str] = Query(None),
    db: Session = Depends(get_db)
):
    """Get detailed product performance table with optional filters"""
    try:
        data_service = DataService(db)
        df = data_service.get_dataframe_from_db(dataset_id)
        
        # Apply filters
        df_filtered = _apply_filters_from_params(df, date_from, date_to, regions, reps, categories)
        
        if "product_name" not in df_filtered.columns or "revenue" not in df_filtered.columns:
            return {"data": {}}
        
        # Same aggregation as app.py
        product_analysis = df_filtered.groupby('product_name').agg({
            'revenue': 'sum',
            'units': 'sum',
            'order_id': 'count'
        }).sort_values('revenue', ascending=False)
        product_analysis.columns = ['Total Revenue', 'Units Sold', 'Number of Orders']
        product_analysis['Avg Revenue per Order'] = product_analysis['Total Revenue'] / product_analysis['Number of Orders']
        
        result = {
            "data": product_analysis.to_dict('index')
        }
        return make_json_serializable(result)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error: {str(e)}")


# ============================================================================
# CUSTOMER INSIGHTS ENDPOINTS
# ============================================================================

@router.get("/datasets/{dataset_id}/customer-insights")
async def get_customer_insights(
    dataset_id: int,
    date_from: Optional[str] = Query(None),
    date_to: Optional[str] = Query(None),
    regions: Optional[str] = Query(None),
    reps: Optional[str] = Query(None),
    categories: Optional[str] = Query(None),
    db: Session = Depends(get_db)
):
    """Get comprehensive customer insights with optional filters"""
    try:
        data_service = DataService(db)
        df = data_service.get_dataframe_from_db(dataset_id)
        
        # Apply filters
        df_filtered = _apply_filters_from_params(df, date_from, date_to, regions, reps, categories)
        
        result = {}
        
        # New vs Returning 
        if "is_returning" in df_filtered.columns and "customer_id" in df_filtered.columns:
            customer_type = df_filtered.groupby('is_returning')['customer_id'].nunique()
            # Map to string keys like app.py does
            result['new_vs_returning'] = {
                "data": {
                    'New': int(customer_type.get(0, 0)),
                    'Returning': int(customer_type.get(1, 0))
                },
                "labels": ['New', 'Returning'],
                "values": [int(customer_type.get(0, 0)), int(customer_type.get(1, 0))]
            }
        
        # AOV by customer type 
        if "is_returning" in df_filtered.columns and "aov" in df_filtered.columns:
            aov_by_type = df_filtered.groupby('is_returning')['aov'].mean()
            result['aov_by_type'] = {
                "data": {
                    'New': float(aov_by_type.get(0, 0)),
                    'Returning': float(aov_by_type.get(1, 0))
                },
                "labels": ['New', 'Returning'],
                "values": [float(aov_by_type.get(0, 0)), float(aov_by_type.get(1, 0))]
            }
        
        # Top customers 
        if "customer_id" in df_filtered.columns and "revenue" in df_filtered.columns:
            top_customers = df_filtered.groupby('customer_id')['revenue'].sum().sort_values(ascending=False).head(10)
            result['top_customers'] = {
                "data": top_customers.to_dict(),
                "labels": list(top_customers.index),
                "values": [float(v) for v in top_customers.values]
            }
        
        # Order frequency 
        if "customer_id" in df_filtered.columns and "order_id" in df_filtered.columns:
            order_freq = df_filtered.groupby('customer_id')['order_id'].count().value_counts().sort_index()
            result['order_frequency'] = {
                "data": {f"{int(k)} orders": int(v) for k, v in order_freq.items()},
                "labels": [f"{int(k)} orders" for k in order_freq.index],
                "values": [int(v) for v in order_freq.values]
            }
        
        return make_json_serializable(result)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error: {str(e)}")


# ============================================================================
# EXPORT ENDPOINT
# ============================================================================

@router.get("/datasets/{dataset_id}/export-csv")
async def export_filtered_csv(
    dataset_id: int,
    date_from: Optional[str] = Query(None),
    date_to: Optional[str] = Query(None),
    regions: Optional[str] = Query(None),
    reps: Optional[str] = Query(None),
    categories: Optional[str] = Query(None),
    db: Session = Depends(get_db)
):
    """Export filtered dataset as CSV"""
    try:
        from fastapi.responses import StreamingResponse
        
        data_service = DataService(db)
        df = data_service.get_dataframe_from_db(dataset_id)
        
        
        df_filtered = _apply_filters_from_params(df, date_from, date_to, regions, reps, categories)
        
        # Convert to CSV
        csv_buffer = io.StringIO()
        df_filtered.to_csv(csv_buffer, index=False)
        csv_buffer.seek(0)
        
        return StreamingResponse(
            iter([csv_buffer.getvalue()]),
            media_type="text/csv",
            headers={"Content-Disposition": "attachment; filename=filtered_sales.csv"}
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error: {str(e)}")
    

############################
#RAW DATA
############################


@router.get("/datasets/{dataset_id}/raw-data")
async def get_raw_data(
    dataset_id: int,
    limit: Optional[int] = Query(None, ge=1, le=10000, description="Limit number of rows returned"),
    offset: int = Query(0, ge=0, description="Number of rows to skip"),
    date_from: Optional[str] = Query(None),
    date_to: Optional[str] = Query(None),
    regions: Optional[str] = Query(None),
    reps: Optional[str] = Query(None),
    categories: Optional[str] = Query(None),
    db: Session = Depends(get_db)
):
    """Get raw filtered data for display - same as bottom table in app.py"""
    try:
        data_service = DataService(db)
        df = data_service.get_dataframe_from_db(dataset_id)
        
        
        df_filtered = _apply_filters_from_params(df, date_from, date_to, regions, reps, categories)
        
        # Apply pagination
        total_records = len(df_filtered)
        
        if offset > 0:
            df_filtered = df_filtered.iloc[offset:]
        
        if limit:
            df_filtered = df_filtered.head(limit)
        
        # Convert to records for JSON serialization
        records = df_filtered.to_dict('records')
        
        # Handle datetime serialization
        for record in records:
            for key, value in record.items():
                if pd.isna(value):
                    record[key] = None
                elif isinstance(value, pd.Timestamp):
                    record[key] = value.strftime('%Y-%m-%d %H:%M:%S')
                elif isinstance(value, np.integer):
                    record[key] = int(value)
                elif isinstance(value, np.floating):
                    record[key] = float(value)
        
        result = {
            "data": records,
            "total_records": total_records,
            "returned_records": len(records),
            "offset": offset,
            "columns": list(df_filtered.columns),
            "has_more": (offset + len(records)) < total_records
        }
        return make_json_serializable(result)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error: {str(e)}")