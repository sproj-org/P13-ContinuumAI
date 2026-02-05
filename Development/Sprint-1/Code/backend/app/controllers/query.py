from __future__ import annotations
from typing import Any, Dict, List, Optional, Union, Literal
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from app.utils.loader import load_dataframe_for_tool, load_frames
from app.orchestrator.gemini_router import Orchestrator

import os, glob, json
import re

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
        return {"status": "success", "rows": len(df), "columns": list(df.columns)}
    except Exception as e:
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
    # Allow a deterministic override for simple forecasting requests so users
    # who write "predict/forecast ... next 4 weeks" are routed to the
    # basic_sales_forecast tool even if the LLM classifier misses it.
    msg = (req.message or "")
    forecast_match = re.search(r"\b(predict|forecast|forecasting|prediction)\b", msg, re.I)
    correlation_match = re.search(r"\b(correlation|correlations|relationship|relationships|driver|drivers|influence|influences|factor|factors)\b", msg, re.I)

    def _parse_periods(message: str):
        # Parse patterns: "next 4 weeks", "next 2 months", "next 1 year", "for 3 days"
        # Convert everything to weeks for consistent forecasting
        m = re.search(r"(?:next|for|in)\s+(\d+)\s*(week|weeks|wk|w|month|months|mo|year|years|yr|y|day|days|d)\b", message, re.I)
        if not m:
            return None
        n = int(m.group(1))
        unit = m.group(2).lower()
        
        # Convert all time units to weeks
        if unit.startswith("week") or unit in ("wk", "w"):
            # Already in weeks
            weeks = n
        elif unit.startswith("month") or unit == "mo":
            # 1 month ≈ 4 weeks
            weeks = n * 4
        elif unit.startswith("year") or unit in ("yr", "y"):
            # 1 year ≈ 52 weeks
            weeks = n * 52
        elif unit.startswith("day") or unit == "d":
            # 7 days = 1 week (round up)
            weeks = max(1, (n + 6) // 7)  # Round up to nearest week
        else:
            return None
        
        return {"periods": weeks, "resample": "W"}

    plan = orch.classify(req.message)
    
    # Override 1: If user explicitly asked to forecast
    if forecast_match:
        parsed = _parse_periods(msg) or {"periods": 4, "resample": "W"}
        plan = {"response_type": "chart", "tool_names": ["basic_sales_forecast"], "tool_args": parsed}
    
    # Override 2: If user asks about correlations/relationships/drivers
    elif correlation_match:
        plan = {"response_type": "chart", "tool_names": ["correlation_analysis"], "tool_args": {}}

    tool_names: List[str] = plan.get("tool_names") or []
    tool_args: Dict[str, Any] = plan.get("tool_args") or {}

    allowed_filter_keys = {"date_from","date_to","regions","reps","categories"}
    derived_filters = {k: v for k, v in tool_args.items() if k in allowed_filter_keys}
    # Merge filters but only keep allowed keys for data loading
    merged_filters = {**(derived_filters or {}), **(req.filters or {})}
    final_filters = {k: v for k, v in merged_filters.items() if k in allowed_filter_keys}


    def _get_df(tool_name: str):
        try:
            return load_dataframe_for_tool(tool_name, final_filters)
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Data load failed: {e}")

    # 1) Try the LLM plan
    out = orch.run_tools(tool_names, _get_df, tool_args, return_debug=True)
    if isinstance(out, tuple):
        results, debug = out
    else:
        results, debug = out, []
    
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
            # Convert mock results to PlotlyObject format
            plotly_objects = [PlotlyObject(**fig) for fig in figs]
            return QuerySuccessResponse(results=plotly_objects)

    if not results:
        return QueryErrorResponse(message="I'm sorry, I couldn't find that data.")

    # Convert results to PlotlyObject format
    try:
        plotly_objects = [PlotlyObject(**result) for result in results]
        return QuerySuccessResponse(results=plotly_objects)
    except Exception as e:
        return QueryErrorResponse(message=f"Error formatting results: {str(e)}")
