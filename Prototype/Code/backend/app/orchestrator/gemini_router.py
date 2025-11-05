from __future__ import annotations
from typing import Any, Dict, List, Callable, Tuple
import os, json, importlib, inspect, re

try:
    import google.generativeai as genai
except Exception:
    print("NO LIB FOR GEMINI")
    genai = None

from app.core.config import settings


def _tokenize(s: str) -> List[str]:
    s = (s or "").lower()
    return re.findall(r"[a-z0-9]+", s)


class Orchestrator:
    def __init__(self) -> None:
        self._tools = self._discover_tools()
        self._index = self._build_index()  # <- add this

        self._model_name = settings.GEMINI_MODEL or os.getenv(
            "GEMINI_MODEL", "gemini-2.5-pro"
        )
        self._gemini_ready = bool(getattr(settings, "GEMINI_API_KEY", "") and genai)
        if self._gemini_ready:
            genai.configure(api_key=settings.GEMINI_API_KEY)

        from app.utils import data_functions as _df
        print("DEBUG|discovered_tools:", [n for n in dir(_df) if callable(getattr(_df, n)) and not n.startswith("_")])


    def _build_index(self) -> Dict[str, set]:
        # tokens per tool: function name + doc + meta fields
        mod = importlib.import_module("app.utils.data_functions")
        idx = {}
        for name, obj in inspect.getmembers(mod, inspect.isfunction):
            if name.startswith("_"): continue
            toks = set(_tokenize(name))
            doc  = (inspect.getdoc(obj) or "")
            toks |= set(_tokenize(doc))
            meta = getattr(obj, "__tool_meta__", {}) or {}
            for k in ("intent","returns","requires"):
                vals = meta.get(k, [])
                if isinstance(vals, (list, tuple)):
                    for v in vals: toks |= set(_tokenize(str(v)))
                elif isinstance(vals, str):
                    toks |= set(_tokenize(vals))
            idx[name] = toks
        return idx



    def _discover_tools(self) -> Dict[str, Callable[..., Any]]:
        mod = importlib.import_module("app.utils.data_functions")
        tools: Dict[str, Callable[..., Any]] = {}
        for name, obj in inspect.getmembers(mod, inspect.isfunction):
            if name.startswith("_"):  # skip internals
                continue
            tools[name] = obj
        return tools

    def tool_catalog(self) -> List[Dict[str, str]]:
        mod = importlib.import_module("app.utils.data_functions")
        cats: List[Dict[str, str]] = []
        for name, obj in inspect.getmembers(mod, inspect.isfunction):
            if name.startswith("_"):
                continue
            meta = getattr(obj, "__tool_meta__", {}) or {}
            doc  = (inspect.getdoc(obj) or "").strip()
            cats.append({
                "name": name,
                "doc": doc[:300],
                "intent": " ".join(meta.get("intent", [])[:20]),
                "returns": " ".join(meta.get("returns", [])[:20]),
                "requires": " ".join(meta.get("requires", [])[:20]),
            })
        return cats

    # ----------------- Classification -----------------

