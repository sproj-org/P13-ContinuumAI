from typing import Any, Dict, List, Optional
from fastapi import APIRouter, HTTPException, Depends
from fastapi.encoders import jsonable_encoder
import numpy as np
import pandas as pd
from pydantic import BaseModel, Field
from app.services.data_loader import load_data, list_filters
from app.services.llm_vizro import call_vizro_llm, extract_json
from app.state import (
    CUSTOM_CHARTS,
    CARD_COMPONENTS,
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


@router.post("/query", response_model=QueryResponse)
def run_query(req: QueryRequest, user=Depends(get_current_user)):
    df = load_data(req.filters or {})
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

    # accumulate like vizro app file regeneration
    GENERATED_RESULTS.extend(results)
    GENERATED_KPIS.extend(kpis)

    sanitized_results = _sanitize(GENERATED_RESULTS)
    sanitized_kpis = _sanitize(GENERATED_KPIS)
    enc = lambda obj: jsonable_encoder(
        obj,
        custom_encoder={
            np.ndarray: lambda v: v.tolist(),
            pd.Period: lambda v: str(v),
        },
    )
    return QueryResponse(
        status="success",
        results=enc(sanitized_results),
        kpis=enc(sanitized_kpis),
        meta={"debug": debug},
    )
