from typing import Any, Dict, List, Optional
from fastapi import APIRouter, HTTPException, Depends
from fastapi.encoders import jsonable_encoder
import numpy as np
import pandas as pd
from pydantic import BaseModel, Field
from app.services.data_loader import load_data, list_filters
from app.services.llm_vizro import call_vizro_llm, extract_json
from app.services.profiler import profile_dataframe
from app.services.vizro_client import call_vizro, run_async, serialize_result
from app.state import (
    CUSTOM_CHARTS,
    CARD_COMPONENTS,
    CARD_PLANS,
    DASHBOARD_COMPONENTS,
    FILTERS,
    CHART_DATA_CACHE,
)
from app.routes.auth import get_current_user
import plotly.graph_objects as go
import plotly.express as px


class QueryRequest(BaseModel):
    message: str = Field(..., description="User prompt")
    filters: Optional[Dict[str, Any]] = None
    tool_names: Optional[List[str]] = Field(default=None, description="Explicit tools to run")


class QueryResponse(BaseModel):
    status: str
    results: List[Dict[str, Any]] = []
    kpis: List[Dict[str, Any]] = []
    meta: Dict[str, Any] = {}


router = APIRouter(tags=["query"])
GENERATED_RESULTS: List[Dict[str, Any]] = []
GENERATED_KPIS: List[Dict[str, Any]] = []


@router.get("/filters")
def get_filters():
    df = load_data()
    return list_filters(df)


@router.get("/tools")
def get_tools():
    return {"status": "deprecated"}


def _sanitize(obj: Any):
    if obj is None:
        return None
    if isinstance(obj, (str, int, float, bool)):
        return obj
    if isinstance(obj, pd.Period):
        return str(obj)
    if isinstance(obj, np.generic):
        return obj.item()
    if isinstance(obj, list):
        return [_sanitize(x) for x in obj]
    if isinstance(obj, tuple):
        return tuple(_sanitize(x) for x in obj)
    if isinstance(obj, dict):
        return {k: _sanitize(v) for k, v in obj.items()}
    return str(obj)


def _execute_plan(plan: Dict[str, Any], df: pd.DataFrame, expect_figure: bool):
    code = plan.get("chart_code") or plan.get("card_code") or ""
    name = plan.get("chart_name") or plan.get("card_name") or ""
    if not code or not name:
        return None
    # exec in shared namespace
    env = {"pd": pd, "px": px, "go": go, "df": df}
    try:
        import vizro  # type: ignore
        import vizro.models as vm  # type: ignore
        import vizro.plotly.express as vpx  # type: ignore

        env.update({"vizro": vizro, "vm": vm, "vpx": vpx})
    except Exception:
        pass

    # run any imports provided by the plan to mirror vizro_app2 behavior
    for imp in plan.get("imports") or []:
        try:
            exec(imp, env, env)
        except Exception:
            # ignore bad import lines; env already has core libs
            pass

    try:
        env["__builtins__"] = __builtins__
        exec(code, env, env)
    except Exception as e:
        raise RuntimeError(f"exec_failed: {e}")

    fn = env.get(name) or env.get(name.strip())
    if not fn or not callable(fn):
        raise RuntimeError(f"function {name} not found after exec")
    try:
        out = fn(df)
    except Exception as e:
        raise RuntimeError(f"{name} call failed: {e}")

    if expect_figure:
        if hasattr(out, "to_plotly_json"):
            return out.to_plotly_json()
        raise RuntimeError(f"{name} did not return a Plotly figure")
    else:
        return out


def _register_chart(chart_plan: Dict[str, Any], fig_json: Dict[str, Any], df: pd.DataFrame):
    chart_name = chart_plan.get("chart_name")
    component = {
        "type": "graph",
        "id": f"{chart_name}_component",
        "title": chart_name.replace("_", " ").title() if chart_name else "Chart",
        "figure": fig_json,
    }
    CUSTOM_CHARTS[:] = [c for c in CUSTOM_CHARTS if c.get("chart_name") != chart_name]
    CUSTOM_CHARTS.append(chart_plan)
    DASHBOARD_COMPONENTS[:] = [c for c in DASHBOARD_COMPONENTS if c.get("id") != component["id"]]
    DASHBOARD_COMPONENTS.append(component)
    # cache dataframe sample
    CHART_DATA_CACHE[chart_name] = {"dataframe": df.head(200)}


