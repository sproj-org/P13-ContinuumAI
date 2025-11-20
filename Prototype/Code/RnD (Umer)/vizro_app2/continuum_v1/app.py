"""Streamlit scaffold for LLM-driven Vizro workflow (Stage 1: access + data ingestion)."""

from __future__ import annotations

import sys
from pathlib import Path

from dotenv import load_dotenv

PACKAGE_DIR = Path(__file__).resolve().parent
PACKAGE_PARENT = PACKAGE_DIR.parent
if str(PACKAGE_PARENT) not in sys.path:
    sys.path.insert(0, str(PACKAGE_PARENT))

load_dotenv(PACKAGE_DIR / ".env", override=False)

import asyncio
import contextlib
import html
import json
import os
import re
import subprocess
import time
from typing import Any, Dict, Optional

import pandas as pd
import requests
import streamlit as st
from openai import OpenAI

from panels.dataset_panel import (
    render_analysis_panel,
    render_dataset_confirmation_button,
    render_dataset_selector,
    render_selected_dataset_badge,
    run_analysis_for_dataset,
)
from llm.context import (
    COLUMN_SYNONYMS,
    detect_question_columns,
    dataset_summary_for_prompt,
    format_column_stats,
    generate_narrative_answer,
    infer_metric_column,
    map_column_name,
    needs_narrative_response,
    resolve_chart_name,
    resolve_column_for_dataframe,
)
from continuum_v1.settings import (
    CARD_COMPONENTS_KEY,
    CHART_DATA_CACHE_KEY,
    CURRENT_UPLOAD_KEY,
    CUSTOM_CHARTS_KEY,
    DASHBOARD_COMPONENTS_KEY,
    DASHBOARD_VALIDATION_KEY,
    DATA_DIR,
    FILTERS_KEY,
    LLM_HISTORY_KEY,
    PREVIEW_PORT,
)
from continuum_v1.services.data_loader import (
    compute_column_stats,
    ensure_column_stats,
    infer_data_info,
    load_dataframe,
    load_dataframe_cached,
)
from continuum_v1.services.vizro_client import (
    call_vizro,
    run_async,
    serialize_result,
    start_preview_process,
    stop_preview_process,
)


def ensure_api_key_loaded() -> Optional[str]:
    key = st.session_state.get("openai_key")
    if key:
        return key
    env_key = os.environ.get("OPENAI_API_KEY")
    if env_key:
        key = env_key.strip()
        st.session_state["openai_key"] = key
        return key
    return None

class ColumnResolutionError(Exception):
    """Raised when a requested column cannot be matched to the data."""


def _card_summary_line(markdown_text: str) -> str:
    """Convert the KPI markdown into a compact, single-line summary."""
    if not markdown_text:
        return ""
    segments = [seg.strip() for seg in markdown_text.splitlines() if seg.strip()]
    condensed = " — ".join(segments)
    condensed = re.sub(r"[#*`>]", "", condensed)
    return html.escape(condensed.strip())


# =============================================================================
# Streamlit styling snippets
# -----------------------------------------------------------------------------
# Embeds raw CSS so the chat widget stays compact regardless of the user's
# theme. For more on custom CSS in Streamlit see:
# https://docs.streamlit.io/knowledge-base/using-streamlit/how-do-i-use-themes-and-custom-css
# =============================================================================
CHAT_SCROLL_STYLE = """
<style>
.chat-scroll {
    max-height: 460px;
    overflow-y: auto;
    padding: 0.75rem;
    border: 1px solid rgba(128, 128, 128, 0.3);
    border-radius: 8px;
    background: rgba(255, 255, 255, 0.6);
}
.chat-bubble {
    margin-bottom: 0.6rem;
    padding: 0.55rem 0.85rem;
    border-radius: 6px;
    line-height: 1.35;
    font-size: 0.95rem;
}
.chat-bubble.user {
    background: #e3f2fd;
    color: #0b5394;
}
.chat-bubble.assistant {
    background: #f5f5f5;
    color: #2d3436;
}
.chat-empty {
    margin: 0;
    color: rgba(0, 0, 0, 0.6);
}
@media (prefers-color-scheme: dark) {
    .chat-scroll {
        background: rgba(20, 20, 20, 0.6);
        border-color: rgba(200, 200, 200, 0.2);
    }
    .chat-bubble.user {
        background: rgba(33, 150, 243, 0.25);
        color: #bbdefb;
    }
    .chat-bubble.assistant {
        background: rgba(255, 255, 255, 0.1);
        color: #eceff1;
    }
    .chat-empty {
        color: rgba(255, 255, 255, 0.7);
    }
}
</style>
"""

APP_STYLE = """
<style>
:root {
    --accent-color: #6c63ff;
    --surface-light: rgba(255, 255, 255, 0.9);
    --surface-dark: rgba(28, 33, 45, 0.9);
}
.stApp {
    background: linear-gradient(135deg, #0f1729 0%, #1d2435 45%, #060b13 100%);
}
.main > div {
    padding-top: 0.25rem;
}
.kpi-strip {
    margin: 0.15rem 0 0.25rem;
    padding: 0;
    border-radius: 0;
    border: none;
    background: transparent;
    box-shadow: none;
}
.kpi-strip h4 {
    margin-bottom: 0.15rem;
    color: #fafafa;
}
.kpi-strip p {
    color: rgba(255, 255, 255, 0.7);
    font-size: 0.9rem;
}
.kpi-card .card-text {
    font-size: 1rem;
}
.stretch-graph {
    padding: 0.5rem;
    width: 100%;
}
.section-card {
    border-radius: 0;
    padding: 0.25rem 0;
    margin-bottom: 0.25rem;
    background: transparent;
    border: none;
}
.section-card h5 {
    margin: 0;
}
.preview-callout {
    border-radius: 10px;
    padding: 0.65rem 0.85rem;
    background: rgba(255, 255, 255, 0.08);
    border: 1px solid rgba(255, 255, 255, 0.12);
    display: flex;
    gap: 1rem;
    justify-content: space-between;
    align-items: center;
    flex-wrap: wrap;
}
.preview-callout .stats {
    font-size: 0.9rem;
    color: rgba(255, 255, 255, 0.75);
}
.chip-row {
    display: flex;
    gap: 0.45rem;
    flex-wrap: wrap;
    margin-bottom: 0.35rem;
}
.chip {
    padding: 0.15rem 0.85rem;
    border-radius: 999px;
    border: 1px solid rgba(108, 99, 255, 0.4);
    color: #c5c1ff;
    font-size: 0.75rem;
    text-transform: uppercase;
    letter-spacing: 0.04em;
}
.filter-panel {
    font-size: 0.9rem;
    color: rgba(255, 255, 255, 0.85);
}
.filter-divider {
    border: 0;
    border-top: 1px solid rgba(255, 255, 255, 0.12);
    margin: 0.25rem 0 0.55rem;
}
.filter-item {
    font-size: 0.85rem;
    color: rgba(255, 255, 255, 0.8);
}
.remove-icon button {
    padding: 0.1rem 0.35rem;
}
.section-title {
    font-size: 1.25rem;
    margin: 0.35rem 0 0.05rem;
    color: rgba(255, 255, 255, 0.95);
}
.section-hint {
    margin-top: 0;
    color: rgba(255, 255, 255, 0.62);
    font-size: 0.92rem;
}
.metric-line {
    font-size: 0.95rem;
    margin: 0.15rem 0;
    display: flex;
    gap: 0.4rem;
    align-items: center;
}
.metric-line .metric-index {
    font-weight: 600;
    color: rgba(255, 255, 255, 0.85);
}
</style>
"""


