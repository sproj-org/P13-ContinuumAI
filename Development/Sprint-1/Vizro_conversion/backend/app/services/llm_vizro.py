import json
import textwrap
from typing import Any, Dict, List, Optional

import pandas as pd
from openai import OpenAI
import httpx

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
  }} | null,
  "dashboard_plan": {{
      "title": "string",
      "theme": "vizro_dark",
      "controls": [],
      "layout_hint": "optional"
  }} | null
}}

Rules:
- Use only the listed dataset columns (case-insensitive mapping allowed); never invent columns.
- If `px.pie` or other PX charts are used, include explicit `data_frame=`.
- Ensure aggregated columns have unique names; rename as needed.
- Do not set Plotly templates/backgrounds; let Vizro themes handle styling.
- Use `card_plan` for single KPI markdown (function must accept `data_frame` and return text or dict with `text`).
- If a requested field is missing, set plans to null and explain in `reply`.
""".strip()


def call_vizro_llm(message: str, df: pd.DataFrame) -> Dict[str, Any]:
    settings = get_settings()
    if not getattr(settings, "OPENAI_API_KEY", None):
        return {"error": "OPENAI_API_KEY not set"}
    # Provide our own httpx client to avoid passing unsupported proxy args on httpx>=0.28
    http_client = httpx.Client()
    client = OpenAI(api_key=settings.OPENAI_API_KEY, http_client=http_client)
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
