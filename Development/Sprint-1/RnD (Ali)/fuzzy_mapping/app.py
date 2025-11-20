"""
Fuzzy Schema Mapper (Streamlit app)

- Upload a CSV
- The app proposes canonical -> user column mappings using fuzzy string matching.
- Uses rapidfuzz if available, otherwise difflib.
- Provides simple type-aware score boosts, conflict resolution, and an interactive threshold.
- Shows mapping table with scores and a renamed preview. Allows download.

Author: Researcher-style R&D helper
"""

from typing import List, Dict, Tuple, Optional, Any
import streamlit as st
import pandas as pd
import numpy as np
import re
import math
import json
from collections import defaultdict

# Try to import rapidfuzz for better fuzzy matching; otherwise fallback to difflib
_USE_RAPIDFUZZ = False
try:
    from rapidfuzz import process, fuzz
    _USE_RAPIDFUZZ = True
except Exception:
    import difflib

st.set_page_config(page_title="Fuzzy Schema Mapper", layout="wide")

# ---------------------------
# Canonical schema for the project
# ---------------------------
CANONICAL = [
    "order_id","opportunity_id","customer_id","order_date","lead_date",
    "close_date","first_purchase_date","revenue","units","product_id",
    "product_name","category","salesperson","region","country","city",
    "stage","channel","is_returning","aov","sales_cycle_days"
]

