import re
import json
from typing import Any, Dict, List, Optional
import streamlit as st
import pandas as pd
import google.generativeai as genai

GROUND_TRUTH_COLS = [
    "order_id","opportunity_id","customer_id","order_date","lead_date",
    "close_date","first_purchase_date","revenue","units","product_id",
    "product_name","category","salesperson","region","country","city",
    "stage","channel","is_returning","aov","sales_cycle_days"
]

genai.configure(api_key="AIzaSyCYqaBnjYtTZD55obDKIGxOx3T76t4IgaY")
model = genai.GenerativeModel("gemini-2.5-flash")

def _extract_text_from_response(resp) -> str:
    if isinstance(resp, str):
        return resp
    if hasattr(resp, "text"):
        try:
            return resp.text
        except Exception:
            pass
    try:
        if hasattr(resp, "output_text") and resp.output_text:
            return resp.output_text
    except Exception:
        pass
    try:
        if hasattr(resp, "candidates"):
            cands = getattr(resp, "candidates")
            if isinstance(cands, (list, tuple)) and len(cands) > 0:
                first = cands[0]
                if isinstance(first, dict) and "content" in first:
                    cont = first["content"]
                    if isinstance(cont, list) and len(cont) > 0:
                        parts = []
                        for block in cont:
                            if isinstance(block, dict) and "text" in block:
                                parts.append(block["text"])
                        if parts:
                            return " ".join(parts)
                elif hasattr(first, "text"):
                    return first.text
    except Exception:
        pass
    try:
        if isinstance(resp, dict):
            if "output" in resp:
                out = resp["output"]
                if isinstance(out, list) and out:
                    texts = []
                    for item in out:
                        if isinstance(item, dict) and "content" in item:
                            for c in item["content"]:
                                if isinstance(c, dict) and "text" in c:
                                    texts.append(c["text"])
                        elif isinstance(item, str):
                            texts.append(item)
                    if texts:
                        return " ".join(texts)
            if "choices" in resp and isinstance(resp["choices"], list) and resp["choices"]:
                ch = resp["choices"][0]
                if "message" in ch and "content" in ch["message"]:
                    return ch["message"]["content"]
                if "text" in ch:
                    return ch["text"]
    except Exception:
        pass
    try:
        return str(resp)
    except Exception:
        return ""

def _extract_first_json_block(text: str) -> Optional[str]:
    if not text:
        return None
    text = re.sub(r"```(?:json)?", "", text, flags=re.IGNORECASE)
    m = re.search(r"\{[\s\S]*\}", text)
    if m:
        return m.group(0)
    return None

def _normalize_mapping_shape(parsed: Any, csv_cols: List[str], ground_truth: List[str]) -> Dict[str, Optional[str]]:
    result = {gt: None for gt in ground_truth}
    if isinstance(parsed, dict):
        keys = list(parsed.keys())
        if all(k in ground_truth for k in keys):
            for k, v in parsed.items():
                if isinstance(v, str) and v in csv_cols:
                    result[k] = v
                elif v is None:
                    result[k] = None
                else:
                    if isinstance(v, str) and v.strip() in csv_cols:
                        result[k] = v.strip()
                    else:
                        result[k] = None
            return result
        if all(k in csv_cols for k in keys):
            for k, v in parsed.items():
                if isinstance(v, str) and v in ground_truth:
                    result[v] = k
            return result
        for k, v in parsed.items():
            if isinstance(v, str) and v in ground_truth and k in csv_cols:
                result[v] = k
        return result
    if isinstance(parsed, list):
        for element in parsed:
            if isinstance(element, dict):
                kk = None
                vv = None
                for k, val in element.items():
                    if isinstance(val, str) and val in ground_truth:
                        kk = val
                    elif isinstance(val, str) and val in csv_cols:
                        vv = val
                if kk:
                    result[kk] = vv
            elif isinstance(element, (list, tuple)) and len(element) == 2:
                a, b = element
                if isinstance(a, str) and a in ground_truth:
                    result[a] = b if b in csv_cols else None
                elif isinstance(b, str) and b in ground_truth:
                    result[b] = a if a in csv_cols else None
        return result
    return result

def get_llm_mapping_robust(csv_cols: List[str], model_obj, debug: bool = True) -> Dict[str, Optional[str]]:
    prompt = (
        "Return a single JSON object ONLY (no prose). Keys must be the canonical column names "
        "and values must be either the exact CSV column name that best matches or null.\n\n"
        f"Canonical: {GROUND_TRUTH_COLS}\n\nCSV columns: {csv_cols}\n\n"
        "Example: {\"order_id\": \"Order No\",\"revenue\": \"amount\",\"aov\": null}\n\n"
        "Return only JSON."
    )
    try:
        response = model_obj.generate_content(prompt)
    except Exception as e:
        st.error(f"Model call failed: {e}")
        return {gt: None for gt in GROUND_TRUTH_COLS}
    raw_repr = repr(response)
    if debug:
        st.write("### DEBUG: raw model response object:")
        st.write(raw_repr)
        try:
            st.write("Available attributes:", dir(response))
        except Exception:
            pass
    text = _extract_text_from_response(response)
    if debug:
        st.write("### DEBUG: extracted text from model:")
        st.code(text)
    json_block = _extract_first_json_block(text)
    parsed = None
    if json_block:
        try:
            parsed = json.loads(json_block)
        except Exception as e:
            st.warning(f"Failed to parse JSON block: {e}")
            parsed = None
    else:
        try:
            parsed = json.loads(text)
        except Exception:
            st.warning("No JSON object found in model text; returning fallback mapping.")
            parsed = None
    final_map = _normalize_mapping_shape(parsed, csv_cols, GROUND_TRUTH_COLS) if parsed is not None else {gt: None for gt in GROUND_TRUTH_COLS}
    if debug:
        st.write("### DEBUG: normalized mapping (canonical -> csv_or_null):")
        st.json(final_map)
    return final_map

st.title("LLM Schema Mapper")
st.write("Upload a CSV; the model will propose mappings and you can review/edit them.")

uploaded = st.file_uploader("Upload CSV", type=["csv"])
if uploaded:
    df = pd.read_csv(uploaded)
    st.subheader("Preview")
    st.dataframe(df.head())
    csv_cols = df.columns.tolist()
    st.write("### Step 1 — LLM suggestion")
    if st.button("Generate Suggested Mappings"):
        with st.spinner("Contacting LLM..."):
            initial_mapping = get_llm_mapping_robust(csv_cols, model, debug=True)
        st.session_state["initial_mapping"] = initial_mapping

if "initial_mapping" in st.session_state:
    st.write("### Step 2 — Review & Edit")
    initial_mapping = st.session_state["initial_mapping"]
    options = ["<no mapping>"] + csv_cols
    user_mapping: Dict[str, Optional[str]] = {}
    used = set()
    for gt_col in GROUND_TRUTH_COLS:
        default_value = initial_mapping.get(gt_col) if initial_mapping.get(gt_col) in options else "<no mapping>"
        selected = st.selectbox(
            f"Mapping for {gt_col}",
            options,
            index=options.index(default_value) if default_value in options else 0,
            key=f"sel_{gt_col}"
        )
        if selected != "<no mapping>":
            if selected in used:
                st.error(f"Column '{selected}' is already mapped. Choose a different one for {gt_col}.")
            else:
                used.add(selected)
        user_mapping[gt_col] = None if selected == "<no mapping>" else selected
    st.write("---")
    st.write("### Step 3 — Finalize")
    if st.button("Finalize Mapping"):
        st.success("Mapping finalized")
        st.json(user_mapping)
        st.code(str(user_mapping), language="python")
