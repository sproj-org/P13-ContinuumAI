from typing import Any, Dict, Optional
import pandas as pd
from sqlalchemy import text, create_engine
from app.core.config import get_settings

settings = get_settings()


def load_data(filters: Optional[Dict[str, Any]] = None) -> pd.DataFrame:
    filters = filters or {}
    # Try DB first
    try:
        engine = create_engine(settings.DATABASE_URL, future=True)
        where = []
        params = {}
        if filters.get("date_from"):
            where.append("order_date >= :date_from")
            params["date_from"] = filters["date_from"]
        if filters.get("date_to"):
            where.append("order_date <= :date_to")
            params["date_to"] = filters["date_to"]
        sql = f"SELECT * FROM {settings.DEMO_TABLE}"
        if where:
            sql += " WHERE " + " AND ".join(where)
        with engine.connect() as conn:
            df = pd.read_sql(text(sql), conn, params=params or None)
        return _apply_filters(df, filters)
    except Exception:
        pass

    # Fallback to CSV
    df = pd.read_csv(settings.CSV_PATH)
    return _apply_filters(df, filters)


def _apply_filters(df: pd.DataFrame, filters: Dict[str, Any]) -> pd.DataFrame:
    out = df.copy()
    # parse dates
    if "order_date" in out.columns:
        out["order_date"] = pd.to_datetime(out["order_date"], errors="coerce")
        if filters.get("date_from"):
            out = out[out["order_date"] >= pd.to_datetime(filters["date_from"])]
        if filters.get("date_to"):
            out = out[out["order_date"] <= pd.to_datetime(filters["date_to"])]

    # dynamic categorical filters: any key with list of values will be applied if column exists
    for key, vals in filters.items():
        if key in ("date_from", "date_to"):
            continue
        if isinstance(vals, list) and vals and key in out.columns:
            out = out[out[key].isin(vals)]
    return out


def list_filters(df: pd.DataFrame) -> Dict[str, list]:
    columns = []
    for col in df.columns:
        if df[col].dtype == object or str(df[col].dtype).startswith("category"):
            vals = sorted([v for v in df[col].dropna().unique().tolist() if v != ""])
            if vals:
                columns.append({"name": col, "values": vals})
    date_info = {}
    if "order_date" in df.columns:
        date_info = {
            "min_date": str(pd.to_datetime(df["order_date"]).min().date()),
            "max_date": str(pd.to_datetime(df["order_date"]).max().date()),
        }
    return {"columns": columns, **date_info}
