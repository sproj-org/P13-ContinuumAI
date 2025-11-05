from __future__ import annotations
from typing import Any, Dict, List, Optional, Union, Literal
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from app.utils.loader import load_dataframe_for_tool, load_frames
from app.orchestrator.gemini_router import Orchestrator

import os, glob, json

DEBUG_ORCH = os.getenv("DEBUG_ORCH", "0") == "1"
MOCK_DIR = os.getenv("MOCK_PLOTLY_DIR", "")


# Response models matching frontend API contract
class PlotlyObject(BaseModel):
    """A complete Plotly chart object with data and layout"""

    data: List[Any] = Field(..., description="Plotly data array")
    layout: Dict[str, Any] = Field(
        default_factory=dict, description="Plotly layout object"
    )
    config: Optional[Dict[str, Any]] = Field(
        default=None, description="Optional Plotly config"
    )


class QuerySuccessResponse(BaseModel):
    """Success response matching frontend expectations"""

    status: Literal["success"] = "success"
    results: List[PlotlyObject] = Field(
        ..., description="Array of Plotly chart objects"
    )


class QueryErrorResponse(BaseModel):
    """Error response matching frontend expectations"""

    status: Literal["error"] = "error"
    message: str = Field(..., description="Error message")


# Union type for all possible responses
QueryResponse = Union[QuerySuccessResponse, QueryErrorResponse]

router = APIRouter(prefix="/query", tags=["query"])


class QueryRequest(BaseModel):
    message: str = Field(...)
    filters: Optional[Dict[str, Any]] = None


@router.get("/diagnostics", tags=["query"])
def diagnostics():
    """
    Perform diagnostics on the loaded DataFrame.
    """
    try:
        df = load_frames()  # Load the single DataFrame
        print(
            f"[DEBUG] Diagnostics: Loaded DataFrame with {len(df)} rows and columns: {df.columns}"
        )  # Debug: Check DataFrame details
        return {"status": "success", "rows": len(df), "columns": list(df.columns)}
    except Exception as e:
        print(f"[DEBUG] Diagnostics failed: {e}")  # Debug: Log the error
        return {"status": "error", "message": str(e)}


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
        return {"status": "error", "message": "No results", "debug": debug}
    return {"status": "success", "results": results, "debug": debug}


@router.post("", summary="LLM Orchestrated Query (returns Plotly JSON)")
def run_query(req: QueryRequest) -> QueryResponse:
    orch = Orchestrator()
    print(f"[DEBUG] Received query: {req.message}")  # Debug: Check the input message
    plan = orch.classify(req.message)
    print(
        f"[DEBUG] Classification plan: {plan}"
    )  # Debug: Check the classification plan

    tool_names: List[str] = plan.get("tool_names") or []
    tool_args: Dict[str, Any] = plan.get("tool_args") or {}
    print(
        f"[DEBUG] Tools to run: {tool_names}, Args: {tool_args}"
    )  # Debug: Check tools and args

    def _get_df(tool_name: str):
        try:
            return load_dataframe_for_tool(tool_name, req.filters or {})
        except Exception as e:
            print(
                f"[DEBUG] Dataframe load failed for {tool_name}: {e}"
            )  # Debug: Check data loading errors
            raise HTTPException(status_code=500, detail=f"Data load failed: {e}")

    # 1) Try the LLM plan
    out = orch.run_tools(tool_names, _get_df, tool_args, return_debug=DEBUG_ORCH)
    if isinstance(out, tuple):
        results, debug = out
    else:
        results, debug = out, []
    # print(
    #     f"[DEBUG] Results from LLM plan: {results}, Debug: {debug}"
    # )  # Debug: Check results from the plan

    # 2) If empty/mismatched, auto-fallback to ranked tools (semantic router)
    if not results:
        ranked = orch.rank_tools(req.message)[:6]  # try a few
        print(
            f"[DEBUG] Ranked tools for fallback: {ranked}"
        )  # Debug: Check fallback tools
        fallback = orch.run_tools(ranked, _get_df, tool_args, return_debug=DEBUG_ORCH)
        if isinstance(fallback, tuple):
            fres, fdbg = fallback
        else:
            fres, fdbg = fallback, []
        results, debug = fres, (debug + fdbg)
        print(
            f"[DEBUG] Results from fallback: {results}, Debug: {debug}"
        )  # Debug: Check fallback results

    # 3) Optional mock
    if (not results) and MOCK_DIR:
        figs = []
        for p in glob.glob(os.path.join(MOCK_DIR, "*.json"))[:2]:
            try:
                figs.append(json.load(open(p, "r")))
            except Exception:
                pass
        if figs:
            print(f"[DEBUG] Mock results: {figs}")  # Debug: Check mock results
            # Convert mock results to PlotlyObject format
            plotly_objects = [PlotlyObject(**fig) for fig in figs]
            return QuerySuccessResponse(results=plotly_objects)

    if not results:
        print(
            f"[DEBUG] Final response: No results found"
        )  # Debug: Check final error response
        return QueryErrorResponse(message="I'm sorry, I couldn't find that data.")

    # Convert results to PlotlyObject format
    try:
        plotly_objects = [PlotlyObject(**result) for result in results]
        return QuerySuccessResponse(results=plotly_objects)
    except Exception as e:
        print(f"[DEBUG] Error converting results to PlotlyObject: {e}")
        return QueryErrorResponse(message=f"Error formatting results: {str(e)}")
