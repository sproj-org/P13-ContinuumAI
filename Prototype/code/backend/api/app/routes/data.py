from fastapi import APIRouter, Depends, UploadFile, File, HTTPException, Query
from sqlalchemy.orm import Session
from typing import Optional, List, Dict, Any
import pandas as pd
import io

from ..core.database import get_db
from ..services.data_service import DataService
from ..services.data_logic import preprocess, compute_kpis

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

        # Preprocess using your existing function
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
    Get KPIs and analysis using your existing data_logic functions.
    This endpoint returns what your Streamlit frontend currently shows.
    """
    try:
        data_service = DataService(db)
        df = data_service.get_dataframe_from_db(dataset_id)

        # Use your existing KPI computation
        kpis = compute_kpis(df)

        return {
            "dataset_id": dataset_id,
            "kpis": kpis,
            "data_preview": df.head(10).to_dict("records"),  # First 10 rows for preview
            "total_records": len(df),
            "columns": list(df.columns),
        }

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

        # Import filtering function
        from ..services.data_logic import apply_filters

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

        # Compute KPIs on filtered data
        from ..services.data_logic import compute_kpis

        kpis = compute_kpis(filtered_df)

        return {
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
