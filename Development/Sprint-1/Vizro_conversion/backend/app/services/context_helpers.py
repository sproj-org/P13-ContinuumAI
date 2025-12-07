import json
from typing import Any, Dict
import pandas as pd


def column_stats(df: pd.DataFrame) -> Dict[str, Dict[str, Any]]:
    stats: Dict[str, Dict[str, Any]] = {}
    for col in df.columns:
        if pd.api.types.is_numeric_dtype(df[col]):
            stats[col] = {
                "type": "numeric",
                "mean": df[col].mean(),
                "median": df[col].median(),
                "std": df[col].std(),
                "count": int(df[col].count()),
                "min": df[col].min(),
                "max": df[col].max(),
            }
        else:
            top = df[col].astype(str).value_counts().head(5).to_dict()
            stats[col] = {"type": "categorical", "top_values": top}
    return stats


def dataset_summary_for_prompt(df: pd.DataFrame) -> str:
    cols = {c: str(df[c].dtype) for c in df.columns}
    sample_rows = df.head(5).to_dict(orient="records")
    stats = column_stats(df)
    lines = ["Columns:"]
    lines.extend(f"- {k}: {v}" for k, v in cols.items())
    lines.append("Sample rows:")
    lines.append(json.dumps(sample_rows, default=str))
    if stats:
        lines.append("Column statistics:")
        for name, info in stats.items():
            if info.get("type") == "numeric":
                lines.append(
                    f"- {name}: mean={info.get('mean'):.2f} median={info.get('median'):.2f} std={info.get('std'):.2f}"
                )
            else:
                top = info.get("top_values", {})
                pairs = ", ".join(f"{k} ({v})" for k, v in top.items())
                lines.append(f"- {name}: {pairs}")
    return "\n".join(lines)
