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


# --------------------
# Guardrail message
# --------------------
ALLOWED_FILTERS = ["date_from","date_to","regions","reps","categories"]

def _guardrail_message() -> QueryErrorResponse:
    examples = [
        "Total revenue for 2025-01-01 to 2025-03-31",
        "Revenue by region for Q2 2025",
        "Top 10 products by revenue (2025)",
        "Monthly sales trend for West (H1 2025)",
        "Sales by representative (Jan–Mar 2025)",
    ]
    hint = (
        "This request doesn’t match the available analytics right now. \n"
        "Ask about descriptive BI on the demo dataset. \n"
        f"You can filter with: {', '.join(ALLOWED_FILTERS)}. \n"
        "Examples: " + "; ".join(examples)
    )
    return QueryErrorResponse(message=hint)
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
    print("DEBUG|plan_from_classifier:", plan)  # TEMP

    tool_names: List[str] = plan.get("tool_names") or []
    tool_args: Dict[str, Any] = plan.get("tool_args") or {}
    print(
        f"[DEBUG] Tools to run: {tool_names}, Args: {tool_args}"
    )  # Debug: Check tools and args

    allowed_filter_keys = {"date_from","date_to","regions","reps","categories"}
    derived_filters = {k: v for k, v in tool_args.items() if k in allowed_filter_keys}
    final_filters = {**(derived_filters or {}), **(req.filters or {})}  # explicit req.filters win


    def _get_df(tool_name: str):
        try:
            return load_dataframe_for_tool(tool_name, final_filters)
        except Exception as e:
            print("DEBUG|_get_df tool=", tool_name, "final_filters=", final_filters)
            raise HTTPException(status_code=500, detail=f"Data load failed: {e}")

    # 1) Try the LLM plan
    out = orch.run_tools(tool_names, _get_df, tool_args, return_debug=True)
    if isinstance(out, tuple):
        results, debug = out
    else:
        results, debug = out, []
    # print(
    #     f"[DEBUG] Results from LLM plan: {results}, Debug: {debug}"
    # )  # Debug: Check results from the plan

    
    # 2) If empty/mismatched, return guardrail instead of fallback
    if not results:
        return _guardrail_message()
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
