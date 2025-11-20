"""Data loading and caching utilities for Continuum v1."""
from __future__ import annotations

from pathlib import Path
from typing import Dict, Optional

import pandas as pd
import streamlit as st

from continuum_v1 import settings


def human_readable_size(num_bytes: int) -> str:
    if num_bytes < 1024:
        return f"{num_bytes} B"
    for unit in ["KB", "MB", "GB", "TB"]:
        num_bytes /= 1024.0
        if num_bytes < 1024:
            return f"{num_bytes:.1f} {unit}"
    return f"{num_bytes:.1f} PB"


def list_data_files() -> list[Path]:
    if not settings.DATA_DIR.exists():
        return []
    supported = {".csv", ".json", ".xls", ".xlsx", ".parquet"}
    files = [path for path in settings.DATA_DIR.iterdir() if path.is_file() and path.suffix.lower() in supported]
    return sorted(files, key=lambda p: p.name.lower())


def load_dataframe(dataset_path: Path) -> pd.DataFrame:
    suffix = dataset_path.suffix.lower()
    if suffix == ".csv":
        return pd.read_csv(dataset_path)
    if suffix in {".xls", ".xlsx"}:
        return pd.read_excel(dataset_path)
    if suffix == ".parquet":
        return pd.read_parquet(dataset_path)
    if suffix == ".json":
        return pd.read_json(dataset_path)
    raise ValueError(f"Unsupported data format: {suffix}")


@st.cache_data(show_spinner=False)
def load_dataframe_cached(path_str: str) -> pd.DataFrame:
    dataset_path = Path(path_str)
    return load_dataframe(dataset_path)


@st.cache_data(show_spinner=False)
def _compute_column_stats_cached(path_str: str) -> Dict[str, Dict[str, any]]:
    dataset_path = Path(path_str)
    try:
        df = load_dataframe_cached(path_str)
    except Exception:
        return {}
    stats: Dict[str, Dict[str, any]] = {}
    for col in df.columns:
        series = df[col]
        if pd.api.types.is_numeric_dtype(series):
            desc = series.describe()
            stats[col] = {
                "type": "numeric",
                "count": float(desc.get("count", 0)) if pd.notna(desc.get("count")) else None,
                "mean": float(desc.get("mean")) if pd.notna(desc.get("mean")) else None,
                "std": float(desc.get("std")) if pd.notna(desc.get("std")) else None,
                "min": float(desc.get("min")) if pd.notna(desc.get("min")) else None,
                "median": float(series.median()) if not series.empty else None,
                "max": float(desc.get("max")) if pd.notna(desc.get("max")) else None,
            }
        else:
            counts = series.astype(str).value_counts().head(10)
            stats[col] = {
                "type": "categorical",
                "top_values": counts.to_dict(),
            }
    return stats


def compute_column_stats(dataset_path: Path) -> Dict[str, Dict[str, any]]:
    return _compute_column_stats_cached(str(dataset_path))


def ensure_column_stats(dataset_path: Optional[Path]) -> None:
    if not dataset_path:
        return
    cache_key = "column_stats_cache_path"
    path_str = str(dataset_path)
    if st.session_state.get(cache_key) == path_str:
        return
    stats = compute_column_stats(dataset_path)
    st.session_state["column_stats"] = stats
    st.session_state[cache_key] = path_str


def infer_data_info(dataset_path: Path) -> Dict[str, any]:
    suffix = dataset_path.suffix.lower()
    readers = {
        ".csv": "pd.read_csv",
        ".json": "pd.read_json",
        ".xls": "pd.read_excel",
        ".xlsx": "pd.read_excel",
        ".parquet": "pd.read_parquet",
    }
    read_fn = readers.get(suffix, "pd.read_csv")
    return {
        "file_name": dataset_path.name,
        "file_path_or_url": dataset_path.resolve().as_posix(),
        "file_location_type": "local",
        "read_function_string": read_fn,
        "column_names_types": None,
    }
