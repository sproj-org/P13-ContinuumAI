"""
In-memory state to mirror the Streamlit vizro_app2 session keys.
This is a lightweight replica to register charts/cards/filters during a run.
"""
from typing import Dict, List, Any

# Mirrors CUSTOM_CHARTS_KEY, CARD_COMPONENTS_KEY, DASHBOARD_COMPONENTS_KEY, FILTERS_KEY
CUSTOM_CHARTS: List[Dict[str, Any]] = []
CARD_COMPONENTS: List[Dict[str, Any]] = []
CARD_PLANS: List[Dict[str, Any]] = []
DASHBOARD_COMPONENTS: List[Dict[str, Any]] = []
FILTERS: List[Dict[str, Any]] = []
CHART_DATA_CACHE: Dict[str, Dict[str, Any]] = {}
LLM_HISTORY: List[Dict[str, str]] = []


def reset_state():
    CUSTOM_CHARTS.clear()
    CARD_COMPONENTS.clear()
    CARD_PLANS.clear()
    DASHBOARD_COMPONENTS.clear()
    FILTERS.clear()
    CHART_DATA_CACHE.clear()
    LLM_HISTORY.clear()
