from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from typing import Optional

from app.db.database import get_db
from app.db.models import User, SavedChart, UserDashboard
from app.core.security import get_current_user
from app.schemas.dashboard import (
    SavedChartCreate,
    SavedChartUpdate,
    SavedChartResponse,
    UserDashboardCreate,
    UserDashboardUpdate,
    UserDashboardResponse,
)

saved_charts_router = APIRouter(prefix="/saved-charts", tags=["Saved Charts"])
dashboards_router = APIRouter(prefix="/dashboards", tags=["Dashboards"])


def _ensure_dashboard(db: Session, user_id: int, dataset_id: str, name: str) -> UserDashboard:
    normalized = name.strip() or "Default"
    existing = (
        db.query(UserDashboard)
        .filter(
            UserDashboard.user_id == user_id,
            UserDashboard.dataset_id == dataset_id,
            UserDashboard.name == normalized,
        )
        .first()
    )
    if existing:
        return existing

    dashboard = UserDashboard(user_id=user_id, dataset_id=dataset_id, name=normalized)
    db.add(dashboard)
    db.flush()
    return dashboard


@saved_charts_router.get("", response_model=list[SavedChartResponse])
async def list_saved_charts(
    dataset_id: Optional[str] = Query(None, description="Filter by dataset"),
    dashboard_name: Optional[str] = Query(None, description="Filter by dashboard name"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List all saved charts for the current user."""
    query = db.query(SavedChart).filter(SavedChart.user_id == current_user.id)
    if dataset_id:
        query = query.filter(SavedChart.dataset_id == dataset_id)
    if dashboard_name:
        query = query.filter(SavedChart.dashboard_name == dashboard_name)
    charts = query.order_by(SavedChart.dashboard_name.asc(), SavedChart.position.asc(), SavedChart.created_at.desc()).all()
    return [SavedChartResponse.from_orm_model(c) for c in charts]


@saved_charts_router.post("", response_model=SavedChartResponse, status_code=status.HTTP_201_CREATED)
async def create_saved_chart(
    data: SavedChartCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Save a chart to the user's dashboard."""
    normalized_dashboard = data.dashboard_name.strip() or "Default"
    _ensure_dashboard(db, current_user.id, data.dataset_id, normalized_dashboard)

    chart = SavedChart(
        user_id=current_user.id,
        dataset_id=data.dataset_id,
        dashboard_name=normalized_dashboard,
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


@saved_charts_router.patch("/{chart_id}", response_model=SavedChartResponse)
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
    if data.dashboard_name is not None:
        chart.dashboard_name = data.dashboard_name.strip() or "Default"
        _ensure_dashboard(db, current_user.id, chart.dataset_id, chart.dashboard_name)
    if data.position is not None:
        chart.position = data.position
    db.commit()
    db.refresh(chart)
    return SavedChartResponse.from_orm_model(chart)


@saved_charts_router.delete("/{chart_id}", status_code=status.HTTP_204_NO_CONTENT)
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


@saved_charts_router.delete("", status_code=status.HTTP_204_NO_CONTENT)
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


@dashboards_router.get("", response_model=list[UserDashboardResponse])
async def list_dashboards(
    dataset_id: Optional[str] = Query(None, description="Filter by dataset"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if dataset_id:
        _ensure_dashboard(db, current_user.id, dataset_id, "Default")
        db.commit()

    query = db.query(UserDashboard).filter(UserDashboard.user_id == current_user.id)
    if dataset_id:
        query = query.filter(UserDashboard.dataset_id == dataset_id)
    return query.order_by(UserDashboard.name.asc()).all()


@dashboards_router.post("", response_model=UserDashboardResponse, status_code=status.HTTP_201_CREATED)
async def create_dashboard(
    data: UserDashboardCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    dashboard = _ensure_dashboard(db, current_user.id, data.dataset_id, data.name)
    db.commit()
    db.refresh(dashboard)
    return dashboard


@dashboards_router.patch("/{dashboard_id}", response_model=UserDashboardResponse)
async def rename_dashboard(
    dashboard_id: int,
    data: UserDashboardUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    dashboard = (
        db.query(UserDashboard)
        .filter(UserDashboard.id == dashboard_id, UserDashboard.user_id == current_user.id)
        .first()
    )
    if not dashboard:
        raise HTTPException(status_code=404, detail="Dashboard not found")

    new_name = data.name.strip()
    if not new_name:
        raise HTTPException(status_code=400, detail="Dashboard name cannot be empty")

    existing = (
        db.query(UserDashboard)
        .filter(
            UserDashboard.user_id == current_user.id,
            UserDashboard.dataset_id == dashboard.dataset_id,
            UserDashboard.name == new_name,
            UserDashboard.id != dashboard.id,
        )
        .first()
    )
    if existing:
        raise HTTPException(status_code=409, detail="Dashboard with this name already exists")

    old_name = dashboard.name
    dashboard.name = new_name

    (
        db.query(SavedChart)
        .filter(
            SavedChart.user_id == current_user.id,
            SavedChart.dataset_id == dashboard.dataset_id,
            SavedChart.dashboard_name == old_name,
        )
        .update({SavedChart.dashboard_name: new_name}, synchronize_session=False)
    )

    db.commit()
    db.refresh(dashboard)
    return dashboard


@dashboards_router.delete("/{dashboard_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_dashboard(
    dashboard_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    dashboard = (
        db.query(UserDashboard)
        .filter(UserDashboard.id == dashboard_id, UserDashboard.user_id == current_user.id)
        .first()
    )
    if not dashboard:
        raise HTTPException(status_code=404, detail="Dashboard not found")

    (
        db.query(SavedChart)
        .filter(
            SavedChart.user_id == current_user.id,
            SavedChart.dataset_id == dashboard.dataset_id,
            SavedChart.dashboard_name == dashboard.name,
        )
        .delete(synchronize_session=False)
    )
    db.delete(dashboard)
    db.commit()


router = APIRouter()
router.include_router(saved_charts_router)
router.include_router(dashboards_router)