# =============================================================================
# Runtime orchestration & Vizro MCP helpers
# -----------------------------------------------------------------------------
# These utilities wrap asyncio + subprocess calls to start/stop previews and
# invoke Vizro MCP tools. Vizro MCP CLI reference:
# https://github.com/mckinsey/vizro/tree/main/vizro-mcp
# =============================================================================
def map_column_name(raw_name: str) -> Optional[str]:
    analysis = st.session_state.get("analysis") or {}
    metadata = (analysis.get("df_metadata") or {}).get("column_names_types") or {}
    if not metadata:
        return None
    lowered = raw_name.lower()
    for actual in metadata.keys():
        if actual.lower() == lowered:
            return actual
        if actual.lower().replace(" ", "_") == lowered.replace(" ", "_"):
            return actual
    return None


def generate_narrative_answer(
    question: str,
    chart_title: str,
    summary_items: list[dict[str, Any]],
    filters: list[dict[str, str]],
    dataset_path: Path,
) -> str:
    api_key = st.session_state.get("openai_key")
    if not api_key:
        return "OpenAI key missing; cannot generate narrative."
    system_prompt = """
You are a senior data analyst. Given grouped summary values from a chart and the user's question, write a short paragraph (2-3 sentences) describing the insight. Reference specific group names and values. Do not request additional code.
""".strip()
    payload = {
        "chart_title": chart_title,
        "question": question,
        "filters": filters,
        "summary": summary_items,
    }
    try:
        client = OpenAI(api_key=api_key)
        resp = client.chat.completions.create(
            model="gpt-5-mini",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": json.dumps(payload)},
            ],
        )
        return resp.choices[0].message.content
    except Exception as exc:
        return f"Unable to generate narrative: {exc}"


def format_column_stats(stats: Dict[str, Any], limit: int = 5) -> str:
    if not stats:
        return "No column statistics available."
    lines = []
    for idx, (col, info) in enumerate(stats.items()):
        if idx >= 20:
            break
        if info.get("type") == "numeric":
            lines.append(
                f"{col}: count={info.get('count')}, mean={info.get('mean')}, median={info.get('median')}, min={info.get('min')}, max={info.get('max')}"
            )
        else:
            top = info.get("top_values", {})
            preview = ", ".join(f"{k} ({v})" for k, v in list(top.items())[:limit])
            lines.append(f"{col}: {preview}")
    return "\n".join(lines)



def _format_chart_context(chart_name: Optional[str], entry: Optional[Dict[str, Any]]) -> str:
    if not chart_name or not entry:
        return "No cached chart data available for this visualization."
    preview = entry.get("preview") or []
    limited_preview = preview[:50]
    payload = {
        "chart_name": chart_name,
        "columns": entry.get("columns") or [],
        "sample_rows": limited_preview,
        "px_function": entry.get("px_function"),
    }
    return json.dumps(payload, default=str)


def _compute_with_dataframe(df: pd.DataFrame, instructions: Dict[str, Any], question: str) -> Dict[str, Any]:
    working = df.copy()
    columns = list(working.columns)
    applied_filters: list[dict[str, str]] = []
    filters = instructions.get("filters") or []
    for f in filters:
        resolved = resolve_column_for_dataframe(str(f.get("column", "")), columns)
        if not resolved:
            raise ColumnResolutionError(f.get("column"))
        value = str(f.get("value", ""))
        working = working[working[resolved].astype(str).str.lower() == value.lower()]
        applied_filters.append({"column": resolved, "value": value})

    group_cols: list[str] = []
    for col in instructions.get("group_by") or []:
        resolved = resolve_column_for_dataframe(str(col), columns)
        if not resolved:
            raise ColumnResolutionError(col)
        group_cols.append(resolved)

    agg = (instructions.get("aggregation") or "count").lower()
    metric_column = None
    target_column = None
    summary: list[dict[str, Any]] = []

    if group_cols:
        grouped = working.groupby(group_cols)
        if agg in {"count", "none"}:
            metric_column = infer_metric_column(working)
            if metric_column:
                result = grouped[metric_column].sum().reset_index(name="value")
            else:
                result = grouped.size().reset_index(name="value")
        elif agg in {"sum", "avg"}:
            target_column = resolve_column_for_dataframe(str(instructions.get("target_column", "")), columns)
            if not target_column:
                raise ColumnResolutionError(instructions.get("target_column"))
            numeric = pd.to_numeric(working[target_column], errors="coerce")
            df_numeric = working.assign(_target=numeric)
            grouped = df_numeric.groupby(group_cols)
            if agg == "sum":
                result = grouped["_target"].sum().reset_index(name="value")
            else:
                result = grouped["_target"].mean().reset_index(name="value")
        else:
            raise ValueError(f"Unsupported aggregation '{agg}'")

        order = (instructions.get("order") or "desc").lower()
        ascending = order == "asc"
        result = result.sort_values(by="value", ascending=ascending)
        top_n = instructions.get("top_n")
        if isinstance(top_n, int) and top_n > 0:
            result = result.head(top_n)
        for _, row in result.iterrows():
            descriptor = ", ".join(f"{col}={row[col]}" for col in group_cols)
            summary.append({"descriptor": descriptor, "value": float(row["value"])})
    else:
        if agg in {"count", "none"}:
            metric_column = infer_metric_column(working)
            if metric_column:
                value = float(working[metric_column].sum())
                descriptor = metric_column
            else:
                value = float(len(working))
                descriptor = "records"
        elif agg in {"sum", "avg"}:
            target_column = resolve_column_for_dataframe(str(instructions.get("target_column", "")), columns)
            if not target_column:
                raise ColumnResolutionError(instructions.get("target_column"))
            numeric = pd.to_numeric(working[target_column], errors="coerce")
            if agg == "sum":
                value = float(numeric.sum())
                descriptor = f"sum_{target_column}"
            else:
                value = float(numeric.mean())
                descriptor = f"avg_{target_column}"
        else:
            raise ValueError(f"Unsupported aggregation '{agg}'")
        summary.append({"descriptor": descriptor, "value": value})

    return {
        "summary": summary,
        "applied_filters": applied_filters,
        "group_cols": group_cols,
        "aggregation": agg,
        "metric_column": metric_column,
        "target_column": target_column or metric_column,
    }


