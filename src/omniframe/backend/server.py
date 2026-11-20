"""OmniFrame Studio Backend API — FastAPI server.

Provides REST endpoints for all 18+ agent actions, WebSocket/SSE agent activity
streaming, MCP server integration, and Web UI support.

Run with:
    python -m omniframe.backend.server

Or via CLI:
    omniframe ui
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import subprocess
import sys
import uuid
from concurrent import futures
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel, Field

from omniframe.core.agent_runtime.registry import get_registry, ActionRegistry
from omniframe.core.agent_runtime.actions import register_builtin_actions
from omniframe.core.config import get_config
from omniframe.engines.code_video import render_scene, CodeScene, CodeVideoRenderer
from omniframe.engines.cartoon_2d import render_frames, CartoonScene
from omniframe.engines.compositor import Compositor
from omniframe.bridges import list_bridges, get_bridge
from omniframe.core.timeline_schema.io import load_project, load_document
from omniframe.core.errors import OmniFrameError

# ── Logging ───────────────────────────────────────────────────────────────
LOG = logging.getLogger("omniframe.backend")
LOG.setLevel(logging.INFO)
_handler = logging.StreamHandler(sys.stderr)
_handler.setFormatter(
    logging.Formatter("[%(asctime)s] %(name)s %(levelname)s %(message)s")
)
LOG.addHandler(_handler)

# ── Global state ──────────────────────────────────────────────────────────
agent_registry: Optional[ActionRegistry] = None
agent_task_log: asyncio.Queue = asyncio.Queue()  # WebSocket broadcast queue
active_connections: set[WebSocket] = set()

# ── Pydantic models for API ───────────────────────────────────────────────


class ActionInput(BaseModel):
    action: str = Field(..., description="Action name, e.g. render.code_scene")
    parameters: Dict[str, Any] = Field(
        default_factory=dict, description="JSON-compatible action parameters"
    )


class ActionOutput(BaseModel):
    success: bool = True
    result: Optional[Any] = None
    error: Optional[str] = None
    error_code: Optional[str] = None


class ProjectLoad(BaseModel):
    project_path: str = Field(..., description="Path to OmniProject JSON/YAML file")


class ProjectValidate(BaseModel):
    project_path: str = Field(..., description="Path to project file")
    check_assets: bool = True


class CheckpointSave(BaseModel):
    project_path: str = Field(..., description="Path to project file")
    label: str = "auto"


# ── Lifespan: initialize registry ────────────────────────────────────────


def _register_actions(reg: ActionRegistry) -> None:
    """Register all built-in actions."""
    register_builtin_actions(reg)


@asynccontextmanager
async def lifespan(app: FastAPI) -> Any:
    """Initialize the agent registry on server start."""
    global agent_registry
    reg = get_registry()
    _register_actions(reg)
    agent_registry = reg
    LOG.info("OmniFrame Studio backend initialized — %d actions registered", len(reg))
    yield


# ── FastAPI app ───────────────────────────────────────────────────────────

def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    app = FastAPI(
        title="OmniFrame Studio API",
        description="Backend API for OmniFrame Studio — agent-first video & animation control platform",
        version="0.1.0",
        lifespan=lifespan,
    )

    # CORS for local Web UI development
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:8765", "http://127.0.0.1:8765", "*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # ── Health ─────────────────────────────────────────────────────────────

    @app.get("/health", include_in_schema=False)
    async def health() -> Dict[str, str]:
        return {"status": "ok", "version": "0.1.0"}

    # ── Action execution ───────────────────────────────────────────────────

    @app.post("/api/v1/actions/execute", response_model=ActionOutput)
    async def execute_action(payload: ActionInput) -> ActionOutput:
        """Execute a single agent action by name with given parameters."""
        global agent_registry
        if agent_registry is None:
            return ActionOutput(
                success=False,
                error="Registry not initialized",
                error_code="E_ENGINE_UNAVAILABLE",
            )

        try:
            result = agent_registry.execute(
                action=payload.action,
                parameters=payload.parameters,
            )
            return ActionOutput(success=True, result=result)
        except OmniFrameError as e:
            return ActionOutput(
                success=False,
                error=str(e),
                error_code=e.code if hasattr(e, "code") else None,
            )
        except Exception as e:
            LOG.exception("Unexpected error executing action %s", payload.action)
            return ActionOutput(
                success=False,
                error=str(e),
                error_code="E_RENDER",
            )

    # ── Project operations ─────────────────────────────────────────────────

    @app.post("/api/v1/projects/validate")
    async def validate_project(payload: ProjectLoad) -> ActionOutput:
        """Validate an OmniProject document."""
        try:
            doc = load_project(payload.project_path)
            from omniframe.core.timeline_schema.validate import validate_project, summarize

            issues = validate_project(doc)
            summary = summarize(issues)
            return ActionOutput(
                success=True,
                result={"issues": summary, "project_path": payload.project_path},
            )
        except Exception as e:
            LOG.exception("Error validating project %s", payload.project_path)
            return ActionOutput(
                success=False,
                error=str(e),
                error_code="E_VALIDATION",
            )

    @app.post("/api/v1/projects/render")
    async def render_project(payload: ProjectLoad) -> ActionOutput:
        """Render an OmniProject to PNG frame sequence."""
        try:
            from omniframe.cli.main import run as cli_runner

            # Use CLI render subcommand
            result = cli_runner(
                ["project", "render", payload.project_path, "--out", "/tmp/omniframe_render"]
            )
            return ActionOutput(
                success=True,
                result={"message": "Render completed", "output_dir": "/tmp/omniframe_render"},
            )
        except Exception as e:
            LOG.exception("Error rendering project")
            return ActionOutput(
                success=False,
                error=str(e),
                error_code="E_RENDER",
            )

    # ── Bridge operations ───────────────────────────────────────────────────

    @app.get("/api/v1/bridges")
    async def list_bridges_api() -> ActionOutput:
        """List all DCC bridges and their availability."""
        try:
            bridges = list_bridges()
            return ActionOutput(
                success=True,
                result=bridges,
            )
        except Exception as e:
            LOG.exception("Error listing bridges")
            return ActionOutput(success=False, error=str(e))

    @app.post("/api/v1/bridges/detect")
    async def detect_bridge(payload: dict) -> ActionOutput:
        """Detect whether a host application is installed."""
        bridge_name = payload.get("bridge", "")
        try:
            bridge = get_bridge(bridge_name)
            result = bridge.detect().to_dict()
            return ActionOutput(success=True, result=result)
        except Exception as e:
            LOG.exception("Error detecting bridge %s", bridge_name)
            return ActionOutput(success=False, error=str(e))

    # ── Environment/doctor ──────────────────────────────────────────────────

    @app.get("/api/v1/environment")
    async def environment() -> ActionOutput:
        """Probe the host machine for runtimes and applications."""
        try:
            from omniframe.cli.main import doctor as doctor_cmd

            # Parse doctor output
            proc = subprocess.run(
                [sys.executable, "-m", "omniframe", "doctor"],
                capture_output=True,
                text=True,
                timeout=30,
            )
            return ActionOutput(
                success=True,
                result={"output": proc.stdout, "errors": proc.stderr},
            )
        except Exception as e:
            LOG.exception("Error running environment doctor")
            return ActionOutput(success=False, error=str(e))

    # ── WebSocket for agent activity stream ──────────────────────────────────

    @app.websocket("/ws/agent-activity")
    async def agent_activity_ws(ws: WebSocket) -> None:
        """WebSocket endpoint for real-time agent activity streaming."""
        await ws.accept()
        active_connections.add(ws)
        try:
            # Keep connection alive; messages sent via broadcast
            while True:
                await ws.receive_text()
        except WebSocketDisconnect:
            active_connections.discard(ws)
        finally:
            active_connections.discard(ws)

    async def broadcast_agent_activity(message: dict) -> None:
        """Broadcast a message to all connected WebSocket clients."""
        if active_connections:
            payload = json.dumps(message)
            disconnected: set[WebSocket] = set()
            for ws in active_connections:
                try:
                    await ws.send_text(payload)
                except Exception:
                    disconnected.add(ws)
            active_connections.difference_update(disconnected)

    # ── MCP endpoint stub ───────────────────────────────────────────────────

    @app.post("/api/v1/mcp/call", response_model=ActionOutput)
    async def mcp_call(payload: Dict[str, Any]) -> ActionOutput:
        """MCP (Model Context Protocol) tool call endpoint."""
        action = payload.get("name", "")
        parameters = payload.get("parameters", {})
        if not action:
            return ActionOutput(success=False, error="Missing action name")
        return await execute_action(ActionInput(action=action, parameters=parameters))

    # ── Serve Web UI ────────────────────────────────────────────────────────

    @app.get("/ui", include_in_schema=False)
    async def get_ui(request: Request) -> HTMLResponse:
        """Serve the Web UI HTML page."""
        ui_path = Path(__file__).parent.parent / "omniframe" / "ui" / "index.html"
        if ui_path.exists():
            content = ui_path.read_text(encoding="utf-8")
            return HTMLResponse(content=content)
        return HTMLResponse(
            content="<h1>OmniFrame Studio UI</h1>"
            "<p>Web UI not yet built. See https://github.com/omniframe-studio/omniframe-studio</p>",
            status_code=200,
        )

    return app


# ── CLI entry point ────────────────────────────────────────────────────────

def main() -> None:
    """Run the FastAPI backend server."""
    import uvicorn

    app = create_app()
    uvicorn.run(
        app,
        host="127.0.0.1",
        port=8765,
        log_level="info",
    )


if __name__ == "__main__":
    main()