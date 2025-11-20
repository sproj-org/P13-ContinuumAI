"""Vizro MCP + preview helpers."""
from __future__ import annotations

import asyncio
import subprocess
import sys
import json
from pathlib import Path
from typing import Any, Dict, List

import streamlit as st
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from continuum_v1 import settings


def _clean_generated_python(code: str) -> str:
    """Strip obviously invalid dangling identifiers produced by LLM output."""
    lines: List[str] = []
    for raw in code.splitlines():
        stripped = raw.strip()
        if stripped.endswith(",") and stripped[:-1].isidentifier():
            # Drop stray tokens like "hover," that sneak into arg lists.
            continue
        lines.append(raw)
    return "\n".join(lines)


def run_async(coro):
    return asyncio.run(coro)


async def call_vizro(tool: str, arguments: Dict[str, Any]):
    mcp_executable = Path(sys.executable).with_name("vizro-mcp.exe")
    if not mcp_executable.exists():
        mcp_executable = Path(sys.executable).with_name("vizro-mcp")
    params = StdioServerParameters(
        command=str(mcp_executable),
        args=[],
    )
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            return await session.call_tool(tool, arguments=arguments)


def stop_preview_process() -> None:
    proc = st.session_state.get("preview_process")
    if proc and proc.poll() is None:
        try:
            proc.terminate()
            proc.wait(timeout=3)
        except Exception:
            proc.kill()
    st.session_state["preview_process"] = None
    st.session_state["preview_active"] = False


def start_preview_process(python_code: str) -> None:
    code = _clean_generated_python(python_code.strip())
    marker = "Vizro().build(model).run()"
    replacement = f"Vizro().build(model).run(port={settings.PREVIEW_PORT})"
    if marker in code:
        code = code.replace(marker, replacement)
    elif "Vizro().build(model).run" not in code:
        code += f"\nVizro().build(model).run(port={settings.PREVIEW_PORT})\n"
    if not code.startswith("# -*- coding: utf-8 -*-"):
        code = "# -*- coding: utf-8 -*-\n" + code
    try:
        compile(code, str(settings.PREVIEW_SCRIPT), "exec")
    except SyntaxError as exc:  # pragma: no cover - defensive guard
        st.session_state["preview_process"] = None
        st.session_state["preview_active"] = False
        st.session_state["preview_ready"] = False
        st.session_state["preview_error"] = f"Preview code error at line {exc.lineno}: {exc.msg}"
        return
    settings.PREVIEW_SCRIPT.write_text(code, encoding="utf-8")
    stop_preview_process()
    proc = subprocess.Popen([sys.executable, str(settings.PREVIEW_SCRIPT)])
    st.session_state["preview_process"] = proc
    st.session_state["preview_active"] = True
    st.session_state["preview_ready"] = False
    st.session_state.pop("preview_error", None)


def serialize_result(result: Any) -> Dict[str, Any]:
    structured = getattr(result, "structuredContent", None)
    if isinstance(structured, dict):
        return structured
    content_blocks = getattr(result, "content", None) or []
    for block in content_blocks:
        text = getattr(block, "text", None)
        if text:
            try:
                return json.loads(text)  # type: ignore[name-defined]
            except Exception:
                return {"error": text}
    return {"error": "Vizro MCP returned no structured content."}