def _format_compute_answer(
    question: str,
    chart_title: str,
    dataset_path: Path,
    compute_result: Dict[str, Any],
) -> str:
    summary = compute_result.get("summary") or []
    group_cols = compute_result.get("group_cols") or []
    applied_filters = compute_result.get("applied_filters") or []
    agg = (compute_result.get("aggregation") or "count").lower()
    if group_cols and summary:
        if "which" in question.lower():
            top_entry = summary[0]
            return f"{top_entry['descriptor']} has {top_entry['value']:.0f}, the highest among the compared groups."
        if needs_narrative_response(question):
            return generate_narrative_answer(question, chart_title, summary, applied_filters, dataset_path)
        return " | ".join(f"{item['descriptor']}: {item['value']:.0f}" for item in summary)

    if not summary:
        return "No records matched the filters."

    descriptor = summary[0]["descriptor"]
    value = summary[0]["value"]
    target = compute_result.get("target_column") or descriptor
    if agg in {"count", "none"}:
        if descriptor == "records":
            return f"There are {value:.0f} records matching the filters."
        return f"The total {descriptor} is {value:.0f}."
    if agg == "sum":
        return f"The sum of {target} is {value:.2f}."
    if agg == "avg":
        return f"The average of {target} is {value:.2f}."
    return f"{descriptor}: {value}"


def wrap_components_for_layout(component_list: list[Dict[str, Any]]) -> list[Dict[str, Any]]:
    if component_list:
        return component_list
    return [
        {
            "type": "text",
            "id": "placeholder_message",
            "text": "No charts added yet. Use the LLM workflow to insert components.",
        }
    ]


def remove_chart_from_dashboard(comp: Dict[str, Any]) -> None:
    chart_target = (comp.get("figure") or {}).get("_target_")
    chart_name = comp.get("chart_name") or chart_target
    st.session_state[CUSTOM_CHARTS_KEY] = [
        chart for chart in st.session_state.get(CUSTOM_CHARTS_KEY, [])
        if chart.get("chart_name") != chart_target
    ]
    st.session_state[DASHBOARD_COMPONENTS_KEY] = [
        existing for existing in st.session_state.get(DASHBOARD_COMPONENTS_KEY, [])
        if existing.get("id") != comp.get("id")
    ]
    cache = st.session_state.get(CHART_DATA_CACHE_KEY)
    if cache and chart_name:
        cache.pop(chart_name, None)
    st.session_state["dashboard_dirty"] = True
    st.session_state[DASHBOARD_VALIDATION_KEY] = None


def remove_card_from_dashboard(comp: Dict[str, Any]) -> None:
    cards = st.session_state.get(CARD_COMPONENTS_KEY, [])
    st.session_state[CARD_COMPONENTS_KEY] = [card for card in cards if card.get("id") != comp.get("id")]
    st.session_state["dashboard_dirty"] = True
    st.session_state[DASHBOARD_VALIDATION_KEY] = None


def remove_filter_from_dashboard(filter_id: str) -> None:
    filters = st.session_state.get(FILTERS_KEY, [])
    st.session_state[FILTERS_KEY] = [flt for flt in filters if flt.get("id") != filter_id]
    st.session_state["dashboard_dirty"] = True
    st.session_state[DASHBOARD_VALIDATION_KEY] = None


# =============================================================================
# Chart & KPI execution utilities
# -----------------------------------------------------------------------------
# Capture Plotly calls emitted by LLM-generated code, run them against the
# selected dataset, and cache metadata for downstream Q&A. Plotly Express API:
# https://plotly.com/python-api-reference/plotly.express.html
# =============================================================================
def _build_px_proxy(px_module, captures: list[dict[str, Any]]):
    class PXProxy:
        def __getattr__(self, item):
            target = getattr(px_module, item)
            if not callable(target):
                return target

            def wrapper(*args, **kwargs):
                df_arg = None
                if "data_frame" in kwargs and isinstance(kwargs["data_frame"], pd.DataFrame):
                    df_arg = kwargs["data_frame"]
                elif args:
                    candidate = args[0]
                    if isinstance(candidate, pd.DataFrame):
                        df_arg = candidate
                if df_arg is not None:
                    try:
                        captures.append({"fn": item, "data": df_arg.copy()})
                    except Exception:
                        captures.append({"fn": item, "data": df_arg})
                return target(*args, **kwargs)

            return wrapper

    return PXProxy()


def _summarize_figure(fig) -> Dict[str, Any]:
    fig_json = fig.to_plotly_json()
    layout = fig_json.get("layout", {})
    xaxis = layout.get("xaxis") or {}
    yaxis = layout.get("yaxis") or {}
    traces = []
    for trace in fig_json.get("data", []):
        traces.append(
            {
                "name": trace.get("name"),
                "type": trace.get("type"),
                "points": len(trace.get("x") or trace.get("labels") or []),
            }
        )
    def _title_text(axis_dict):
        title = axis_dict.get("title")
        if isinstance(title, dict):
            return title.get("text")
        return title
    return {
        "chart_type": traces[0]["type"] if traces else None,
        "traces": traces,
        "xaxis_title": _title_text(xaxis),
        "yaxis_title": _title_text(yaxis),
    }


def _execute_chart_code(chart_plan: Dict[str, Any], dataset_path: Path) -> Optional[Dict[str, Any]]:
    chart_code = chart_plan.get("chart_code", "").strip()
    chart_name = chart_plan.get("chart_name")
    if not chart_code or not chart_name:
        return None
    namespace: Dict[str, Any] = {}
    imports = chart_plan.get("imports") or []
    for stmt in imports:
        exec(stmt, namespace)
    namespace.setdefault("pd", pd)
    captures: list[dict[str, Any]] = []
    px_module = namespace.get("px")
    if px_module is not None:
        namespace["px"] = _build_px_proxy(px_module, captures)
    exec(chart_code, namespace)
    func = namespace.get(chart_name)
    if not callable(func):
        raise ValueError(f"Chart function {chart_name} not found after executing chart code.")
    df = load_dataframe(dataset_path)
    fig = func(data_frame=df.copy())
    data_frame = df.copy()
    px_fn = None
    if captures:
        capture = captures[-1]
        data_frame = capture["data"].copy()
        px_fn = capture["fn"]
    summary = _summarize_figure(fig)
    preview = data_frame.head(min(200, len(data_frame))).to_dict(orient="records")
    return {
        "figure": fig,
        "data_frame": data_frame,
        "preview": preview,
        "columns": list(data_frame.columns),
        "px_function": px_fn,
        "summary": summary,
    }


def cache_chart_data(chart_plan: Dict[str, Any], dataset_path: Path) -> None:
    chart_name = chart_plan.get("chart_name")
    if not chart_name:
        return
    cache = st.session_state.setdefault(CHART_DATA_CACHE_KEY, {})
    try:
        result = _execute_chart_code(chart_plan, dataset_path)
    except Exception as exc:
        cache[chart_name] = {"error": f"Unable to cache chart data: {exc}"}
        return
    if not result:
        cache[chart_name] = {"error": "No chart data generated."}
        return
    cache[chart_name] = {
        "dataframe": result["data_frame"],
        "preview": result["preview"],
        "columns": result["columns"],
        "px_function": result["px_function"],
        "figure_summary": result["summary"],
    }


