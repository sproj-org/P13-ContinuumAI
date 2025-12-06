"""Application settings and constants for Continuum v1."""
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent

# Streamlit session keys
CURRENT_UPLOAD_KEY = "current_dataset_path"
CUSTOM_CHARTS_KEY = "custom_charts"
DASHBOARD_COMPONENTS_KEY = "dashboard_components"
DASHBOARD_VALIDATION_KEY = "dashboard_validation"
CHART_DATA_CACHE_KEY = "chart_data_cache"
CARD_COMPONENTS_KEY = "card_components"
FILTERS_KEY = "dashboard_filters"
LLM_HISTORY_KEY = "conversation_history"

# Paths
DATA_DIR = PROJECT_ROOT / "data"
PREVIEW_DIR = PROJECT_ROOT / ".vizro_preview"
PREVIEW_SCRIPT = PREVIEW_DIR / "app.py"
PREVIEW_PORT = 8051

DATA_DIR.mkdir(parents=True, exist_ok=True)
PREVIEW_DIR.mkdir(parents=True, exist_ok=True)

# UI constants
APP_TITLE = "Analytical Continuum"
APP_SUBTITLE = "Descriptive and Diagnostic Analysis"
