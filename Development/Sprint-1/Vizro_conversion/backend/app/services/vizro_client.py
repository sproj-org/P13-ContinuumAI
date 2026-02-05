"""Vizro MCP stdio client + preview helpers (lightweight mirror of vizro_app2)."""
from __future__ import annotations

import asyncio
import json
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict


def run_async(coro):
    return asyncio.run(coro)


async def call_vizro(tool: str, arguments: Dict[str, Any]):
    # Lazy import to avoid hard failure if mcp is not installed; callers should ensure dependency is present.
    try:
        from mcp import ClientSession, StdioServerParameters
        from mcp.client.stdio import stdio_client
    except ModuleNotFoundError as exc:  # pragma: no cover
        raise RuntimeError("mcp package is not installed; install vizro-mcp/mcp dependencies") from exc
    mcp_executable = Path(sys.executable).with_name("vizro-mcp.exe")
    if not mcp_executable.exists():
        mcp_executable = Path(sys.executable).with_name("vizro-mcp")
    params = StdioServerParameters(command=str(mcp_executable), args=[])
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            return await session.call_tool(tool, arguments=arguments)


def serialize_result(result: Any) -> Dict[str, Any]:
    structured = getattr(result, "structuredContent", None)
    if isinstance(structured, dict):
        return structured
    content_blocks = getattr(result, "content", None) or []
    for block in content_blocks:
        text = getattr(block, "text", None)
        if text:
            try:
                return json.loads(text)
            except Exception:
                return {"error": text}
    return {"error": "Vizro MCP returned no structured content."}