def _execute_card_code(card_plan: Dict[str, Any], dataset_path: Path) -> Dict[str, Any]:
    card_code = (card_plan.get("card_code") or "").strip()
    card_name = card_plan.get("card_name")
    if not card_code or not card_name:
        raise ValueError("Card plan must include 'card_name' and 'card_code'.")
    namespace: Dict[str, Any] = {}
    for stmt in card_plan.get("imports") or []:
        exec(stmt, namespace)
    namespace.setdefault("pd", pd)
    exec(card_code, namespace)
    func = namespace.get(card_name)
    if not callable(func):
        raise ValueError(f"Card function {card_name} not found after executing card code.")
    df = load_dataframe(dataset_path)
    result = func(data_frame=df.copy())
    if isinstance(result, str):
        return {"text": result}
    if isinstance(result, dict):
        return result
    raise ValueError("Card code must return Markdown text or a dict with card properties.")


def handle_card_plan(card_plan: Dict[str, Any], dataset_path: Path) -> str:
    try:
        payload = _execute_card_code(card_plan, dataset_path)
    except Exception as exc:
        return f"Card generation failed: {exc}"
    text = (payload.get("text") or "").strip()
    if not text:
        return "Card code must return a dictionary containing a 'text' field with Markdown content."
    card_name = card_plan.get("card_name", "custom_card")
    safe_name = re.sub(r"[^0-9a-zA-Z_]+", "_", card_name).strip("_") or "card"
    component_id = f"{safe_name}_card"
    card_component = {"type": "card", "id": component_id, "text": text}
    base_extra = dict(card_plan.get("extra") or {})
    style = dict(base_extra.get("style") or {})
    style.setdefault("textAlign", "center")
    style.setdefault("display", "flex")
    style.setdefault("flexDirection", "column")
    style.setdefault("justifyContent", "center")
    style.setdefault("alignItems", "center")
    style.setdefault("minHeight", "140px")
    style.setdefault("flex", "1 1 calc(50% - 12px)")
    style.setdefault("minWidth", "240px")
    base_extra["style"] = style
    default_class = "card-nav" if card_component.get("href") else ""
    existing_class = base_extra.get("className") or default_class
    base_extra["className"] = (existing_class + " text-center kpi-card").strip()
    card_component["extra"] = base_extra
    if payload.get("href"):
        card_component["href"] = payload["href"]
    cards = st.session_state.setdefault(CARD_COMPONENTS_KEY, [])
    cards = [card for card in cards if card.get("id") != component_id]
    cards.append(card_component)
    st.session_state[CARD_COMPONENTS_KEY] = cards
    st.session_state[DASHBOARD_VALIDATION_KEY] = None
    st.session_state["dashboard_dirty"] = True
    return "Card added to dashboard components. Validate the dashboard config to include it in the Vizro code."


# =============================================================================
# Streamlit UI rendering
# -----------------------------------------------------------------------------
# Everything below wires the utilities into visible panels: sidebar data
# controls, dashboard builder, preview controls, and the chat surface. Streamlit
# layout primitives reference: https://docs.streamlit.io/library/api-reference/layout
# =============================================================================
def build_filter_controls() -> list[Dict[str, Any]]:
    """Convert session-stored filters into Vizro filter definitions."""
    filters = st.session_state.get(FILTERS_KEY, [])
    controls: list[Dict[str, Any]] = []
    for idx, flt in enumerate(filters, start=1):
        controls.append(
            {
                "type": "filter",
                "id": flt.get("id") or f"filter_{idx}",
                "column": flt["column"],
                "targets": flt.get("targets") or [],
                "show_in_url": flt.get("show_in_url", False),
                "visible": flt.get("visible", True),
                "selector": {
                    "type": "dropdown",
                    "title": flt.get("label") or flt["column"].replace("_", " ").title(),
                    "multi": flt.get("multi", True),
                },
            }
        )
    return controls


def render_filter_builder(
    dataset_path: Path,
    chart_components: list[Dict[str, Any]],
    card_components: list[Dict[str, Any]],
) -> None:
    filters = st.session_state.setdefault(FILTERS_KEY, [])
    stats = st.session_state.get("column_stats") or {}
    available_columns = sorted(stats.keys())
    component_options = []
    for comp in chart_components + card_components:
        component_options.append(
            {
                "id": comp.get("id"),
                "label": comp.get("title") or comp.get("id", "component"),
            }
        )

    with st.expander("Filters & cross-filtering", expanded=bool(filters)):
        st.markdown("<div class='filter-panel'>", unsafe_allow_html=True)
        st.caption(
            "Create page-level filters so viewers can slice multiple charts simultaneously. "
            "Each filter operates on a dataset column and targets the charts/cards you select."
        )
        if not available_columns:
            st.info("Load a dataset to configure filters.")

        if filters:
            st.markdown("**Existing filters**")
            for flt in filters:
                targets_raw = flt.get("targets") or []
                targets_pretty = [opt["label"] for opt in component_options if opt["id"] in targets_raw]
                if not targets_pretty:
                    targets_pretty = ["All charts"]
                row = st.columns([0.9, 0.1])
                with row[0]:
                    st.markdown(
                        f"<div class='filter-item'><strong>{flt.get('label', flt['column'])}</strong> · {flt['column']} → {', '.join(targets_pretty)}</div>",
                        unsafe_allow_html=True,
                    )
                with row[1]:
                    if st.button("✕", key=f"remove_filter_{flt['id']}", help="Remove filter"):
                        remove_filter_from_dashboard(flt["id"])
                        st.session_state["dashboard_dirty"] = True
                        st.session_state[DASHBOARD_VALIDATION_KEY] = None
                        st.rerun()
            st.markdown("<hr class='filter-divider' />", unsafe_allow_html=True)

        if not available_columns:
            st.markdown("</div>", unsafe_allow_html=True)
            return

        with st.form("add_filter_form", clear_on_submit=True):
            column = st.selectbox("Column to filter", options=available_columns)
            default_label = f"{column.replace('_', ' ').title()} filter"
            label = st.text_input("Filter label", value=default_label)
            multi = st.checkbox("Allow multi-select", value=True)
            show_in_url = st.checkbox("Show value in URL", value=False)
            target_ids = [opt["id"] for opt in component_options if opt["id"]]
            defaults = target_ids[:]
            target_labels = {opt["id"]: f"{opt['id']} · {opt['label']}" for opt in component_options if opt["id"]}
            selected_targets_labels = st.multiselect(
                "Apply to components",
                options=list(target_labels.keys()),
                format_func=lambda comp_id: target_labels.get(comp_id, comp_id),
                default=defaults,
                help="Choose the charts/cards that should respond to this filter.",
            )
            submitted = st.form_submit_button("Add filter", use_container_width=True)
            if submitted:
                filter_id = f"filter_{len(filters) + 1}_{column}"
                filters.append(
                    {
                        "id": filter_id,
                        "column": column,
                        "label": label or column,
                        "multi": multi,
                        "targets": selected_targets_labels,
                        "show_in_url": show_in_url,
                        "visible": True,
                    }
                )
                st.session_state[FILTERS_KEY] = filters
                st.session_state["dashboard_dirty"] = True
                st.session_state[DASHBOARD_VALIDATION_KEY] = None
                st.success(f"Added filter '{label or column}'.")
                st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)


