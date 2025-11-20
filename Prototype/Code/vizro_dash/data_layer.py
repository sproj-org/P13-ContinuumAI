from __future__ import annotations

from pathlib import Path
from typing import Callable, Dict

import pandas as pd

PROJECT_CODE_DIR = Path(__file__).resolve().parent.parent
DATA_PATH = PROJECT_CODE_DIR / "backend" / "database" / "data" / "demo_sales.csv"


def load_sales_data(source: str | None = None, **kwargs) -> pd.DataFrame:
    """
    Load the dataset from the configured source without schema normalization.
    """

    loaders: Dict[str, Callable[..., pd.DataFrame]] = {
        "csv": _load_from_csv,
        "postgres": _load_from_postgres,
        "api": _load_from_api,
    }

    source_key = (source or "csv").lower()
    if source_key not in loaders:
        raise ValueError(f"Unsupported sales data source '{source_key}'.")

    return loaders[source_key](**kwargs)


def _load_from_csv(path: Path | None = None, **_: object) -> pd.DataFrame:
    """Load the raw CSV file exactly as provided."""
    csv_path = path or DATA_PATH
    df = pd.read_csv(csv_path)
    return df


def _load_from_postgres(**_: object) -> pd.DataFrame:
    """Placeholder for a future PostgreSQL implementation."""
    raise NotImplementedError("PostgreSQL data source not implemented yet.")


def _load_from_api(**_: object) -> pd.DataFrame:
    """Placeholder for a future API-based implementation."""
    raise NotImplementedError("API data source not implemented yet.")
