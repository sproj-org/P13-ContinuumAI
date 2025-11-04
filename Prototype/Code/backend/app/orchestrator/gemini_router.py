from __future__ import annotations
from typing import Any, Dict, List, Callable, Tuple
import os, json, importlib, inspect, re

try:
    import google.generativeai as genai
except Exception:
    genai = None

from app.core.config import settings

def _tokenize(s: str) -> List[str]:
    s = (s or "").lower()
    return re.findall(r"[a-z0-9]+", s)

class Orchestrator:
    def __init__(self) -> None:
        self._tools = self._discover_tools()
        self._model_name = settings.GEMINI_MODEL or os.getenv("GEMINI_MODEL", "gemini-2.5-pro")
        self._gemini_ready = bool(getattr(settings, "GEMINI_API_KEY", "") and genai)
        if self._gemini_ready:
            genai.configure(api_key=settings.GEMINI_API_KEY)

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
            doc = (inspect.getdoc(obj) or "").strip()
            cats.append({"name": name, "doc": doc[:300]})
        return cats

    # ----------------- Classification -----------------

    def _build_classifier_prompt(self, message: str) -> str:
        tools_json = json.dumps(self.tool_catalog(), ensure_ascii=False)
        schema = {"response_type":"chart","tool_names":["name1"],"tool_args":{}}
        return f"""You are a BI tool router. Choose 1–2 best tools from TOOLS and minimal args for the user's request.
TOOLS:
{tools_json}
Return ONLY JSON like: {json.dumps(schema)}
User: {message}"""

    def _safe_json(self, text: str) -> Any:
        try:
            return json.loads(text)
        except Exception:
            s, e = text.find("{"), text.rfind("}")
            if s != -1 and e != -1 and e > s:
                try: return json.loads(text[s:e+1])
                except Exception: return {}
            return {}

    def _rank_tools(self, message: str) -> List[Tuple[str,float]]:
        mtoks = set(_tokenize(message))
        scores: List[Tuple[str,float]] = []
        for tname in self._tools.keys():
            ttoks = set(_tokenize(tname))
            score = 0.0
            if any(k in mtoks for k in ("top","rank","best","leaderboard")):
                if "product" in ttoks or "salespeople" in ttoks or "leaderboard" in ttoks:
                    score += 2
            if "trend" in mtoks or "over" in mtoks or "time" in mtoks:
                if any(k in ttoks for k in ("over_time","trend")):
                    score += 2
            for k in ("revenue","product","customer","city","country","region","salesperson","aov","funnel","pipeline"):
                if k in mtoks and k in ttoks:
                    score += 0.5
            if score > 0:
                scores.append((tname, score))
        return sorted(scores, key=lambda x: x[1], reverse=True)

    def classify(self, message: str) -> Dict[str, Any]:
        if self._gemini_ready:
            try:
                model = genai.GenerativeModel(self._model_name)
                resp = model.generate_content(self._build_classifier_prompt(message))
                text = resp.text if hasattr(resp, "text") else str(resp)
                parsed = self._safe_json(text)
                if isinstance(parsed, dict) and parsed.get("tool_names"):
                    return parsed
            except Exception:
                pass
        ranked = self._rank_tools(message)
        picks = [n for n,_ in ranked[:2]] or list(self._tools.keys())[:1]
        return {"response_type":"chart","tool_names": picks, "tool_args": {}}

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
            for key in ("figure","plot","payload","plotly"):
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
            a,b = obj
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
                    "data": [{
                        "type":"table",
                        "header": {"values": list(df.columns)},
                        "cells":  {"values": [df[c].tolist() for c in df.columns]},
                    }],
                    "layout": {"title": "Table"}
                }
        except Exception:
            pass

        return None

    def run_tools(self, tool_names: List[str], get_df, tool_args: Dict[str, Any], return_debug: bool=False):
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
                bound = sig.bind_partial(df, **{k:v for k,v in kwargs.items() if k in sig.parameters})
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
                    debug.append({"tool": name, "error": "unexpected_return_type", "py_type": prev})
            except Exception as e:
                debug.append({"tool": name, "error": f"exception: {e}"})

        return (results, debug) if return_debug else results
