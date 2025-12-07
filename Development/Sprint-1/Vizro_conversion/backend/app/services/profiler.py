from typing import Any, Dict, List
import pandas as pd


def profile_dataframe(df: pd.DataFrame) -> Dict[str, Any]:
    """Lightweight profiling to mirror vizro_app2 prompt grounding."""
    cols_types = {col: str(df[col].dtype) for col in df.columns}
    sample_rows = df.head(5).to_dict(orient="records")
    stats: Dict[str, Dict[str, Any]] = {}
    for col in df.columns:
        series = df[col]
        if pd.api.types.is_numeric_dtype(series):
            stats[col] = {
                "type": "numeric",
                "mean": series.mean(),
                "median": series.median(),
                "std": series.std(),
                "min": series.min(),
                "max": series.max(),
                "count": int(series.count()),
            }
        else:
            top = series.astype(str).value_counts().head(5).to_dict()
            stats[col] = {"type": "categorical", "top_values": top}
    return {"column_names_types": cols_types, "sample_rows": sample_rows, "stats": stats}