#     def _build_classifier_prompt(self, message: str) -> str:
#         tools_json = json.dumps(self.tool_catalog(), ensure_ascii=False)
#         schema = {"response_type": "chart", "tool_names": ["name1"], "tool_args": {}}
#         return f"""You are a BI tool router. Choose 1–2 best tools from TOOLS and minimal args for the user's request.
# TOOLS:
# {tools_json}
# Return ONLY JSON like: {json.dumps(schema)}
# User: {message}"""


    def _build_classifier_prompt(self, message: str) -> str:
        # Anchor “current date” for parsing relatives
        TODAY = "17 October 2025"

        tools_json = json.dumps(self.tool_catalog(), ensure_ascii=False)
        schema = {
            "response_type": "chart",
            "tool_names": ["name1"],
            "tool_args": {
                "date_from": "YYYY-MM-DD or null",
                "date_to":   "YYYY-MM-DD or null",
                "regions":   ["list of strings or empty"],
                "reps":      ["list of strings or empty"],
                "categories":["list of strings or empty"]
            }
        }
        return f"""
    You are a BI tool router and argument extractor.

    - Today's date is **{TODAY}**. Resolve relative dates (e.g., "last quarter", "this year to date") against this date.
    - Return ONLY JSON matching the schema below.
    - Choose the best 1-2 tools whose intent matches the user ask.
    - Fill tool_args ONLY with these keys: date_from, date_to, regions, reps, categories.
    - Use ISO dates YYYY-MM-DD. If a date is ambiguous, prefer calendar quarters, and fill concrete start/end dates.
    - Do not invent fields. Empty lists instead of scalars for regions/reps/categories.

    TOOLS:
    {tools_json}

    SCHEMA:
    {json.dumps(schema)}

    USER:
    {message}
    """.strip()


    def _safe_json(self, text: str) -> Any:
        try:
            return json.loads(text)
        except Exception:
            s, e = text.find("{"), text.rfind("}")
            if s != -1 and e != -1 and e > s:
                try:
                    return json.loads(text[s : e + 1])
                except Exception:
                    return {}
            return {}

    def rank_tools(self, message: str) -> List[Tuple[str, float]]:
        mtoks = set(_tokenize(message))
        print(
            f"[DEBUG] Message tokens: {mtoks}"
        )  # Debug: Check tokens from the message
        scores: List[Tuple[str, float]] = []
        for tname in self._tools.keys():
            ttoks = set(_tokenize(tname))
            overlap = mtoks & ttoks

        #     score = 0.0
        #     if any(k in mtoks for k in ("top", "rank", "best", "leaderboard")):
        #         if (
        #             "product" in ttoks
        #             or "salespeople" in ttoks
        #             or "leaderboard" in ttoks
        #         ):
        #             score += 2
        #     if "trend" in mtoks or "over" in mtoks or "time" in mtoks:
        #         if any(k in ttoks for k in ("over_time", "trend")):
        #             score += 2
        #     for k in (
        #         "revenue",
        #         "product",
        #         "customer",
        #         "city",
        #         "country",
        #         "region",
        #         "salesperson",
        #         "aov",
        #         "funnel",
        #         "pipeline",
        #     ):
        #         if k in mtoks and k in ttoks:
        #             score += 0.5
        #     if score > 0:
        #         scores.append((tname, score))
        # print(
        #     f"[DEBUG] Ranked tools: {scores}"
        # )  # Debug: Check ranked tools and their scores
        # return sorted(scores, key=lambda x: x[1], reverse=True)

        for tname, ttoks in self._index.items():
            overlap = mtoks & ttoks
            # simple scoring: overlap size with some boosts
            score = float(len(overlap))
            if "by" in mtoks and {"region","regions"} & ttoks: score += 0.5
            if {"trend","monthly","mo","month"} & mtoks and {"trend","month"} & ttoks: score += 0.5
            if score > 0:
                scores.append((tname, score))
        return sorted(scores, key=lambda x: x[1], reverse=True)


    def classify(self, message: str) -> Dict[str, Any]:
        print(
            f"[DEBUG] Classifying message: {message}"
        )  # Debug: Check the input message
        if self._gemini_ready:
            try:
                model = genai.GenerativeModel(self._model_name)
                resp = model.generate_content(self._build_classifier_prompt(message))
                text = resp.text if hasattr(resp, "text") else str(resp)
                parsed = self._safe_json(text)
                print(
                    f"[DEBUG] Gemini classification response: {parsed}"
                )  # Debug: Check Gemini response
                if isinstance(parsed, dict) and parsed.get("tool_names"):
                    return parsed
            except Exception as e:
                print(
                    f"[DEBUG] Gemini classification failed: {e}"
                )  # Debug: Check Gemini errors
        ranked = self.rank_tools(message)
        print(
            f"[DEBUG] Fallback ranked tools: {ranked}"
        )  # Debug: Check fallback ranking
        if not ranked:
            return {"response_type": "chart", "tool_names": [], "tool_args": {}}
        picks = [n for n, _ in ranked[:2]]
        return {"response_type": "chart", "tool_names": picks, "tool_args": {}}


    # ----------------- Execution -----------------

    def _to_plotly_json(self, obj):
        # Pass-through figure dicts
        if isinstance(obj, dict) and "data" in obj:
            return obj

        # Plotly figures
        try:
            if hasattr(obj, "to_plotly_json"):
                return obj.to_plotly_json()
        except Exception:
            pass

        # Common wrapper keys
        if isinstance(obj, dict):
            for key in ("figure", "plot", "payload", "plotly"):
                if key in obj:
                    inner = obj[key]
                    try:
                        if hasattr(inner, "to_plotly_json"):
                            return inner.to_plotly_json()
                    except Exception:
                        pass
                    if isinstance(inner, dict) and "data" in inner:
                        return inner
                    if isinstance(inner, str):
                        try:
                            parsed = json.loads(inner)
                            if isinstance(parsed, dict) and "data" in parsed:
                                return parsed
                        except Exception:
                            pass
            if "results" in obj and isinstance(obj["results"], list):
                for item in obj["results"]:
                    norm = self._to_plotly_json(item)
                    if isinstance(norm, dict) and "data" in norm:
                        return norm
            if "traces" in obj and isinstance(obj["traces"], list):
                return {"data": obj["traces"], "layout": obj.get("layout", {})}

        # Tuples
        if isinstance(obj, tuple) and len(obj) == 2:
            a, b = obj
            if isinstance(a, list) and (isinstance(b, dict) or b is None):
                return {"data": a, "layout": (b or {})}
            na = self._to_plotly_json(a)
            if isinstance(na, dict) and "data" in na:
                return na
            nb = self._to_plotly_json(b)
            if isinstance(nb, dict) and "data" in nb:
                return nb

        # Lists
        if isinstance(obj, list):
            if not obj:
                return {"data": [], "layout": {}}
            if isinstance(obj[0], dict) and "data" in obj[0]:
                return obj[0]
            if isinstance(obj[0], dict):
                return {"data": obj, "layout": {}}
            for it in obj:
                norm = self._to_plotly_json(it)
                if isinstance(norm, dict) and "data" in norm:
                    return norm

        # JSON string or file path
        if isinstance(obj, str):
            if obj.lower().endswith(".json") and os.path.exists(obj):
                try:
                    with open(obj, "r", encoding="utf-8") as f:
                        parsed = json.load(f)
                    if isinstance(parsed, dict) and "data" in parsed:
                        return parsed
                except Exception:
                    pass
            try:
                parsed = json.loads(obj)
                if isinstance(parsed, dict) and "data" in parsed:
                    return parsed
                if isinstance(parsed, dict) and "results" in parsed:
                    return self._to_plotly_json(parsed)
            except Exception:
                pass

        # Pandas DF -> table fallback
        try:
            import pandas as _pd

            if "pandas" in str(type(obj)):
                df = obj
                return {
                    "data": [
                        {
                            "type": "table",
                            "header": {"values": list(df.columns)},
                            "cells": {"values": [df[c].tolist() for c in df.columns]},
                        }
                    ],
                    "layout": {"title": "Table"},
                }
        except Exception:
            pass

        return None

    def run_tools(
        self,
        tool_names: List[str],
        get_df,
        tool_args: Dict[str, Any],
        return_debug: bool = False,
    ):
        results: List[Dict[str, Any]] = []
        debug: List[Dict[str, Any]] = []

        for name in tool_names:
            fn = self._tools.get(name)
            if not fn:
                debug.append({"tool": name, "error": "not_found"})
                continue
            try:
                df = get_df(name)
            except Exception as e:
                debug.append({"tool": name, "error": f"dataframe_load_failed: {e}"})
                continue
            try:
                sig = inspect.signature(fn)
                kwargs = dict(tool_args or {})
                if "n" in sig.parameters and "n" not in kwargs:
                    kwargs["n"] = 10
                if "k" in sig.parameters and "k" not in kwargs:
                    kwargs["k"] = 10
                bound = sig.bind_partial(
                    df, **{k: v for k, v in kwargs.items() if k in sig.parameters}
                )
                bound.apply_defaults()
                raw = fn(*bound.args, **bound.kwargs)
                norm = self._to_plotly_json(raw)
                if isinstance(norm, dict) and "data" in norm:
                    results.append(norm)
                elif isinstance(norm, list):
                    for f in norm:
                        nf = self._to_plotly_json(f)
                        if isinstance(nf, dict) and "data" in nf:
                            results.append(nf)
                else:
                    prev = str(type(raw).__name__)
                    debug.append(
                        {
                            "tool": name,
                            "error": "unexpected_return_type",
                            "py_type": prev,
                        }
                    )
            except Exception as e:
                debug.append({"tool": name, "error": f"exception: {e}"})

        return (results, debug) if return_debug else results
