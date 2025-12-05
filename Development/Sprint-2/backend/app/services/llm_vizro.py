import json
import textwrap
from typing import Any, Dict, List, Optional

import pandas as pd
from openai import OpenAI

from app.core.config import get_settings
from app.services.context_helpers import dataset_summary_for_prompt


def build_system_prompt(df: pd.DataFrame) -> str:
    return f"""
You are Vizro MCP's LLM assistant. Help the user design charts and dashboards from the provided dataset.
Dataset summary:
{dataset_summary_for_prompt(df)}

Always respond with valid JSON of the form:
{{
  "reply": "natural language guidance",
  "chart_plan": {{
      "chart_type": "...",
      "chart_name": "snake_case",
      "imports": ["import pandas as pd", "import plotly.express as px"],
      "chart_code": "def chart_name(data_frame): ...\\n    return fig"
  }} | null,
  "card_plan": {{
      "card_name": "snake_case",
      "imports": ["import pandas as pd"],
      "card_code": "def card_name(data_frame): ...\\n    return {{'text': '### KPI\\n42%'}}"
  }} | null
}}

Use `card_plan` for KPI-style summaries that should appear above the charts. The `card_code` function must accept `data_frame` and return either Markdown text (string) or a dict containing at least a `text` field. Keep each card focused on a single scalar metric derived from the dataset and format the Markdown text with the computed value.

If `px.pie` is used, ALWAYS include an explicit `data_frame=` argument (e.g., aggregate into a small DataFrame as `chart_df` and call `px.pie(data_frame=chart_df, names=..., values=...)`).
When preparing aggregated data, ensure every column name is unique (e.g., use `rename` or distinct column names instead of duplicating `count`). If you create `chart_df = ...value_counts().reset_index()`, rename both columns explicitly (e.g., `chart_df.columns = ["nationality", "count"]`).
Never set Plotly templates or background colors (omit `template=` arguments and let Vizro themes handle styling).
The dataset column names listed above are the source of truth. When the user mentions a column concept ("employment type", "nationalities", etc.), map it to the actual column name from that list (case-insensitive match). Always reference the exact column spelling from the dataset in the generated code.

If no visual should be generated, set both plan entries to null. When producing code, follow Vizro chart guidelines, use the provided data_frame argument, and rely on pandas/plotly express for charts or pandas computations for KPI cards.
""".strip()


def call_vizro_llm(message: str, df: pd.DataFrame) -> Dict[str, Any]:
    settings = get_settings()
    if not getattr(settings, "OPENAI_API_KEY", None):
        return {"error": "OPENAI_API_KEY not set"}
    client = OpenAI(api_key=settings.OPENAI_API_KEY)
    sys_prompt = build_system_prompt(df)
    resp = client.chat.completions.create(
        model="gpt-5-mini",
        messages=[
            {"role": "system", "content": sys_prompt},
            {"role": "user", "content": message},
        ],
        # temperature=0.2,
    )
    raw = resp.choices[0].message.content or ""
    return {"raw": raw}


def extract_json(raw: str) -> Dict[str, Any]:
    text = raw.strip()
    if text.startswith("```"):
        parts = text.split("```", 2)
        if len(parts) >= 2:
            text = parts[1]
    try:
        return json.loads(text)
    except Exception:
        return {"reply": raw, "chart_plan": None, "card_plan": None}
