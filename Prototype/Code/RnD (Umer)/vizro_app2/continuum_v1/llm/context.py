"""Shared LLM context helpers: column summaries, prompts, narratives."""
from __future__ import annotations

import textwrap
from pathlib import Path
from typing import Any, Dict, Optional

import pandas as pd
import streamlit as st

from continuum_v1.settings import CURRENT_UPLOAD_KEY, DASHBOARD_COMPONENTS_KEY

COLUMN_SYNONYMS = {
    "country": "nationality",
    "nationality": "nationality",
    "employment type": "emp_type",
    "job type": "emp_type",
    "distance": "distance_from_office_miles",
    "travel cost": "travel_cost",
    "age": "age",
}


def format_column_stats(stats: Dict[str, Dict[str, Any]]) -> str:
    if not stats:
        return "No cached statistics."
    lines = []
    for name, info in stats.items():
        if info.get("type") == "numeric":
            lines.append(
                f"- {name}: mean={info.get('mean'):.2f if info.get('mean') is not None else 'n/a'}, "
                f"median={info.get('median', 'n/a')}, std={info.get('std', 'n/a')}"
            )
        else:
            top_values = info.get("top_values") or {}
            pairs = ", ".join(f"{k} ({v})" for k, v in top_values.items())
            lines.append(f"- {name}: {pairs}")
    return "\n".join(lines)


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
    return COLUMN_SYNONYMS.get(lowered)


def detect_question_columns(question: str, dataset_columns: list[str]) -> list[str]:
    q = question.lower()
    matches: list[str] = []
    for col in dataset_columns:
        patterns = {col.lower(), col.lower().replace("_", " ")}
        if any(p in q for p in patterns):
            matches.append(col)
    for phrase, actual in COLUMN_SYNONYMS.items():
        if phrase in q and actual in dataset_columns:
            matches.append(actual)
    seen = set()
    ordered: list[str] = []
    for col in matches:
        if col not in seen:
            ordered.append(col)
            seen.add(col)
    return ordered


def resolve_chart_name(chart_title: str) -> Optional[str]:
    if not chart_title:
        return None
    comps = st.session_state.get(DASHBOARD_COMPONENTS_KEY, [])
    target = chart_title.lower()
    for comp in comps:
        candidate = comp.get("chart_name") or (comp.get("figure") or {}).get("_target_")
        if not candidate:
            continue
        title = comp.get("title", "")
        comp_id = comp.get("id", "")
        if title and title.lower() == target:
            return candidate
        if comp_id and comp_id.lower() == target:
            return candidate
    return None


def resolve_column_for_dataframe(name: str, df_columns: list[str]) -> Optional[str]:
    if not name:
        return None
    lowered = name.strip().lower()
    normalized = lowered.replace(" ", "_")
    for col in df_columns:
        col_lower = col.lower()
        if col_lower == lowered or col_lower.replace(" ", "_") == normalized:
            return col
    mapped = map_column_name(name)
    if mapped and mapped in df_columns:
        return mapped
    return None


def infer_metric_column(df: pd.DataFrame) -> Optional[str]:
    candidates = ["value", "count", "total", "measure", "records"]
    for col in candidates:
        if col in df.columns and pd.api.types.is_numeric_dtype(df[col]):
            return col
    return None


def dataset_summary_for_prompt(dataset_path: Path) -> str:
    analysis = st.session_state.get("analysis") or {}
    summary_chunks = []
    general = analysis.get("summary")
    if general:
        summary_chunks.append(textwrap.shorten(general, width=600))
    sample = (analysis.get("df_metadata") or {}).get("column_names_types") or {}
    if sample:
        summary_chunks.append("Columns:\n" + "\n".join(f"- {name}: {ctype}" for name, ctype in sample.items()))
    stats = st.session_state.get("column_stats")
    if stats:
        summary_chunks.append("Column statistics:\n" + format_column_stats(stats))
    if not summary_chunks:
        summary_chunks.append(f"Dataset path: {dataset_path}")
    return "\n\n".join(summary_chunks)


def needs_narrative_response(question: str) -> bool:
    q = question.lower()
    keywords = ["explain", "summarize", "trend", "describe", "insight", "overview"]
    return any(k in q for k in keywords)


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
You are a senior data analyst. Given grouped summary values from a chart and the user's question, write a short paragraph
(2-3 sentences) describing the insight. Reference specific group names and values. Do not request additional code.
""".strip()
    payload = {
        "chart_title": chart_title,
        "question": question,
        "filters": filters,
        "summary": summary_items,
        "dataset_hint": str(dataset_path),
    }
    try:
        from openai import OpenAI

        client = OpenAI(api_key=api_key)
        resp = client.chat.completions.create(
            model="gpt-5-mini",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": str(payload)},
            ],
        )
        return resp.choices[0].message.content.strip()
    except Exception as exc:  # pragma: no cover - relies on external service
        return f"Unable to generate narrative explanation: {exc}"
