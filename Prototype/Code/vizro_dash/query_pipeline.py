from __future__ import annotations

import json
import logging
import os
import re
from pathlib import Path
from typing import Dict, List, Sequence

import pandas as pd

try:
    import google.generativeai as genai
except Exception:
    genai = None


def _load_local_env():
    env_path = Path(__file__).resolve().parent / ".env"
    if not env_path.exists():
        return
    for raw in env_path.read_text().splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip()
        if key and key not in os.environ:
            os.environ[key] = value


_load_local_env()
logging.basicConfig(level=os.getenv("VIZRO_PIPELINE_LOG", "INFO"))


def _dedupe(values: Sequence[str]) -> List[str]:
    seen = {}
    for val in values:
        if val:
            seen.setdefault(val, None)
    return list(seen.keys())


def filter_dataframe(
    df: pd.DataFrame,
    regions: Sequence[str],
    categories: Sequence[str],
) -> pd.DataFrame:
    scoped = df.copy()
    if regions:
        scoped = scoped[scoped["region"].isin(regions)]
    if categories:
        scoped = scoped[scoped["category"].isin(categories)]
    return scoped if not scoped.empty else df


def format_summary(regions: Sequence[str], categories: Sequence[str]) -> str:
    parts: List[str] = []
    if regions:
        parts.append("regions: " + ", ".join(regions))
    if categories:
        parts.append("categories: " + ", ".join(categories))
    return "Showing overall performance." if not parts else "Showing filtered view for " + " and ".join(parts) + "."


class VizroQueryPipeline:
    """Lightweight planner that can optionally leverage Gemini for natural language filters."""

    def __init__(self, df: pd.DataFrame | None = None):
        self._logger = logging.getLogger("vizro.pipeline")
        self._base_df = df.copy() if df is not None else None
        self.regions = sorted({str(v) for v in (self._base_df["region"].dropna().unique() if self._base_df is not None else [])})
        self.categories = sorted({str(v) for v in (self._base_df["category"].dropna().unique() if self._base_df is not None else [])})
        self._region_lookup = {v.lower(): v for v in self.regions}
        self._category_lookup = {v.lower(): v for v in self.categories}
        self._model_name = os.getenv("GEMINI_MODEL", "gemini-1.5-flash")
        self._api_key = os.getenv("GEMINI_API_KEY")
        self._llm_ready = bool(self._api_key and genai)
        if self._llm_ready:
            genai.configure(api_key=self._api_key)
            self._logger.info(
                "Gemini pipeline enabled (model=%s). API key detected via environment.", self._model_name
            )
            print(f"[VizroPipeline] Gemini enabled with model {self._model_name}.")
        else:
            reason = "library not installed" if not genai else "API key missing"
            self._logger.warning("Gemini pipeline disabled (%s). Falling back to keyword parser.", reason)
            print(f"[VizroPipeline] Gemini disabled ({reason}). Using keyword fallback.")

    def plan(self, message: str) -> Dict[str, List[str] | str]:
        if self._llm_ready:
            plan = self._llm_plan(message)
            if plan:
                self._logger.debug("Gemini plan succeeded: %s", plan)
                return plan
            self._logger.warning("Gemini classification failed; falling back to keyword plan.")
        return self._keyword_plan(message)

    # ----- LLM helpers -----

    def _llm_plan(self, message: str) -> Dict[str, List[str] | str] | None:
        try:
            model = genai.GenerativeModel(self._model_name)
            prompt = self._build_prompt(message)
            resp = model.generate_content(prompt)
            text = getattr(resp, "text", "") or str(resp)
            parsed = self._safe_json(text)
            if not isinstance(parsed, dict):
                return None
            regions = self._clean_values(parsed.get("regions", []), self._region_lookup)
            categories = self._clean_values(parsed.get("categories", []), self._category_lookup)
            summary = parsed.get("summary") or format_summary(regions, categories)
            return {"regions": regions, "categories": categories, "summary": summary}
        except Exception as exc:
            self._logger.exception("Gemini plan failed: %s", exc)
            return None

    def _build_prompt(self, message: str) -> str:
        return f"""
You are a BI assistant that translates user requests into filters on a sales dataset.

Return JSON with keys "regions" (array of region names), "categories" (array), and "summary" (short sentence).

Available regions: {", ".join(self.regions) or "Unknown"}
Available categories: {", ".join(self.categories) or "Unknown"}

Rules:
- Only use region/category names from the lists above.
- If unsure, return empty arrays.
- Summary should mention what is being shown (e.g., "Showing software sales in the West.").

User query: {message}
"""

    @staticmethod
    def _safe_json(text: str):
        try:
            return json.loads(text)
        except Exception:
            s, e = text.find("{"), text.rfind("}")
            if s != -1 and e != -1 and e > s:
                try:
                    return json.loads(text[s : e + 1])
                except Exception:
                    return None
            return None

    def _clean_values(self, values: Sequence[str], lookup: Dict[str, str]) -> List[str]:
        cleaned: List[str] = []
        for val in values or []:
            if not val:
                continue
            key = str(val).strip().lower()
            if key in lookup:
                cleaned.append(lookup[key])
                continue
            # partial match fallback
            for known, resolved in lookup.items():
                if key in known or known in key:
                    cleaned.append(resolved)
                    break
        return _dedupe(cleaned)

    # ----- Keyword fallback -----

    def _keyword_plan(self, message: str) -> Dict[str, List[str] | str]:
        text = (message or "").lower()
        regions = [val for key, val in self._region_lookup.items() if key and key in text]
        categories = [val for key, val in self._category_lookup.items() if key and key in text]

        synonyms = {
            "north": "north",
            "northern": "north",
            "south": "south",
            "southern": "south",
            "west": "west",
            "western": "west",
            "east": "east",
            "eastern": "east",
            "central": "central",
        }
        for word, canonical in synonyms.items():
            if word in text and canonical in self._region_lookup:
                regions.append(self._region_lookup[canonical])

        if not categories:
            if "software" in text and "software" in self._category_lookup:
                categories.append(self._category_lookup["software"])
            if "service" in text and "services" in self._category_lookup:
                categories.append(self._category_lookup["services"])

        regions = _dedupe(regions)
        categories = _dedupe(categories)
        plan = {"regions": regions, "categories": categories, "summary": format_summary(regions, categories)}
        self._logger.debug("Keyword plan produced: %s", plan)
        return plan
