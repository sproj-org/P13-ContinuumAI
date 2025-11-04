from __future__ import annotations
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from app.utils.loader import load_dataframe_for_tool
from app.orchestrator.gemini_router import Orchestrator
import os, glob, json

DEBUG_ORCH = os.getenv("DEBUG_ORCH", "0") == "1"
MOCK_DIR   = os.getenv("MOCK_PLOTLY_DIR", "")

router = APIRouter(prefix="/query", tags=["query"])

class QueryRequest(BaseModel):
    message: str = Field(...)
    filters: Optional[Dict[str, Any]] = None


@router.get("/diagnostics", tags=["query"])
def diagnostics():
    try:
        from app.utils.loader import load_frames
        sales_df, opp_df = load_frames({})
        return {
            "sales_rows": 0 if sales_df is None else int(len(sales_df)),
            "sales_cols": [] if sales_df is None else list(sales_df.columns),
            "opp_rows": 0 if opp_df is None else int(len(opp_df)),
            "opp_cols": [] if opp_df is None else list(opp_df.columns),
        }
    except Exception as e:
        return {"error": f"diagnostics_failed: {e}"}


@router.get("/tools")
def list_tools():
    orch = Orchestrator()
    return {"tools": orch.tool_catalog()}

class PlanRequest(BaseModel):
    message: str

@router.post("/plan")
def plan(req: PlanRequest):
    orch = Orchestrator()
    return {"plan": orch.classify(req.message)}


# --- DEBUG: force-run a specific tool with args ---
class ForceRun(BaseModel):
    tool: str
    args: dict | None = None
    filters: dict | None = None

@router.post("/run")
def force_run(req: ForceRun):
    orch = Orchestrator()
    tool_names = [req.tool]
    tool_args = req.args or {}

    def _get_df(name: str):
        try:
            return load_dataframe_for_tool(name, req.filters or {})
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Data load failed: {e}")

    results, debug = orch.run_tools(tool_names, _get_df, tool_args, return_debug=True)
    if not results:
        return {"status":"error","message":"No results", "debug": debug}
    return {"status":"success","results":results, "debug": debug}


@router.post("", summary="LLM Orchestrated Query (returns Plotly JSON)")
def run_query(req: QueryRequest) -> Dict[str, Any]:
    orch = Orchestrator()
    plan = orch.classify(req.message)

    tool_names: List[str] = plan.get("tool_names") or []
    tool_args: Dict[str, Any] = plan.get("tool_args") or {}

    def _get_df(tool_name: str):
        try:
            return load_dataframe_for_tool(tool_name, req.filters or {})
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Data load failed: {e}")

    # 1) Try the LLM plan
    out = orch.run_tools(tool_names, _get_df, tool_args, return_debug=DEBUG_ORCH)
    if isinstance(out, tuple):
        results, debug = out
    else:
        results, debug = out, []

    # 2) If empty/mismatched, auto-fallback to ranked tools (semantic router)
    if not results:
        ranked = orch.rank_tools(req.message)[:6]  # try a few
        fallback = orch.run_tools(ranked, _get_df, tool_args, return_debug=DEBUG_ORCH)
        if isinstance(fallback, tuple):
            fres, fdbg = fallback
        else:
            fres, fdbg = fallback, []
        results, debug = fres, (debug + fdbg)

    # 3) Optional mock
    if (not results) and MOCK_DIR:
        figs = []
        for p in glob.glob(os.path.join(MOCK_DIR, "*.json"))[:2]:
            try:
                figs.append(json.load(open(p, "r")))
            except Exception:
                pass
        if figs:
            return {"status":"success","results":figs, **({"debug":debug} if DEBUG_ORCH else {})}

    if not results:
        resp = {"status": "error", "message": "I'm sorry, I couldn't find that data."}
        if DEBUG_ORCH:
            resp["debug"] = debug
        return resp

    return {"status":"success","results":results, **({"debug":debug} if DEBUG_ORCH else {})}
