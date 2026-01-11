import json
import textwrap
from typing import Any, Dict, List
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from openai import OpenAI
from app.core.config import get_settings

SYSTEM_PROMPT = """You are an analytics assistant that generates Python code for interactive visuals.
- Input: user question + a pandas DataFrame named df.
- Output: Python code that creates one or more Plotly Figures and assigns each to variables with names starting with fig_ (e.g., fig_1, fig_a). Do not print; do not show anything else.
- You may import and use: pandas (pd), plotly.express as px, plotly.graph_objects as go, vizro, vizro.models as vm, vizro.plotly.express as px (if available).
- Keep it safe and deterministic; do not fetch network resources.
- Prefer charts over tables unless the user explicitly asks for a table.
- If the user asks for multiple visuals, create multiple figures (fig_1, fig_2, ...)."""


def _df_schema_snippet(df: pd.DataFrame) -> str:
    cols = {c: str(df[c].dtype) for c in df.columns}
    sample = df.head(5).to_dict(orient="list")
    return f"Columns and dtypes: {json.dumps(cols)}\nSample rows: {json.dumps(sample, default=str)}"


def generate_plotly_code(message: str, df: pd.DataFrame) -> Dict[str, Any]:
    settings = get_settings()
    if not getattr(settings, "OPENAI_API_KEY", None):
        return {"error": "OPENAI_API_KEY not set"}
    client = OpenAI(api_key=settings.OPENAI_API_KEY)
    user_prompt = f"Question: {message}\n\nUse DataFrame `df` with schema:\n{_df_schema_snippet(df)}"
    resp = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {
                "role": "user",
                "content": user_prompt
                + "\nReturn ONLY python code. Ensure you assign Plotly figures to variables named fig_*.",
            },
        ],
        temperature=0.2,
    )
    code = resp.choices[0].message.content or ""
    return {"code": code}


def run_generated_code(code: str, df: pd.DataFrame) -> Dict[str, Any]:
    # extract code block if present
    if "```" in code:
        parts = code.split("```")
        for i in range(len(parts)):
            if parts[i].strip().startswith("python"):
                code = parts[i + 1]
                break
        else:
            # take last fenced block if no python label
            code = parts[-2] if len(parts) >= 2 else code
    code = textwrap.dedent(code)
    exec_env: Dict[str, Any] = {"df": df, "pd": pd, "px": px, "go": go}
    # Optional Vizro imports if available
    try:
        import vizro  # type: ignore
        import vizro.models as vm  # type: ignore
        import vizro.plotly.express as vpx  # type: ignore

        exec_env.update({"vizro": vizro, "vm": vm, "vpx": vpx})
    except Exception:
        pass

    try:
        # Use a single namespace for globals/locals so assignments stay visible
        exec_env["__builtins__"] = __builtins__
        exec(code, exec_env, exec_env)
    except Exception as e:
        return {"error": f"exec_failed: {e}", "code": code}

    figures: List[Dict[str, Any]] = []
    for name, val in exec_env.items():
        if name.startswith("fig") and hasattr(val, "to_plotly_json"):
            figures.append(val.to_plotly_json())

    if not figures:
        return {"error": "no_fig_generated", "locals": list(exec_env.keys()), "code": code}

    return {"figures": figures}
