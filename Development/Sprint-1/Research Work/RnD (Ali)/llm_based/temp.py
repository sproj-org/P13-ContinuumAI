import streamlit as st
import pandas as pd
import google.generativeai as genai

# ------------------------------
# CONFIG
# ------------------------------
GROUND_TRUTH_COLS = [
    "order_id","opportunity_id","customer_id","order_date","lead_date",
    "close_date","first_purchase_date","revenue","units","product_id",
    "product_name","category","salesperson","region","country","city",
    "stage","channel","is_returning","aov","sales_cycle_days"
]
genai.configure(api_key="AIzaSyCYqaBnjYtTZD55obDKIGxOx3T76t4IgaY")

# genai.configure(api_key=st.secrets.get("GEMINI_API_KEY", None))
# genai.configure(api_key=st.secrets.get("AIzaSyCYqaBnjYtTZD55obDKIGxOx3T76t4IgaY", None))
# genai.configure(api_key=st.secrets.get("GEMINI_API_KEY", "AIzaSyCYqaBnjYtTZD55obDKIGxOx3T76t4IgaY"))


model = genai.GenerativeModel("gemini-2.5-flash")


import re
import json
import streamlit as st

def _extract_text_from_response(resp) -> str:
    """
    Try many common SDK shapes to extract the returned text from the response object.
    We'll return the best guess string.
    """
    # 1) If it's already a string
    if isinstance(resp, str):
        return resp

    # 2) If it has attribute "text"
    if hasattr(resp, "text"):
        try:
            return resp.text
        except Exception:
            pass

    # 3) If it's a dataclass-like object with 'output' or 'candidates'
    try:
        # resp.output_text is used in some wrappers
        if hasattr(resp, "output_text") and resp.output_text:
            return resp.output_text
    except Exception:
        pass

    try:
        # resp.candidates (list) fallback
        if hasattr(resp, "candidates"):
            cands = getattr(resp, "candidates")
            if isinstance(cands, (list, tuple)) and len(cands) > 0:
                first = cands[0]
                # first might have .content or .text
                if isinstance(first, dict) and "content" in first:
                    # content often is a list of blocks
                    cont = first["content"]
                    if isinstance(cont, list) and len(cont) > 0:
                        # join text parts if present
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

    # 4) If it's a dict-like mapping
    try:
        if isinstance(resp, dict):
            # try common locations
            if "output" in resp:
                out = resp["output"]
                if isinstance(out, list) and out:
                    # try to extract textual pieces
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
                # openai compat
                if "message" in ch and "content" in ch["message"]:
                    return ch["message"]["content"]
                if "text" in ch:
                    return ch["text"]
    except Exception:
        pass

    # 5) Last resort: stringified object
    try:
        return str(resp)
    except Exception:
        return ""

def _extract_first_json_block(text: str) -> str | None:
    """
    Try to extract the first {...} JSON object from text.
    Returns the substring (including braces) or None.
    """
    if not text:
        return None
    # remove markdown fences (```json ... ``` / ``` ... ```)
    text = re.sub(r"```(?:json)?", "", text, flags=re.IGNORECASE)
    # find balanced braces by simple regex (first {...})
    m = re.search(r"\{[\s\S]*\}", text)
    if m:
        return m.group(0)
    return None

def _normalize_mapping_shape(parsed, csv_cols, ground_truth):
    """
    Accept multiple shapes and return canonical -> csv_col_or_none mapping.
    - If parsed is dict and keys are ground_truth => assume correct shape
    - If parsed is dict and keys are CSV columns => invert to canonical -> csv
    - If parsed is list of pairs/objects => convert accordingly
    """
    # init all-none
    result = {gt: None for gt in ground_truth}

    if isinstance(parsed, dict):
        keys = list(parsed.keys())
        # keys look like canonical names?
        if all(k in ground_truth for k in keys):
            # assume correct shape
            for k, v in parsed.items():
                if isinstance(v, str) and v in csv_cols:
                    result[k] = v
                elif v is None:
                    result[k] = None
                else:
                    # tolerant: if string but not exact, try trim
                    if isinstance(v, str) and v.strip() in csv_cols:
                        result[k] = v.strip()
                    else:
                        result[k] = None
            return result
        # keys look like CSV column names -> invert if values are canonical
        if all(k in csv_cols for k in keys):
            # invert: value -> key (if value is canonical)
            for k, v in parsed.items():
                if isinstance(v, str) and v in ground_truth:
                    result[v] = k
            return result
        # mixed or unknown keys: try to heuristically assign if values look canonical
        for k, v in parsed.items():
            if isinstance(v, str) and v in ground_truth and k in csv_cols:
                result[v] = k
        return result

    # If parsed is a list of pairs
    if isinstance(parsed, list):
        for element in parsed:
            if isinstance(element, dict):
                # try { "canonical": "order_id", "csv": "Order No" } or similar
                # find canonical and csv-like entries
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
                # ambiguous which is which; prefer canonical in second pos if matches
                if isinstance(a, str) and a in ground_truth:
                    result[a] = b if b in csv_cols else None
                elif isinstance(b, str) and b in ground_truth:
                    result[b] = a if a in csv_cols else None
        return result

    # fallback: return all-none
    return result