def render_dashboard_panel(dataset_path: Optional[Path]) -> None:
    st.markdown("<h3 class='section-title'>Dashboard scaffold</h3>", unsafe_allow_html=True)
    st.markdown(
        "<p class='section-hint'>Design KPIs and visuals, then validate to generate production-ready Vizro code.</p>",
        unsafe_allow_html=True,
    )
    if not dataset_path:
        st.info("Confirm a dataset to start building the dashboard.")
        return
    ensure_column_stats(dataset_path)

    st.session_state.setdefault(CUSTOM_CHARTS_KEY, [])
    st.session_state.setdefault(DASHBOARD_COMPONENTS_KEY, [])
    st.session_state.setdefault(CARD_COMPONENTS_KEY, [])
    valid_chart_names = {chart.get("chart_name") for chart in st.session_state[CUSTOM_CHARTS_KEY]}
    filtered_components = []
    for comp in st.session_state[DASHBOARD_COMPONENTS_KEY]:
        target = (comp.get("figure") or {}).get("_target_")
        if target in valid_chart_names:
            comp.pop("chart_name", None)
            filtered_components.append(comp)
    st.session_state[DASHBOARD_COMPONENTS_KEY] = filtered_components

    title = st.text_input("Dashboard title", value=st.session_state.get("dashboard_title", "My Vizro Dashboard"))
    page_title = st.text_input("Page title", value=st.session_state.get("dashboard_page_title", "Overview"))
    theme = st.selectbox("Theme", options=["vizro_dark", "vizro_light"], index=0)

    st.session_state["dashboard_title"] = title
    st.session_state["dashboard_page_title"] = page_title
    st.session_state["dashboard_theme"] = theme

    card_components = st.session_state.get(CARD_COMPONENTS_KEY, [])
    chart_components = st.session_state.get(DASHBOARD_COMPONENTS_KEY, [])

    for comp in card_components + chart_components:
        extra = comp.get("extra")
        if isinstance(extra, dict) and "class_name" in extra:
            extra["className"] = extra.pop("class_name")

    render_filter_builder(dataset_path, chart_components, card_components)
    with st.expander("Current components", expanded=bool(card_components or chart_components)):
        if not card_components and not chart_components:
            st.info("No charts or cards added yet. Use the LLM conversation panel to create them.")
        else:
            if card_components:
                st.markdown("**Key metrics**")
                for idx, comp in enumerate(card_components, start=1):
                    cols = st.columns([0.94, 0.06])
                    summary = _card_summary_line(comp.get("text", "")) or "Untitled metric"
                    with cols[0]:
                        st.markdown(
                            f"<div class='metric-line'><span class='metric-index'>{idx}.</span><span>{summary}</span></div>",
                            unsafe_allow_html=True,
                        )
                    with cols[1]:
                        if st.button("✕", key=f"remove_card_{comp['id']}", help="Remove card"):
                            remove_card_from_dashboard(comp)
                            st.session_state[DASHBOARD_VALIDATION_KEY] = None
                            st.rerun()
            if chart_components:
                st.markdown("**Charts**")
                for idx, comp in enumerate(chart_components, start=1):
                    st.markdown("<div class='section-card'>", unsafe_allow_html=True)
                    block = st.container()
                    header_cols = block.columns([0.94, 0.06])
                    with header_cols[0]:
                        label = comp.get("title") or comp.get("id", "component")
                        st.write(f"{idx}. {label}")
                    with header_cols[1]:
                        if st.button("✕", key=f"remove_chart_{comp['id']}", help="Remove chart"):
                            remove_chart_from_dashboard(comp)
                            st.session_state[DASHBOARD_VALIDATION_KEY] = None
                            st.rerun()
                    question_input_key = f"question_{comp['id']}"
                    reset_key = f"{question_input_key}_reset"
                    if st.session_state.get(reset_key):
                        st.session_state[question_input_key] = ""
                        st.session_state.pop(reset_key, None)
                    q_cols = block.columns([5, 1])
                    question_placeholder = f"Ask about '{comp.get('title', comp.get('id', 'chart'))}'"
                    question = q_cols[0].text_input(
                        label=question_placeholder,
                        key=question_input_key,
                        label_visibility="collapsed",
                        placeholder=question_placeholder,
                    )
                    if q_cols[1].button("Ask", key=f"ask_{comp['id']}"):
                        if question.strip():
                            history = st.session_state.setdefault(LLM_HISTORY_KEY, [])
                            prompt = f"Question about chart '{comp.get('title', comp.get('id', 'chart'))}': {question.strip()}"
                            history.append({"role": "user", "content": prompt})
                            answer_chart_question(question, comp.get("title") or comp["id"], dataset_path, history)
                            st.session_state[reset_key] = True
                            st.rerun()
                        else:
                            st.warning("Enter a question before asking.")
                    st.markdown("</div>", unsafe_allow_html=True)

    data_info = infer_data_info(dataset_path)
    filter_controls = build_filter_controls()
    layout_components: list[Dict[str, Any]] = []
    if card_components:
        layout_components.append(
            {
                "type": "container",
                "id": "kpi_card_wrap",
                "layout": {
                    "type": "flex",
                    "direction": "row",
                    "wrap": True,
                    "gap": "16px",
                },
                "components": card_components,
            }
        )
    if chart_components:
        layout_components.append(
            {
                "type": "container",
                "id": "chart_wrap",
                "layout": {
                    "type": "flex",
                    "direction": "column",
                    "wrap": False,
                    "gap": "24px",
                },
                "components": chart_components,
            }
        )
    components_for_validation = wrap_components_for_layout(layout_components)

    dashboard_config = {
        "title": title,
        "theme": theme,
        "pages": [
            {
                "title": page_title,
                "controls": filter_controls,
                "components": [
                    {
                        "type": "container",
                        "id": "flex_wrapper",
                        "layout": {
                            "type": "flex",
                            "direction": "column",
                            "wrap": False,
                        },
                        "components": components_for_validation,
                    }
                ],
            }
        ],
    }

    validation = st.session_state.get(DASHBOARD_VALIDATION_KEY)
    dirty = st.session_state.get("dashboard_dirty", True)
    if st.session_state.pop("run_validation", False):
        args = {
            "dashboard_config": dashboard_config,
            "data_infos": [data_info],
            "custom_charts": st.session_state.get(CUSTOM_CHARTS_KEY, []),
            "auto_open": False,
        }
        with st.spinner("Validating via Vizro MCP..."):
            result = run_async(call_vizro("validate_dashboard_config", args))
            st.session_state[DASHBOARD_VALIDATION_KEY] = serialize_result(result)
            st.session_state["dashboard_dirty"] = False
        validation = st.session_state.get(DASHBOARD_VALIDATION_KEY)
        dirty = st.session_state.get("dashboard_dirty", True)
        st.session_state["open_preview_after_validation"] = True

    if not dirty and validation:
        st.caption("No changes since last validation.")
    if st.button("Validate & preview dashboard"):
        st.session_state["run_validation"] = True
        st.rerun()

    if validation:
        if validation.get("python_code"):
            st.success("Dashboard validated.")
            with st.expander("Generated Python code", expanded=False):
                st.text_area("Generated Python code", value=validation.get("python_code", ""), height=240)
        elif validation.get("error"):
            st.error(validation.get("error"))
        else:
            st.warning("Validation returned no code or error details.")
    else:
        st.caption("Validate to see generated Vizro code here.")
        st.session_state["preview_active"] = False

    preview_link = None
    if st.session_state.pop("open_preview_after_validation", False) and validation and validation.get("python_code"):
        code = validation.get("python_code")
        if code:
            start_preview_process(code)
            preview_link = f"http://127.0.0.1:{PREVIEW_PORT}"
    render_preview_section(validation, preview_link)


