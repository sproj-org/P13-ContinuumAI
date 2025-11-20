"""Dataset selection and analysis panel."""
from __future__ import annotations

from pathlib import Path
from typing import Dict, Optional

import streamlit as st

from continuum_v1.services.data_loader import ensure_column_stats, human_readable_size, list_data_files
from continuum_v1.services.vizro_client import call_vizro, run_async, serialize_result
from continuum_v1.settings import CURRENT_UPLOAD_KEY, DATA_DIR


def _panel():
    return st.sidebar


def render_dataset_selector() -> Optional[Path]:
    target = _panel()
    target.header("Data files")
    if target.button("Refresh list", key="refresh_data_files"):
        st.rerun()
    files = list_data_files()
    if not DATA_DIR.exists():
        target.error("Create a 'data' directory and place your datasets there.")
        st.session_state.pop(CURRENT_UPLOAD_KEY, None)
        return None
    if not files:
        target.warning("No supported files found in the data/ directory.")
        st.session_state.pop(CURRENT_UPLOAD_KEY, None)
        return None

    labels = []
    label_to_path: Dict[str, Path] = {}
    for path in files:
        label = f"{path.name} ({human_readable_size(path.stat().st_size)})"
        labels.append(label)
        label_to_path[label] = path

    default_label = st.session_state.get("selected_dataset_label")
    default_index = labels.index(default_label) if default_label in labels else 0
    selection = target.radio("Select a dataset", options=labels, index=default_index, key="dataset_radio")
    st.session_state["selected_dataset_label"] = selection
    selected_path = label_to_path.get(selection)
    if selected_path:
        st.session_state[CURRENT_UPLOAD_KEY] = str(selected_path.resolve())
    else:
        st.session_state.pop(CURRENT_UPLOAD_KEY, None)
    return selected_path


def render_dataset_confirmation_button(selected_dataset: Optional[Path]) -> None:
    target = _panel()
    button = target.button("Load this dataset", disabled=selected_dataset is None, key="load_dataset_button")
    if button and selected_dataset:
        st.session_state["dataset_confirmed"] = True
        st.session_state["confirmed_dataset_path"] = str(selected_dataset)
        if run_analysis_for_dataset(selected_dataset):
            target.success("Dataset locked in. Analysis refreshed below.")
        else:
            st.session_state["dataset_confirmed"] = False
            st.session_state.pop("confirmed_dataset_path", None)
    elif selected_dataset is None:
        target.caption("Select a dataset above to enable the workflow.")


def render_selected_dataset_badge() -> None:
    target = _panel()
    if not st.session_state.get("dataset_confirmed"):
        return
    path_str = st.session_state.get("confirmed_dataset_path")
    if not path_str:
        return
    path = Path(path_str)
    target.markdown("### Selected dataset")
    target.success(path.name)
    target.caption("Locked in for Vizro MCP analysis.")


def render_analysis_panel() -> None:
    target = _panel()
    analysis = st.session_state.get("analysis")
    with target.expander("Vizro MCP analysis report", expanded=False):
        if analysis:
            source = st.session_state.get("analysis_ran_for")
            if source:
                target.caption(f"Source: {Path(source).name}")
            target.json(analysis)
        else:
            target.caption("Select a file and click Load this dataset to run the Vizro analysis.")


def run_analysis_for_dataset(dataset_path: Path) -> bool:
    try:
        with st.spinner("Analyzing dataset via Vizro MCP..."):
            result = run_async(
                call_vizro("load_and_analyze_data", {"path_or_url": dataset_path.resolve().as_posix()})
            )
    except Exception as exc:
        st.error(f"Analysis failed: {exc}")
        return False
    st.session_state["analysis"] = serialize_result(result)
    st.session_state["analysis_ran_for"] = str(dataset_path.resolve())
    ensure_column_stats(dataset_path)
    return True
