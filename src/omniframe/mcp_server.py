"""OmniFrame Studio MCP (Model Context Protocol) Server.

A stdio-based MCP server that exposes all registered OmniFrame agent actions
as tool-calling endpoints. Any MCP-compatible client (Claude Code, Cursor, etc.)
can connect immediately after ``pip install -e .``.

Usage:
    python -m omniframe.mcp

Or as a CLI plugin:
    omniframe mcp

The server reads the global action registry and renders schemas via
``ActionSpec.to_tool_schema()``. It supports:
- ``list_tools`` — discover all available actions
- ``call_tool <name> <args_json>`` — execute any registered action
- ``inspect_tool <name>`` — show detailed schema for one action
- Live event emission via WebSocket (/ws/agent-activity) when UI is active
"""
from __future__ import annotations

import json
import sys
import asyncio
from pathlib import Path
from typing import Any

from .core.agent_runtime.actions import ensure_builtin_actions
from .core.agent_runtime.registry import get_registry, build_tool_manifest
from .core.errors import OmniFrameError
from .updater import get_cached_update_advisory

# ── MCP protocol constants ────────────────────────────────────────────────

JSONRPC_VERSION = "2.0"
MCP_PROTOCOL_VERSION = "2024-11-05"

INITIALIZE = "initialize"
INITIALIZE_RESULT = "initialized"
LIST_TOOLS = "tools/list"
LIST_TOOLS_LEGACY = "list_tools"
LIST_TOOLS_RESULT = "tools/list_result"
CALL_TOOL = "tools/call"
CALL_TOOL_LEGACY = "call_tool"
CALL_TOOL_RESULT = "tools/call_result"
SUPPORTED = "supported"
ERROR = "error"


# ── JSON-RPC helpers ──────────────────────────────────────────────────────

def _make_rpc_result(msg_id: Any, result: dict[str, Any]) -> dict[str, Any]:
    """Build a JSON-RPC 2.0 result envelope."""
    return {
        "jsonrpc": JSONRPC_VERSION,
        "id": msg_id,
        "result": result,
    }


def _make_rpc_error(msg_id: Any, code: int, message: str) -> dict[str, Any]:
    """Build a JSON-RPC 2.0 error envelope."""
    return {
        "jsonrpc": JSONRPC_VERSION,
        "id": msg_id,
        "error": {
            "code": code,
            "message": message,
        },
    }


def _update_fields() -> dict[str, Any]:
    """Return a cache-only advisory for MCP-aware agents."""

    advisory = get_cached_update_advisory()
    if not advisory:
        return {}
    return {"update_available": True, "update_info": advisory}


# ── MCP stdio server ──────────────────────────────────────────────────────


async def _mcp_stdio_server() -> None:
    """Run an MCP server over stdio.

    Reads JSON-RPC 2.0 messages from stdin and writes responses to stdout.
    Supports the following methods:
    - initialize / initialized
    - list_tools
    - call_tool <action_name> [args_json]
    """
    import json as _json

    buf = ""
    pending_msg: dict[str, Any] | None = None

    async def _read_line() -> str | None:
        nonlocal buf
        while True:
            ch = await asyncio.get_event_loop().run_in_executor(None, sys.stdin.read, 1)
            if ch is None or ch == "":
                return None
            if ch == "\n":
                result = buf
                buf = ""
                return result
            buf += ch

    async def _process_message(msg: dict[str, Any]) -> dict[str, Any] | None:
        """Process a single JSON-RPC message and return a response dict or None."""
        method = msg.get("method")
        msg_id = msg.get("id")
        params = msg.get("params", {})

        if method == INITIALIZE:
            # Respond with server capabilities
            registry = ensure_builtin_actions()
            tools = registry.to_tool_schemas()
            return _make_rpc_result(
                msg_id,
                {
                    "protocolVersion": MCP_PROTOCOL_VERSION,
                    "capabilities": {
                        "tools": {"listChanged": False},
                    },
                    "serverInfo": {
                        "name": "OmniFrame Studio",
                        "version": "0.1.0",
                    },
                    **_update_fields(),
                },
            )

        elif method in (LIST_TOOLS, LIST_TOOLS_LEGACY):
            registry = ensure_builtin_actions()
            tools = registry.to_tool_schemas()
            return _make_rpc_result(msg_id, {"tools": tools, **_update_fields()})

        elif method in (CALL_TOOL, CALL_TOOL_LEGACY):
            tool_name = params.get("name", "")
            tool_args = params.get("arguments", {}) or {}

            if not tool_name:
                return _make_rpc_error(msg_id, -32602, "Missing tool name")

            try:
                registry = ensure_builtin_actions()
                result = registry.execute(tool_name, tool_args)
                advisory_result = {**result, **_update_fields()}
                if method == CALL_TOOL:
                    return _make_rpc_result(
                        msg_id,
                        {
                            "content": [
                                {"type": "text", "text": json.dumps(advisory_result, ensure_ascii=False)}
                            ],
                            "structuredContent": advisory_result,
                            "isError": False,
                            **_update_fields(),
                        },
                    )
                return _make_rpc_result(msg_id, {"result": advisory_result, **_update_fields()})
            except OmniFrameError as e:
                return _make_rpc_error(
                    msg_id,
                    -32000,
                    f"OmniFrame error: {e.message}" if hasattr(e, "message") else str(e),
                )
            except Exception as e:
                return _make_rpc_error(
                    msg_id,
                    -32000,
                    f"Action execution failed: {str(e)}",
                )

        else:
            return _make_rpc_error(
                msg_id, -32601, f"Method not found: {method}"
            )

    # ── Main stdio loop ───────────────────────────────────────────────────

    while True:
        line = await _read_line()
        if line is None:
            break
        line = line.strip()
        if not line:
            continue

        try:
            msg = _json.loads(line)
        except _json.JSONDecodeError:
            sys.stdout.write(
                _json.dumps(_make_rpc_error(None, -32600, "Invalid JSON")) + "\n"
            )
            sys.stdout.flush()
            continue

        response = await _process_message(msg)
        if response is not None:
            sys.stdout.write(_json.dumps(response) + "\n")
            sys.stdout.flush()


# ── CLI entry point ───────────────────────────────────────────────────────

def main() -> None:
    """Run the OmniFrame Studio MCP server over stdio."""
    try:
        asyncio.run(_mcp_stdio_server())
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()