from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from typing import Optional

from app.db.database import get_db
from app.db.models import User, SavedChart
from app.core.security import get_current_user
from app.schemas.dashboard import SavedChartCreate, SavedChartUpdate, SavedChartResponse

router = APIRouter(prefix="/saved-charts", tags=["Saved Charts"])


@router.get("", response_model=list[SavedChartResponse])
async def list_saved_charts(
    dataset_id: Optional[str] = Query(None, description="Filter by dataset"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List all saved charts for the current user."""
    query = db.query(SavedChart).filter(SavedChart.user_id == current_user.id)
    if dataset_id:
        query = query.filter(SavedChart.dataset_id == dataset_id)
    charts = query.order_by(SavedChart.position.asc(), SavedChart.created_at.desc()).all()
    return [SavedChartResponse.from_orm_model(c) for c in charts]


@router.post("", response_model=SavedChartResponse, status_code=status.HTTP_201_CREATED)
async def create_saved_chart(
    data: SavedChartCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Save a chart to the user's dashboard."""
    chart = SavedChart(
        user_id=current_user.id,
        dataset_id=data.dataset_id,
        mart_id=data.mart_id,
        title=data.title,
        chart_spec=data.chart_spec,
        rows_snapshot=data.rows,
        position=data.position,
    )
    db.add(chart)
    db.commit()
    db.refresh(chart)
    return SavedChartResponse.from_orm_model(chart)


@router.patch("/{chart_id}", response_model=SavedChartResponse)
async def update_saved_chart(
    chart_id: int,
    data: SavedChartUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Update a saved chart's title or position."""
    chart = (
        db.query(SavedChart)
        .filter(SavedChart.id == chart_id, SavedChart.user_id == current_user.id)
        .first()
    )
    if not chart:
        raise HTTPException(status_code=404, detail="Chart not found")
    if data.title is not None:
        chart.title = data.title
    if data.position is not None:
        chart.position = data.position
    db.commit()
    db.refresh(chart)
    return SavedChartResponse.from_orm_model(chart)


@router.delete("/{chart_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_saved_chart(
    chart_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Delete a saved chart."""
    chart = (
        db.query(SavedChart)
        .filter(SavedChart.id == chart_id, SavedChart.user_id == current_user.id)
        .first()
    )
    if not chart:
        raise HTTPException(status_code=404, detail="Chart not found")
    db.delete(chart)
    db.commit()


@router.delete("", status_code=status.HTTP_204_NO_CONTENT)
async def clear_saved_charts(
    dataset_id: Optional[str] = Query(None, description="Filter by dataset"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Clear all saved charts for the current user (optionally scoped to a dataset)."""
    query = db.query(SavedChart).filter(SavedChart.user_id == current_user.id)
    if dataset_id:
        query = query.filter(SavedChart.dataset_id == dataset_id)
    query.delete(synchronize_session=False)
    db.commit()