def _register_card(card_plan: Dict[str, Any], body: str):
    card_name = card_plan.get("card_name")
    card_component = {
        "type": "card",
        "id": f"{card_name}_card",
        "title": card_name.replace("_", " ").title() if card_name else "KPI",
        "text": body,
    }
    CARD_COMPONENTS[:] = [c for c in CARD_COMPONENTS if c.get("id") != card_component["id"]]
    CARD_COMPONENTS.append(card_component)
    CARD_PLANS[:] = [cp for cp in CARD_PLANS if cp.get("card_name") != card_name]
    CARD_PLANS.append(card_plan)


def _collect_all_plan_codes() -> List[str]:
    codes: List[str] = []
    for plan in CUSTOM_CHARTS:
        code = plan.get("chart_code")
        if code:
            codes.append(code)
    for plan in CARD_PLANS:
        code = plan.get("card_code")
        if code:
            codes.append(code)
    return codes


def _render_all_plans(df: pd.DataFrame):
    """Re-render all cached charts/cards for the current dataframe."""
    results: List[Dict[str, Any]] = []
    kpis: List[Dict[str, Any]] = []
    debug: List[Dict[str, Any]] = []

    for plan in CUSTOM_CHARTS:
        try:
            fig_json = _execute_plan(plan, df, expect_figure=True)
            if fig_json:
                results.append(fig_json)
        except Exception as e:
            debug.append({"chart_refresh_error": str(e), "chart_code": plan.get("chart_code")})

    for plan in CARD_PLANS:
        try:
            card_out = _execute_plan(plan, df, expect_figure=False)
            if isinstance(card_out, dict):
                body = card_out.get("text", "")
            else:
                body = str(card_out)
            kpis.append({"type": "kpi", "title": plan.get("card_name", "KPI"), "body": body})
        except Exception as e:
            debug.append({"card_refresh_error": str(e), "card_code": plan.get("card_code")})

    return results, kpis, debug


@router.post("/query", response_model=QueryResponse)
def run_query(req: QueryRequest, user=Depends(get_current_user)):
    df = load_data(req.filters or {})
    profile = profile_dataframe(df)
    results: List[Dict[str, Any]] = []
    kpis: List[Dict[str, Any]] = []
    debug: List[Dict[str, Any]] = []

    llm_res = call_vizro_llm(req.message, df)
    if llm_res.get("error"):
        return QueryResponse(status="error", results=[], kpis=[], meta={"debug": debug + [llm_res]})
    parsed = extract_json(llm_res.get("raw", ""))
    debug.append({"raw": llm_res.get("raw", ""), "parsed": parsed})

    chart_plan = parsed.get("chart_plan")
    card_plan = parsed.get("card_plan")

    if chart_plan:
        try:
            fig_json = _execute_plan(chart_plan, df, expect_figure=True)
            if fig_json:
                results.append(fig_json)
                _register_chart(chart_plan, fig_json, df)
        except Exception as e:
            debug.append({"chart_exec_error": str(e), "chart_code": chart_plan.get("chart_code")})
    else:
        debug.append({"chart_plan_missing": True})

    if card_plan:
        try:
            card_out = _execute_plan(card_plan, df, expect_figure=False)
            if isinstance(card_out, dict):
                body = card_out.get("text", "")
            else:
                body = str(card_out)
            kpis.append({"type": "kpi", "title": card_plan.get("card_name", "KPI"), "body": body})
            _register_card(card_plan, body)
        except Exception as e:
            debug.append({"card_exec_error": str(e), "card_code": card_plan.get("card_code")})
    else:
        debug.append({"card_plan_missing": True})

    # Re-render all plans (old + new) so the frontend gets the full dashboard
    all_results, all_kpis, refresh_debug = _render_all_plans(df)
    debug.extend(refresh_debug)
    if all_results:
        GENERATED_RESULTS.clear()
        GENERATED_RESULTS.extend(all_results)
    if all_kpis:
        GENERATED_KPIS.clear()
        GENERATED_KPIS.extend(all_kpis)

    sanitized_results = _sanitize(GENERATED_RESULTS)
    sanitized_kpis = _sanitize(GENERATED_KPIS)
    enc = lambda obj: jsonable_encoder(
        obj,
        custom_encoder={
            np.ndarray: lambda v: v.tolist(),
            pd.Period: lambda v: str(v),
        },
    )
    # Build a simple Vizro dashboard config for MCP validation (cards then charts)
    components: List[Dict[str, Any]] = []
    cards = [c for c in DASHBOARD_COMPONENTS if c.get("type") == "card"]
    charts = [c for c in DASHBOARD_COMPONENTS if c.get("type") == "graph"]
    if cards:
        components.append({"type": "container", "id": "kpi_wrap", "layout": {"type": "flex", "direction": "row", "wrap": True, "gap": "12px"}, "components": cards})
    if charts:
        components.append({"type": "container", "id": "chart_wrap", "layout": {"type": "flex", "direction": "column", "wrap": False, "gap": "16px"}, "components": charts})
    dashboard_config = {
        "title": "Dashboard",
        "theme": "vizro_dark",
        "pages": [
            {
                "title": "Page 1",
                "controls": [],
                "components": components or [],
            }
        ],
    }

    validation = None
    try:
        args = {
            "dashboard_config": dashboard_config,
            "data_infos": [profile],
            "custom_charts": CUSTOM_CHARTS,
            "auto_open": False,
        }
        validation = serialize_result(run_async(call_vizro("validate_dashboard_config", args)))
    except Exception as exc:
        validation = {"error": f"validation_failed: {exc}"}
    debug.append({"validation": validation})

    return QueryResponse(
        status="success",
        results=enc(GENERATED_RESULTS or all_results),
        kpis=enc(GENERATED_KPIS or all_kpis),
        meta={"debug": debug, "debug_codes": _collect_all_plan_codes(), "validation": validation},
    )