# ---------------------------
# Helpers: normalization, type inference
# ---------------------------
def _normalize(s: str) -> str:
    if s is None:
        return ""
    s = str(s).strip().lower()
    # unify common separators and remove extra chars
    s = re.sub(r"[^\w]+", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s

def infer_col_type(series: pd.Series, sample_n: int = 20) -> str:
    """
    Very lightweight heuristics to infer column type:
    returns one of: "date", "numeric", "id", "string", "unknown"
    """
    s = series.dropna().head(sample_n)
    if s.empty:
        return "unknown"
    date_ct = 0
    num_ct = 0
    total = 0
    uniq = len(series.dropna().unique())
    for v in s:
        total += 1
        vs = str(v).strip()
        if vs == "":
            continue
        # numeric?
        try:
            float(vs.replace(",", "").replace("$", ""))
            num_ct += 1
            continue
        except Exception:
            pass
        # date-like patterns
        if re.search(r"\b\d{4}[-/]\d{1,2}[-/]\d{1,2}\b", vs) or re.search(r"\b\d{1,2}[-/]\d{1,2}[-/]\d{2,4}\b", vs):
            date_ct += 1
    if total == 0:
        return "unknown"
    if date_ct/total > 0.6:
        return "date"
    if num_ct/total > 0.6:
        # if many unique values, treat as numeric (but could be id)
        if uniq > max(10, min(100, int(len(series) * 0.1))):
            return "numeric"
        return "numeric"
    # id heuristic: many unique values relative to rows
    if uniq >= min(20, max(5, int(len(series) * 0.3))):
        return "id"
    return "string"

# ---------------------------
# Fuzzy scoring functions
# ---------------------------
def fuzzy_candidates(query: str, choices: List[str], limit: int = 10) -> List[Tuple[str, float]]:
    """
    Return list of (choice, score) where score in 0..1 (higher better).
    Uses rapidfuzz if available (recommended), else difflib.
    """
    q = _normalize(query)
    if _USE_RAPIDFUZZ:
        # process.extract returns (choice, score, idx)
        matches = process.extract(q, choices, scorer=fuzz.ratio, limit=limit)
        out = []
        for match, score, idx in matches:
            out.append((match, float(score)/100.0))
        return out
    else:
        # difflib fallback
        normalized_choices = [_normalize(c) for c in choices]
        close = difflib.get_close_matches(q, normalized_choices, n=limit, cutoff=0)
        out = []
        for cm in close:
            idx = [i for i,c in enumerate(normalized_choices) if c == cm]
            if not idx:
                continue
            idx0 = idx[0]
            orig = choices[idx0]
            score = difflib.SequenceMatcher(a=q, b=cm).ratio()
            out.append((orig, score))
        return sorted(out, key=lambda x: x[1], reverse=True)

# ---------------------------
# Main mapping routine
# ---------------------------
def compute_fuzzy_mapping(
    df: pd.DataFrame,
    canonical: List[str] = CANONICAL,
    top_k: int = 5,
    fuzzy_threshold: float = 0.6,
    prefer_type_boost: bool = True,
    sample_n: int = 10
) -> Tuple[Dict[str, Optional[str]], Dict[str, Any]]:
    """
    Returns:
      - mapping: canonical -> user_col_or_None
      - report: detailed diagnostics (scores, candidates, inferred types)
    """
    user_cols = list(df.columns)
    # normalize mapping helpers
    norm_user = {c: _normalize(c) for c in user_cols}
    norm_canon = {c: _normalize(c) for c in canonical}

    # infer types for columns
    types = {c: infer_col_type(df[c], sample_n=sample_n) if c in df.columns else "unknown" for c in user_cols}
    # report structure
    report = {"user_cols": user_cols, "inferred_types": types, "candidates": {}, "scores": {}}

    # For each canonical, compute fuzzy matches among user columns
    canonical_candidates = {}
    for can in canonical:
        q = can
        candidates = fuzzy_candidates(q, user_cols, limit=top_k)
        enriched = []
        for ucol, base_score in candidates:
            # type boost
            type_boost = 0.0
            if prefer_type_boost:
                ctype_hint = "string"
                if "date" in can or can.endswith("_date"):
                    ctype_hint = "date"
                elif can in ("revenue", "units", "aov", "sales_cycle_days"):
                    ctype_hint = "numeric"
                elif can.endswith("_id") or "id" in can:
                    ctype_hint = "id"
                col_type = types.get(ucol, "unknown")
                # simple matching boosts
                if ctype_hint == "date" and col_type == "date":
                    type_boost = 0.15
                elif ctype_hint == "numeric" and col_type == "numeric":
                    type_boost = 0.15
                elif ctype_hint == "id" and col_type == "id":
                    type_boost = 0.12
            non_null_frac = df[ucol].notna().mean() if ucol in df.columns else 0.0
            # total score sum: base_score + type_boost + tiny population boost
            total_score = float(base_score) + float(type_boost) + 0.03 * float(non_null_frac)
            enriched.append({
                "user_col": ucol,
                "base_score": float(base_score),
                "type_boost": float(type_boost),
                "non_null_frac": float(non_null_frac),
                "total_score": float(total_score),
            })
        # sort descending by total_score
        enriched = sorted(enriched, key=lambda x: x["total_score"], reverse=True)
        canonical_candidates[can] = enriched
        report["candidates"][can] = enriched

    # Candidate selection and conflict resolution
    # Map canonical -> best user candidate that passes threshold; but ensure one-to-one mapping.
    tentative = {}  # canonical -> (user_col, total_score)
    for can, cand_list in canonical_candidates.items():
        if not cand_list:
            continue
        top = cand_list[0]
        # normalize threshold acceptance rules: accept if base_score >= fuzzy_threshold OR total_score >= fuzzy_threshold
        if top["base_score"] >= fuzzy_threshold or top["total_score"] >= fuzzy_threshold:
            tentative[can] = (top["user_col"], top["total_score"], top["base_score"])

    # Now we may have multiple canonicals pointing to same user_col. Resolve conflicts by choosing highest total_score per user_col
    user_best = {}  # user_col -> (canonical, total_score)
    for can, (ucol, tscore, bscore) in tentative.items():
        prev = user_best.get(ucol)
        if prev is None or tscore > prev[1]:
            user_best[ucol] = (can, tscore)

    # Construct final mapping
    mapping = {c: None for c in canonical}
    for ucol, (can, tscore) in user_best.items():
        # assign the winner
        mapping[can] = ucol

    # Add optional info about canonical candidates not picked (for debugging)
    report["tentative"] = tentative
    report["user_best"] = user_best
    report["final_map"] = mapping
    return mapping, report

# ---------------------------
# Streamlit UI layout & interactions
# ---------------------------
st.title("🔎 Fuzzy Schema Mapper")

st.markdown(
    """
This app proposes mappings from uploaded CSV column names to the canonical sales schema using fuzzy string matching.
It supports an adjustable fuzzy threshold and a small type-aware boost to improve accuracy.
"""
)

col1, col2 = st.columns([1, 2])

with col1:
    st.header("Controls")
    st.write("Upload CSV and tune mapping options.")
    uploaded = st.file_uploader("Upload CSV (CSV or TXT)", type=["csv", "txt"])
    st.markdown("**Options**")
    fuzzy_threshold = st.slider("Fuzzy base threshold (base_score)", min_value=0.0, max_value=1.0, value=0.60, step=0.01, help="Minimum base fuzzy score required OR total_score match to accept mapping.")
    prefer_type_boost = st.checkbox("Prefer type-aware boost (gives small score bonus if column values match expected type)", value=True)
    top_k = st.number_input("Top-K candidate search", min_value=1, max_value=20, value=6, step=1)
    sample_n = st.number_input("Samples per column (for type inference)", min_value=3, max_value=100, value=10, step=1)
    run_button = st.button("Run fuzzy mapping")

with col2:
    st.header("Canonical Schema")
    st.write(CANONICAL)

# show info on backend fuzzy engine
with st.expander("Engine info"):
    if _USE_RAPIDFUZZ:
        st.success("Using rapidfuzz for fuzzy matching (recommended).")
    else:
        st.info("rapidfuzz not available; using difflib fallback (less accurate).")

# Main logic
mapping_result = None
report_result = None
if uploaded is not None:
    # load dataframe robustly
    try:
        df = pd.read_csv(uploaded)
    except Exception:
        df = pd.read_csv(uploaded, engine="python")
    st.subheader("Preview of uploaded data (first 5 rows)")
    st.dataframe(df.head())

    st.markdown(f"Detected columns ({len(df.columns)}):")
    st.write(list(df.columns))

    if run_button:
        with st.spinner("Computing fuzzy mappings..."):
            mapping_result, report_result = compute_fuzzy_mapping(df,
                                                                 canonical=CANONICAL,
                                                                 top_k=int(top_k),
                                                                 fuzzy_threshold=float(fuzzy_threshold),
                                                                 prefer_type_boost=bool(prefer_type_boost),
                                                                 sample_n=int(sample_n))
        st.success("Mapping complete")

        # Prepare display: mapping table with score details
        mapping_rows = []
        for can in CANONICAL:
            mapped = mapping_result.get(can)
            cand_info = report_result["candidates"].get(can, [])[:3]  # show top3 candidates
            top_info = cand_info[0] if cand_info else None
            base_score = top_info["base_score"] if top_info else None
            total_score = top_info["total_score"] if top_info else None
            row = {
                "canonical": can,
                "mapped_to": mapped if mapped is not None else "<no mapping>",
                "top_candidate_base_score": round(base_score, 3) if base_score is not None else None,
                "top_candidate_total_score": round(total_score, 3) if total_score is not None else None,
                "top_3_candidates": json.dumps([{ "user_col": c["user_col"], "total_score": round(c["total_score"],3) } for c in cand_info])
            }
            mapping_rows.append(row)
        mapping_df = pd.DataFrame(mapping_rows)

        st.subheader("Proposed mapping (canonical → user column or `<no mapping>`) with scores")
        st.dataframe(mapping_df)

        # Show detailed report toggle
        if st.checkbox("Show detailed candidates & types (debug)"):
            st.markdown("### Inferred column types (sample-based)")
            types_df = pd.DataFrame([{"user_col": k, "inferred_type": v} for k,v in report_result["inferred_types"].items()])
            st.dataframe(types_df)

            st.markdown("### Candidate lists per canonical (top 6)")
            # build a neat display
            for can in CANONICAL:
                st.write(f"**{can}**")
                cand_list = report_result["candidates"].get(can, [])[:6]
                if not cand_list:
                    st.write("_no candidates_")
                else:
                    ctab = pd.DataFrame([{
                        "user_col": c["user_col"],
                        "base_score": round(c["base_score"],3),
                        "type_boost": round(c["type_boost"],3),
                        "non_null_frac": round(c["non_null_frac"],3),
                        "total_score": round(c["total_score"],3)
                    } for c in cand_list])
                    st.dataframe(ctab)

        # Show renamed preview (apply mapping)
        # Rename only mapped columns to canonical names
        rename_map = {v: k for k,v in mapping_result.items() if v is not None}
        renamed_df = df.rename(columns=rename_map)
        st.subheader("Renamed DataFrame preview (after applying mappings)")
        st.dataframe(renamed_df.head())

        # download mapped CSV
        csv_out = renamed_df.to_csv(index=False).encode("utf-8")
        st.download_button("Download renamed CSV", data=csv_out, file_name="mapped_fuzzy_output.csv", mime="text/csv")

# Footer / notes
st.markdown("---")