def render_preview_section(validation: Optional[Dict[str, Any]], open_preview_link: Optional[str]) -> None:
    st.markdown("### Dashboard preview")
    if not validation:
        st.caption("Validate the dashboard to enable preview controls.")
        return
    card_count = len(st.session_state.get(CARD_COMPONENTS_KEY, []))
    chart_count = len(st.session_state.get(DASHBOARD_COMPONENTS_KEY, []))
    st.markdown(
        f"<div class='preview-callout'><div><strong>Dashboard validated</strong>"
        f"<div class='stats'>Cards: {card_count} · Charts: {chart_count}</div></div></div>",
        unsafe_allow_html=True,
    )
    preview_error = st.session_state.get("preview_error")
    if preview_error:
        st.error(f"Preview failed: {preview_error}")
    if open_preview_link:
        st.markdown(f"[Open preview ↗]({open_preview_link})", unsafe_allow_html=True)
    if st.session_state.get("preview_active"):
        if st.button("Stop preview", key="stop_preview"):
            stop_preview_process()


def build_chat_history_html(history: list[Dict[str, str]]) -> str:
    if not history:
        return "<div class='chat-scroll'><p class='chat-empty'>No conversation yet. Ask a question to get started.</p></div>"
    rows = []
    for entry in history[-60:]:
        role = entry.get("role", "assistant")
        css_role = "user" if role == "user" else "assistant"
        role_label = "You" if role == "user" else "Assistant"
        content = entry.get("content", "")
        safe = html.escape(content).replace("\n", "<br/>")
        rows.append(
            f"<div class='chat-bubble {css_role}'><strong>{role_label}:</strong> <span class='chat-text'>{safe}</span></div>"
        )
    return "<div class='chat-scroll'>" + "".join(rows) + "</div>"


# =============================================================================
# LLM prompt construction & parsing
# -----------------------------------------------------------------------------
# Compile dataset summaries and enforce JSON schemas so Vizro MCP + OpenAI
# produce deterministic chart/card plans. Helpful references:
#   https://platform.openai.com/docs/guides/function-calling
#   https://vizro.readthedocs.io/projects/vizro-mcp/en/latest/tools/overview.html
# =============================================================================
def dataset_summary_for_prompt(dataset_path: Path) -> str:
    analysis = st.session_state.get("analysis") or {}
    df_info = analysis.get("df_info") or {}
    metadata = analysis.get("df_metadata") or {}
    general = df_info.get("general_info") or ""
    sample = df_info.get("sample") or {}
    lines = []
    if general:
        lines.append(general.strip())
    if sample:
        lines.append("Sample columns:")
        for name in list(sample.keys())[:6]:
            lines.append(f"- {name}")
    cols = metadata.get("column_names_types")
    if cols:
        lines.append("Actual columns and inferred types:\n" + "\n".join(f"- {name}: {ctype}" for name, ctype in cols.items()))
    stats = st.session_state.get("column_stats")
    if stats:
        lines.append("Column statistics:\n" + format_column_stats(stats))
    if not lines:
        lines.append(f"Dataset path: {dataset_path}")
    return "\n".join(lines)


def build_system_prompt(dataset_path: Path) -> str:
    summary = dataset_summary_for_prompt(dataset_path)
    return f"""
You are Vizro MCP's LLM assistant. Help the user design charts and dashboards from the dataset located at {dataset_path}.
Dataset summary:
{summary}

Always respond with valid JSON of the form:
{{
  "reply": "natural language guidance",
  "chart_plan": {{
      "chart_type": "...",
      "chart_name": "snake_case",
      "imports": ["import pandas as pd", "import plotly.express as px"],
      "chart_code": "def chart_name(data_frame): ...\n    return fig"
  }} | null,
  "card_plan": {{
      "card_name": "snake_case",
      "imports": ["import pandas as pd"],
      "card_code": "def card_name(data_frame): ...\n    return {{'text': '### KPI\n42%'}}"
  }} | null
}}

Use `card_plan` for KPI-style summaries that should appear above the charts. The `card_code` function must accept `data_frame` and return either Markdown text (string) or a dict containing at least a `text` field. Optional keys such as `href` are allowed. Keep each card focused on a single scalar metric derived from the dataset and format the Markdown text with the computed value.

If `px.pie` is used, ALWAYS include an explicit `data_frame=` argument (e.g., aggregate into a small DataFrame as `chart_df` and call `px.pie(data_frame=chart_df, names=..., values=...)`).
When preparing aggregated data, ensure every column name is unique (e.g., use `rename` or distinct column names instead of duplicating `count`). If you create `chart_df = ...value_counts().reset_index()`, rename both columns explicitly (e.g., `chart_df.columns = ["nationality", "count"]`).
Never set Plotly templates or background colors (omit `template=` arguments and let Vizro themes handle styling).
The dataset column names listed above are the source of truth. When the user mentions a column concept ("employment type", "nationalities", etc.), map it to the actual column name from that list (case-insensitive match, e.g., `emp_type`, `nationality`). Always reference the exact column spelling from the dataset in the generated code.

If no visual should be generated, set both plan entries to null. When producing code, follow Vizro chart guidelines, use the provided data_frame argument, and rely on pandas/plotly express for charts or pandas computations for KPI cards.
""".strip()


def parse_llm_response(raw: str) -> Dict[str, Any]:
    text = raw.strip()
    if text.startswith("```"):
        parts = text.split("```", 2)
        if len(parts) >= 2:
            text = parts[1]
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return {"reply": raw, "chart_plan": None, "card_plan": None}
    return {
        "reply": data.get("reply", raw),
        "chart_plan": data.get("chart_plan"),
        "card_plan": data.get("card_plan"),
    }


def extract_json(raw: str) -> Dict[str, Any]:
    text = raw.strip()
    if text.startswith("```"):
        parts = text.split("```", 2)
        if len(parts) >= 2:
            text = parts[1]
    return json.loads(text)


def px_pie_missing_dataframe(code: str) -> bool:
    pattern = re.compile(r"px\.pie\s*\((.*?)\)", re.DOTALL)
    for match in pattern.finditer(code):
        args = match.group(1)
        if "data_frame" not in args:
            return True
    return False