def get_llm_mapping_robust(csv_cols, model_obj, debug: bool = True):
    """
    Robust wrapper around model.generate_content(...). Returns mapping canonical->csv_or_None.
    - `model_obj` = your previously created genai.GenerativeModel(...) instance (or similar)
    """
    # Build a clearer prompt to reduce hallucinations. We ask for canonical -> csv_col mapping.
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

    # Debug: show model raw object and available attrs
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
            # show parse error
            st.warning(f"Failed to parse JSON block: {e}")
            parsed = None
    else:
        # try to parse the whole text as JSON
        try:
            parsed = json.loads(text)
        except Exception as e:
            st.warning("No JSON object found in model text; returning fallback mapping.")

    final_map = _normalize_mapping_shape(parsed, csv_cols, GROUND_TRUTH_COLS) if parsed is not None else {gt: None for gt in GROUND_TRUTH_COLS}
    if debug:
        st.write("### DEBUG: normalized mapping (canonical -> csv_or_null):")
        st.json(final_map)
    return final_map


# ------------------------------
# FUNCTION: ASK GEMINI FOR MAPPING
# ------------------------------
def get_llm_mapping(csv_cols):
    prompt = f"""
You are a schema-matching assistant.

Ground truth schema:
{GROUND_TRUTH_COLS}

CSV columns:
{csv_cols}

Task:
Return a JSON dictionary mapping each ground truth column → the best matching CSV column.
If no good match exists, map it to null.
Only output JSON. No explanation.
    """

    response = model.generate_content(prompt)

    try:
        mapping = eval(response.text)
        return mapping
    except:
        return {col: None for col in GROUND_TRUTH_COLS}


# ------------------------------
# STREAMLIT UI
# ------------------------------
st.title("🔍 Smart CSV Schema Mapping (LLM-Powered)")

st.write("Upload any CSV. The AI will detect column mappings and you can manually review them.")

uploaded = st.file_uploader("Upload CSV", type=["csv"])


# ------------------------------
# MAIN LOGIC
# ------------------------------
if uploaded:
    df = pd.read_csv(uploaded)
    st.subheader("📄 Preview of Uploaded File")
    st.dataframe(df.head())

    csv_cols = df.columns.tolist()

    st.write("### Step 1 — LLM Schema Suggestion")
    if st.button("Generate Suggested Mappings"):
        with st.spinner("LLM analyzing columns..."):
            # initial_mapping = get_llm_mapping(csv_cols)
            initial_mapping = get_llm_mapping_robust(csv_cols, model, debug=True)

        st.session_state["initial_mapping"] = initial_mapping

# If mapping exists, show editing UI
if "initial_mapping" in st.session_state:
    st.write("### Step 2 — Review & Correct Mappings")

    initial_mapping = st.session_state["initial_mapping"]

    # Build dropdown options
    options = ["<no mapping>"] + csv_cols

    # Track user selections
    user_mapping = {}

    # Track used columns to enforce one-to-one mapping
    used = set()

    for gt_col in GROUND_TRUTH_COLS:
        default_value = (
            initial_mapping.get(gt_col) if initial_mapping.get(gt_col) in options else "<no mapping>"
        )

        selected = st.selectbox(
            f"Mapping for **{gt_col}**",
            options,
            index=options.index(default_value) if default_value in options else 0,
            key=f"sel_{gt_col}"
        )

        # Enforce: cannot assign same CSV col twice
        if selected != "<no mapping>":
            if selected in used:
                st.error(f"❌ Column '{selected}' is already mapped. Choose a different one for {gt_col}.")
            else:
                used.add(selected)

        user_mapping[gt_col] = None if selected == "<no mapping>" else selected

    st.write("---")
    st.write("### Step 3 — Final Mapping")

    if st.button("Finalize Mapping"):
        st.success("✅ Mapping finalized!")
        st.json(user_mapping)

        st.write("Copy this Python dict:")
        st.code(str(user_mapping), language="python")