class RefreshRequest(BaseModel):
    filters: Optional[Dict[str, Any]] = None


@router.post("/refresh", response_model=QueryResponse)
def refresh_existing(user=Depends(get_current_user), req: RefreshRequest = None):
    """Re-run cached chart/card plans against new filters without a fresh LLM call."""
    if not CUSTOM_CHARTS and not CARD_PLANS:
        raise HTTPException(status_code=400, detail="No charts or KPIs to refresh. Run a query first.")
    filters = (req.filters if req else None) or {}
    df = load_data(filters)
    results, kpis, debug = _render_all_plans(df)

    GENERATED_RESULTS.clear()
    GENERATED_RESULTS.extend(results)
    GENERATED_KPIS.clear()
    GENERATED_KPIS.extend(kpis)

    enc = lambda obj: jsonable_encoder(
        _sanitize(obj),
        custom_encoder={
            np.ndarray: lambda v: v.tolist(),
            pd.Period: lambda v: str(v),
        },
    )
    return QueryResponse(
        status="success",
        results=enc(results),
        kpis=enc(kpis),
        meta={"debug": debug, "debug_codes": _collect_all_plan_codes()},
    )


class QuestionRequest(BaseModel):
    chart_id: Optional[str] = None
    question: str
    filters: Optional[Dict[str, Any]] = None


@router.post("/question")
def ask_question(req: QuestionRequest, user=Depends(get_current_user)):
    df = load_data(req.filters or {})
    profile = profile_dataframe(df)
    # Try to fetch chart cache; if chart_id not provided, take first entry.
    cache = CHART_DATA_CACHE or {}
    cache_df = None
    if req.chart_id and req.chart_id in cache and isinstance(cache[req.chart_id], dict):
        cache_df = cache[req.chart_id].get("dataframe")
    if cache_df is None and cache:
        first = next(iter(cache.values()))
        if isinstance(first, dict):
            cache_df = first.get("dataframe")

    chart_context = ""
    if isinstance(cache_df, pd.DataFrame):
        chart_context = cache_df.head(20).to_markdown(index=False)

    system_prompt = f"""
You are a data analyst with access to the dataset and cached chart data.

Chart sample (if available):
{chart_context or 'No chart data cached.'}

Dataset summary:
Columns: {profile.get('column_names_types')}
Stats: {profile.get('stats')}

Answer the user's question concisely. If the question can be answered from the chart data, prioritize that. Otherwise, use the dataset summary to guide your answer. Return only plain text.
""".strip()

    try:
        from openai import OpenAI
        import httpx

        client = OpenAI(http_client=httpx.Client())
        resp = client.chat.completions.create(
            model="gpt-5-mini",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": req.question},
            ],
        )
        answer = resp.choices[0].message.content or "No answer returned."
        return {"status": "success", "answer": answer}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Question failed: {exc}")