def px_violin_uses_opacity(code: str) -> bool:
    pattern = re.compile(r"px\.violin\s*\((.*?)\)", re.DOTALL)
    for match in pattern.finditer(code):
        if "opacity" in match.group(1):
            return True
    return False


TEMPLATE_ASSIGNMENT_PATTERN = re.compile(r"\s*template\s*=\s*['\"][^'\"]*['\"]\s*,?")


def strip_plotly_templates(code: str) -> str:
    cleaned = TEMPLATE_ASSIGNMENT_PATTERN.sub("", code)
    cleaned = re.sub(r"\.template\s*=\s*['\"][^'\"]*['\"]", "", cleaned)
    return cleaned


def handle_chart_plan(chart_plan: Dict[str, Any], dataset_path: Path) -> str:
    chart_code = chart_plan.get("chart_code", "")
    sanitized_code = strip_plotly_templates(chart_code)
    if sanitized_code != chart_code:
        chart_plan = dict(chart_plan)
        chart_plan["chart_code"] = sanitized_code
    if px_pie_missing_dataframe(chart_plan.get("chart_code", "")):
        return (
            "Chart rejected: px.pie must include a `data_frame` argument (e.g., `px.pie(data_frame=chart_df, ...)`). "
            "Please update the code and try again."
        )
    if px_violin_uses_opacity(chart_plan.get("chart_code", "")):
        return (
            "Chart rejected: Vizro currently disallows the `opacity` argument on `px.violin`. "
            "Please remove it (or ask the LLM to omit opacity) and try again."
        )

    data_info = infer_data_info(dataset_path)
    cache_bucket = st.session_state.setdefault("chart_validation_cache", {})
    cache_key = f"{chart_plan.get('chart_name')}::{hash(chart_plan.get('chart_code', ''))}::{data_info['file_name']}"
    struct = cache_bucket.get(cache_key)
    if not struct:
        try:
            args = {
                "chart_config": chart_plan,
                "data_info": data_info,
                "auto_open": False,
            }
            result = run_async(call_vizro("validate_chart_code", args))
            struct = serialize_result(result)
            cache_bucket[cache_key] = struct
        except Exception as exc:
            return f"Chart validation failed: {exc}"
    message = struct.get("message", "Chart validated.")

    custom_charts = st.session_state.setdefault(CUSTOM_CHARTS_KEY, [])
    custom_charts = [c for c in custom_charts if c.get("chart_name") != chart_plan.get("chart_name")]
    custom_charts.append(chart_plan)
    st.session_state[CUSTOM_CHARTS_KEY] = custom_charts

    components = st.session_state.setdefault(DASHBOARD_COMPONENTS_KEY, [])
    components = [comp for comp in components if comp.get("id") != f"{chart_plan['chart_name']}_component"]
    components.append(
        {
            "type": "graph",
            "id": f"{chart_plan['chart_name']}_component",
            "title": chart_plan["chart_name"].replace("_", " ").title(),
            "figure": {
                "_target_": chart_plan["chart_name"],
                "data_frame": data_info["file_name"],
            },
            "extra": {
                "style": {
                    "flex": "1 1 100%",
                    "width": "100%",
                    "minWidth": "100%",
                    "height": "100%",
                },
                "className": "stretch-graph",
            },
        }
    )
    st.session_state[DASHBOARD_COMPONENTS_KEY] = components
    st.session_state[DASHBOARD_VALIDATION_KEY] = None
    st.session_state["dashboard_dirty"] = True

    cache_chart_data(chart_plan, dataset_path)

    return message + " Chart added to dashboard components."


# =============================================================================
# LLM orchestration pipeline
# -----------------------------------------------------------------------------
# Handle user prompts end-to-end: call OpenAI, interpret JSON tools, and route
# the result to Vizro MCP validators. This is where we can plug additional
# skills (SQL, KPI cards, etc.). Background:
# https://docs.streamlit.io/library/api-reference/chat/st.chat_input
# =============================================================================
def handle_llm_interaction(
    user_prompt: str,
    dataset_path: Path,
    history: list[Dict[str, str]],
    show_messages: bool = True,
) -> None:
    api_key = st.session_state.get("openai_key")
    if not api_key:
        warning = "OpenAI key missing; cannot contact GPT-5-mini."
        history.append({"role": "assistant", "content": warning})
        if show_messages:
            with st.chat_message("assistant"):
                st.markdown(warning)
        return

    messages = [{"role": "system", "content": build_system_prompt(dataset_path)}]
    messages.extend({"role": entry["role"], "content": entry["content"]} for entry in history)

    try:
        client = OpenAI(api_key=api_key)
        spinner = st.spinner("Waiting for GPT-5-mini...") if show_messages else contextlib.nullcontext()
        with spinner:
            resp = client.chat.completions.create(model="gpt-5-mini", messages=messages)
        raw_content = resp.choices[0].message.content
    except Exception as exc:
        error_text = f"Failed to call GPT-5-mini: {exc}"
        history.append({"role": "assistant", "content": error_text})
        if show_messages:
            with st.chat_message("assistant"):
                st.markdown(error_text)
        return

    parsed = parse_llm_response(raw_content)
    reply_text = parsed.get("reply", raw_content)
    history.append({"role": "assistant", "content": reply_text})
    if show_messages:
        with st.chat_message("assistant"):
            st.markdown(reply_text)

    chart_plan = parsed.get("chart_plan")
    if chart_plan:
        outcome = handle_chart_plan(chart_plan, dataset_path)
        history.append({"role": "assistant", "content": outcome})
        if show_messages:
            with st.chat_message("assistant"):
                st.markdown(outcome)

    card_plan = parsed.get("card_plan")
    if card_plan:
        outcome = handle_card_plan(card_plan, dataset_path)
        history.append({"role": "assistant", "content": outcome})
        if show_messages:
            with st.chat_message("assistant"):
                st.markdown(outcome)


def answer_chart_question(question: str, chart_title: str, dataset_path: Path, history: list[Dict[str, str]]) -> None:
    api_key = st.session_state.get("openai_key")
    if not api_key:
        warning = "OpenAI key missing; cannot contact GPT-5-mini."
        history.append({"role": "assistant", "content": warning})
        return

    chart_name = resolve_chart_name(chart_title)
    chart_cache_entry = None
    if chart_name:
        chart_cache_entry = (st.session_state.get(CHART_DATA_CACHE_KEY) or {}).get(chart_name)
    chart_context = _format_chart_context(chart_name, chart_cache_entry)

    ensure_column_stats(dataset_path)
    stats_text = format_column_stats(st.session_state.get("column_stats") or {})
    system_prompt = f"""
You are a data analyst with access to the dataset and a cached table extracted from the user's chart.
Chart data context (sampled rows):
{chart_context}

Decide how to answer:
1. If the chart context already contains the answer, respond with:
   {{"mode": "chart_data", "answer": "..."}}
2. If the user wants a written explanation, respond with:
   {{"mode": "narrative", "answer": "..."}}
3. Only if you still need raw dataset computations, respond with:
   {{
     "mode": "compute",
     "filters": [{{"column": "...", "value": "..."}}],
     "group_by": ["col_a", "col_b"],
     "aggregation": "count" | "sum" | "avg" | "none",
     "target_column": "..." (required for sum/avg),
     "order": "desc" | "asc",
     "top_n": 1
   }}
4. If the required columns truly do not exist, respond with:
   {{"mode": "explain", "reason": "..."}}

When using chart data, reference the exact column names shown above (case-insensitive). Prefer the chart data whenever possible.

Dataset summary (use these columns if you must compute from the full dataset):
{dataset_summary_for_prompt(dataset_path)}

Column statistics:
{stats_text}

Return ONLY JSON.
""".strip()

    user_prompt = f"Chart: {chart_title}\nQuestion: {question.strip()}"
    try:
        client = OpenAI(api_key=api_key)
        resp = client.chat.completions.create(
            model="gpt-5-mini",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        )
        instructions = extract_json(resp.choices[0].message.content)
    except Exception as exc:
        history.append({"role": "assistant", "content": f"Failed to interpret question: {exc}"})
        return

    mode = (instructions.get("mode") or "").lower()
    if mode in {"chart_data", "narrative"}:
        answer = instructions.get("answer") or instructions.get("reason") or "No answer provided."
        history.append({"role": "assistant", "content": answer})
        return

    if mode == "explain":
        reason = instructions.get("reason") or "I do not have enough information to answer that."
        history.append({"role": "assistant", "content": reason})
        return

    if mode != "compute":
        history.append({"role": "assistant", "content": "Unable to process the question; unexpected response from LLM."})
        return

    candidate_frames: list[tuple[str, pd.DataFrame]] = []
    if chart_cache_entry and isinstance(chart_cache_entry.get("dataframe"), pd.DataFrame):
        candidate_frames.append(("chart cache", chart_cache_entry["dataframe"].copy()))
    dataset_error = None
    try:
        candidate_frames.append(("dataset", load_dataframe(dataset_path)))
    except Exception as exc:
        dataset_error = str(exc)

    missing_columns: list[str] = []
    last_error = None
    for label, candidate_df in candidate_frames:
        try:
            compute_result = _compute_with_dataframe(candidate_df.copy(), instructions, question)
        except ColumnResolutionError as exc:
            missing_columns.append(str(exc) if exc.args else "unknown column")
            continue
        except Exception as exc:
            last_error = f"{label} computation failed: {exc}"
            break

        answer = _format_compute_answer(question, chart_title, dataset_path, compute_result)
        history.append({"role": "assistant", "content": answer})
        return

    if last_error:
        history.append({"role": "assistant", "content": last_error})
        return

    if missing_columns:
        cols = sorted({col for col in missing_columns if col})
        history.append(
            {"role": "assistant", "content": f"Unable to answer because the column(s) {', '.join(cols)} were not found in the chart data or dataset."}
        )
        return

    if dataset_error:
        history.append({"role": "assistant", "content": f"Could not load dataset for computation: {dataset_error}."})
        return

    history.append({"role": "assistant", "content": "Computation instructions unclear; please rephrase the question."})


def render_conversation_panel(dataset_path: Optional[Path]) -> None:
    st.subheader("LLM Conversation")
    if not dataset_path:
        st.info("Confirm a dataset to unlock the conversation workflow.")
        return

    history = st.session_state.setdefault(LLM_HISTORY_KEY, [])
    st.caption("Chat with Vizro MCP to add visuals, generate KPIs, or interrogate existing charts.")
    st.markdown(
        "<div class='chip-row'>"
        "<span class='chip'>Talk to data</span>"
        "<span class='chip'>Create chart</span>"
        "<span class='chip'>Add KPI</span>"
        "<span class='chip'>Ask about chart</span>"
        "</div>",
        unsafe_allow_html=True,
    )
    user_prompt = st.chat_input("Describe the chart or dashboard change you'd like")
    if user_prompt:
        history.append({"role": "user", "content": user_prompt})
        history.append(
            {
                "role": "assistant",
                "content": "Got it. I'm working on that request—click **Validate dashboard config** once I'm done to pull the updates into the dashboard.",
            }
        )
        handle_llm_interaction(user_prompt, dataset_path, history, show_messages=False)
    st.markdown(build_chat_history_html(history), unsafe_allow_html=True)
    if not history:
        st.caption("Use this chat to ask for new Vizro charts, KPI cards, dashboards, or data questions.")


# =============================================================================
# App entry point
# -----------------------------------------------------------------------------
# Compose sidebar + workspace layout and register callbacks. Streamlit reruns
# this `main` function on every interaction, so keep heavy work cached above.
# =============================================================================
def main() -> None:
    st.set_page_config(page_title="Analytical Continuum", layout="wide")
    st.markdown(APP_STYLE + CHAT_SCROLL_STYLE, unsafe_allow_html=True)
    st.markdown(
        "<h1 style='text-align:center; font-size:2.1rem; margin-top:0.2rem;'>Analytical Continuum</h1>",
        unsafe_allow_html=True,
    )
    st.markdown(
        "<p style='text-align:center; font-size:1.05rem; margin-top:-0.35rem; color:rgba(255,255,255,0.8);'>Descriptive and Diagnostic Analysis</p>",
        unsafe_allow_html=True,
    )

    api_key = ensure_api_key_loaded()
    st.session_state.setdefault("dashboard_dirty", True)

    # --- Dataset ingest lane (delegates UI + analysis to panels/dataset_panel) ---
    selected_dataset = render_dataset_selector()
    if not selected_dataset:
        stored_path = st.session_state.get(CURRENT_UPLOAD_KEY)
        selected_dataset = Path(stored_path) if stored_path else None

    if selected_dataset:
        st.success(f"Selected dataset: {selected_dataset.name}")
    else:
        st.info("Add files to the data/ directory and select one from the left pane.")

    confirmed_path = st.session_state.get("confirmed_dataset_path")
    selected_path_str = str(selected_dataset) if selected_dataset else None
    if not selected_path_str:
        st.session_state["dataset_confirmed"] = False
    elif confirmed_path and confirmed_path != selected_path_str:
        st.session_state["dataset_confirmed"] = False

    render_dataset_confirmation_button(selected_dataset)
    render_analysis_panel()

    if not api_key:
        st.warning("Set OPENAI_API_KEY in your environment to unlock LLM features.")

    dataset_path = Path(st.session_state["confirmed_dataset_path"]) if st.session_state.get("dataset_confirmed") else None

    if dataset_path:
        dataset_token = str(dataset_path.resolve())
        if st.session_state.get("filters_dataset") != dataset_token:
            st.session_state["filters_dataset"] = dataset_token
            st.session_state[FILTERS_KEY] = []
            st.session_state["dashboard_dirty"] = True
            st.session_state[DASHBOARD_VALIDATION_KEY] = None

    left_col, right_col = st.columns([3, 2])
    # --- Conversational lane: chat drives LLM orchestration + dashboard edits ---
    with right_col:
        render_conversation_panel(dataset_path)
    with left_col:
        if dataset_path:
            render_dashboard_panel(dataset_path)
        else:
            st.info("Lock in a dataset to start building the dashboard and asking chart questions.")


if __name__ == "__main__":
    main()
