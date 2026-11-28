"""OmniFrame Studio Backend API — FastAPI server.

Provides REST endpoints for the registered agent actions, WebSocket/SSE agent activity
streaming, MCP server integration, and Web UI support.

Run with:
    python -m omniframe.backend.server

Or via CLI:
    omniframe ui
"""
from __future__ import annotations

import asyncio
import base64
import json
import logging
import os
import sys
import tempfile
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, StreamingResponse
from pydantic import BaseModel, Field
from pydantic import ValidationError as PydanticValidationError

from omniframe.bridges import get_bridge, list_bridges
from omniframe.core.agent_runtime.actions import register_builtin_actions
from omniframe.core.agent_runtime.registry import ActionRegistry, get_registry
from omniframe.core.config import detect_environment
from omniframe.core.errors import OmniFrameError, RenderError, ValidationError
from omniframe.core.timeline_schema.io import load_project, save_project
from omniframe.core.timeline_schema.models import OmniProject
from omniframe.engines.code_video import CodeScene, CodeVideoRenderer
from omniframe.updater import (
    check_for_update,
    get_cached_update_advisory,
    restart_instructions,
    stream_update_events,
)

# ── Logging ───────────────────────────────────────────────────────────────
LOG = logging.getLogger("omniframe.backend")
LOG.setLevel(logging.INFO)
_handler = logging.StreamHandler(sys.stderr)
_handler.setFormatter(
    logging.Formatter("[%(asctime)s] %(name)s %(levelname)s %(message)s")
)
LOG.addHandler(_handler)

# ── Global state ──────────────────────────────────────────────────────────
agent_registry: ActionRegistry | None = None
agent_task_log: asyncio.Queue = asyncio.Queue()  # WebSocket broadcast queue
active_connections: set[WebSocket] = set()

# ── Pydantic models for API ───────────────────────────────────────────────


class ActionInput(BaseModel):
    action: str = Field(..., description="Action name, e.g. render.code_scene")
    parameters: dict[str, Any] = Field(
        default_factory=dict, description="JSON-compatible action parameters"
    )


class ActionOutput(BaseModel):
    success: bool = True
    result: Any | None = None
    error: str | None = None
    error_code: str | None = None
    update_available: bool = False
    update_info: dict[str, Any] | None = None

    def model_post_init(self, __context: Any) -> None:
        if self.update_info is None:
            advisory = get_cached_update_advisory()
            if advisory:
                self.update_available = True
                self.update_info = advisory


class ProjectLoad(BaseModel):
    project_path: str = Field(..., description="Path to OmniProject JSON/YAML file")


class ProjectValidate(BaseModel):
    project_path: str = Field(..., description="Path to project file")
    check_assets: bool = True


class InspectorValidateRequest(BaseModel):
    project: dict[str, Any] = Field(
        ..., description="In-memory OmniProject document to validate"
    )
    check_assets: bool = False


class CheckpointSave(BaseModel):
    project_path: str = Field(..., description="Path to project file")
    label: str = "auto"


class ProjectSave(BaseModel):
    project_path: str = Field(..., description="Path to write the edited project to")
    project: dict[str, Any] = Field(..., description="Full edited OmniProject document")


class PreviewFrameRequest(BaseModel):
    project_path: str = Field(..., description="Path to project file")
    frame: int = Field(..., ge=0, description="Absolute frame index in the project")
    width: int | None = Field(default=None, ge=1, description="Override preview width")
    height: int | None = Field(default=None, ge=1, description="Override preview height")
    backend: str = Field("auto", description="auto | playwright | stub")
    project: dict[str, Any] | None = Field(
        default=None,
        description=(
            "Optional in-memory project document. When present it is validated and "
            "rendered from instead of the on-disk file, so unsaved inspector edits "
            "(e.g. code.params) are reflected in the preview frame."
        ),
    )


class CompareRequest(BaseModel):
    project_path: str = Field(..., description="Path to project file")
    frames: list[int] = Field(
        default_factory=lambda: [0],
        description="Frame numbers to look at side by side in both outputs",
    )
    reference_video: str | None = Field(
        default=None, description="Optional reference video to compare against"
    )
    reference_frames_dir: str | None = Field(
        default=None, description="Optional directory of reference PNG frames"
    )
    width: int | None = Field(default=None, ge=1, description="Override preview width")
    height: int | None = Field(default=None, ge=1, description="Override preview height")
    backend: str = Field("stub", description="auto | playwright | stub")


class CompareReportRequest(BaseModel):
    project_path: str = Field(..., description="Project the run belongs to")
    compare: dict[str, Any] = Field(
        default_factory=dict, description="Compare result payload to record"
    )
    output_path: str | None = Field(
        default=None, description="Where to write the markdown gate report"
    )

class JobSubmit(BaseModel):
    kind: str = Field(..., description="Phase 2 job kind (render/compose/translate/validate)")
    payload: dict[str, Any] = Field(default_factory=dict, description="Job parameters")
    owner: str | None = Field(default=None, description="Optional job owner label")


# ── Lifespan: initialize registry ────────────────────────────────────────


def _register_actions(reg: ActionRegistry) -> None:
    """Register all built-in actions once per process."""
    if not reg.has("environment.detect"):
        register_builtin_actions(reg)


@asynccontextmanager
async def lifespan(app: FastAPI) -> Any:
    """Initialize the agent registry on server start."""
    global agent_registry
    reg = get_registry()
    _register_actions(reg)
    agent_registry = reg
    LOG.info("OmniFrame Studio backend initialized — %d actions registered", len(reg.names()))
    yield


# ── Editor preview helpers ────────────────────────────────────────────────


def _first_code_clip(project: OmniProject) -> Any:
    """Pick the first code_scene clip in track order (spec section: active clip)."""

    for track in sorted(project.tracks, key=lambda item: item.index):
        for clip in track.clips:
            if getattr(clip, "kind", None) == "code_scene":
                return clip
    return None


def _render_preview_frame(
    project: OmniProject,
    frame: int,
    width: int | None,
    height: int | None,
    backend: str,
) -> dict[str, Any]:
    """Render one exact frame; output depends only on project bytes and frame."""

    total = int(project.meta.duration_frames)
    if frame < 0 or frame >= total:
        raise ValidationError(
            "Preview frame is outside the project range.",
            frame=frame,
            duration_frames=total,
        )
    clip = _first_code_clip(project)
    if clip is None:
        raise ValidationError("Project has no code_scene clip to preview.")

    scene = CodeScene.from_clip(clip, project)
    if width is not None:
        scene.width = width
    if height is not None:
        scene.height = height
    scene.duration_frames = 1
    # The engine evaluates frame 0 of this one-frame scene. Overriding the
    # injected globals makes the scene's own pure seek(t) draw at `frame`.
    scene.javascript = (
        f"window.__OMNIFRAME_FRAME__ = {frame};\n"
        f"window.__OMNIFRAME_TOTAL_FRAMES__ = {total};\n"
        + (scene.javascript or "")
    )

    renderer = CodeVideoRenderer(backend=backend)
    with tempfile.TemporaryDirectory(prefix="omniframe-preview-") as target:
        result = renderer.render(scene, target)
        if not result.ok or not result.frames:
            message = str(result.issues[0]) if result.issues else "Preview render failed"
            raise RenderError(message)
        png = Path(result.frames[0]).read_bytes()

    return {
        "frame": frame,
        "t": frame / float(project.meta.fps),
        "fps": float(project.meta.fps),
        "width": scene.width,
        "height": scene.height,
        "verification_level": result.verification_level,
        "backend": result.backend,
        "issues": [str(issue) for issue in result.issues],
        "image_base64": base64.b64encode(png).decode("ascii"),
    }


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
    async def health() -> dict[str, str]:
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
            from omniframe.core.timeline_schema.validate import summarize, validate_project

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
            cli_runner(
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

    @app.post("/api/v1/projects/timeline")
    async def project_timeline(payload: ProjectLoad) -> ActionOutput:
        """Return the loaded OmniProject document for inspector UI.

        Additive, read-only endpoint powering the phase-4 Timeline panel. It
        surfaces the same ``omniframe.core.timeline_schema.io.load_project``
        result the CLI/validate path uses, so the UI can render sorted tracks
        and clips (kind, source, frames) without importing backend functions in
        the browser. No proprietary host or external pipeline is involved.
        """
        try:
            project = load_project(payload.project_path)
            return ActionOutput(
                success=True,
                result={
                    "project_path": payload.project_path,
                    "project": project.model_dump(mode="json"),
                },
            )
        except Exception as e:
            LOG.exception("Error loading project timeline %s", payload.project_path)
            return ActionOutput(success=False, error=str(e), error_code="E_PROJECT_LOAD")

    @app.post("/api/v1/projects/get", response_model=ActionOutput)
    async def get_project(payload: ProjectLoad) -> ActionOutput:
        """Return the full editable project document (editor counterpart of timeline)."""

        try:
            project = load_project(payload.project_path)
        except Exception as e:
            LOG.exception("Error loading project %s", payload.project_path)
            return ActionOutput(success=False, error=str(e), error_code="E_PROJECT_LOAD")
        return ActionOutput(
            success=True,
            result={
                "project_path": payload.project_path,
                "project": project.model_dump(mode="json"),
            },
        )

    @app.post("/api/v1/projects/save", response_model=ActionOutput)
    async def save_edited_project(payload: ProjectSave) -> ActionOutput:
        """Validate an edited document, then write it back atomically."""

        try:
            project = OmniProject.model_validate(payload.project)
        except Exception as e:
            return ActionOutput(success=False, error=str(e), error_code="E_VALIDATION")
        try:
            target = Path(payload.project_path)
            scratch = target.with_name("." + target.name + ".omniframe-tmp")
            save_project(project, scratch)
            os.replace(scratch, target)
        except Exception as e:
            LOG.exception("Error saving edited project %s", payload.project_path)
            return ActionOutput(success=False, error=str(e), error_code="E_VALIDATION")
        return ActionOutput(success=True, result={"project_path": str(target)})

    @app.post("/api/v1/inspector/validate", response_model=ActionOutput)
    async def inspector_validate(payload: InspectorValidateRequest) -> ActionOutput:
        """Validate an in-memory project document for the inspector.

        Runs the same semantic checks as the disk-based validate endpoint but on
        an arbitrary document, so the editor can surface schema errors (e.g.
        E_CLIP_OVERLAP) before saving without needing a file on disk.
        """

        from omniframe.core.timeline_schema.validate import summarize, validate_document

        try:
            project = OmniProject.model_validate(payload.project)
            summary = summarize(validate_document(project.model_dump(mode="json")))
            return ActionOutput(success=True, result=summary)
        except Exception as e:
            return ActionOutput(success=False, error=str(e), error_code="E_VALIDATION")

    @app.post("/api/v1/preview/frame", response_model=ActionOutput)
    async def preview_frame(payload: PreviewFrameRequest) -> ActionOutput:
        """Render one exact frame before committing to a full video render.

        When ``payload.project`` is supplied it is validated and rendered from
        instead of the on-disk file, so unsaved inspector edits (params etc.)
        are reflected in the frame. A structurally invalid in-memory document
        surfaces E_VALIDATION; schema issues are returned under
        ``result.validation`` for the inspector to display.
        """

        from omniframe.core.timeline_schema.validate import (
            summarize,
            validate_document,
        )

        try:
            if payload.project is not None:
                project = OmniProject.model_validate(payload.project)
            else:
                project = load_project(payload.project_path)

            result = await asyncio.to_thread(
                _render_preview_frame,
                project,
                payload.frame,
                payload.width,
                payload.height,
                payload.backend,
            )
            result = dict(result)
            result["validation"] = summarize(
                validate_document(project.model_dump(mode="json"))
            )
            return ActionOutput(success=True, result=result)
        except PydanticValidationError as e:
            # A malformed in-memory document (schema-level) is a validation
            # failure, not a render failure.
            return ActionOutput(success=False, error=str(e), error_code="E_VALIDATION")
        except OmniFrameError as e:
            # Includes the out-of-range and no-code-scene ValidationErrors the
            # renderer raises; their own .code (E_VALIDATION, ...) is kept.
            return ActionOutput(
                success=False, error=str(e), error_code=getattr(e, "code", "E_RENDER")
            )
        except Exception as e:
            LOG.exception("Error rendering preview frame")
            return ActionOutput(success=False, error=str(e), error_code="E_RENDER")

    @app.post("/api/v1/compare/frames", response_model=ActionOutput)
    async def compare_frames(payload: CompareRequest) -> ActionOutput:
        """Render the same frame numbers from the output and a reference."""

        from omniframe.engines.compositor.compare import build_compare

        try:
            project = load_project(payload.project_path)

            def render_frame(frame: int) -> dict[str, Any]:
                return _render_preview_frame(
                    project,
                    frame,
                    payload.width,
                    payload.height,
                    payload.backend,
                )

            result = await asyncio.to_thread(
                build_compare,
                payload.frames,
                render_frame=render_frame,
                project_path=payload.project_path,
                project_fps=float(project.meta.fps),
                total_frames=int(project.meta.duration_frames),
                reference_video=payload.reference_video,
                reference_frames_dir=payload.reference_frames_dir,
                width=payload.width,
                height=payload.height,
                backend=payload.backend,
            )
            return ActionOutput(success=True, result=result)
        except OmniFrameError as e:
            return ActionOutput(
                success=False, error=str(e), error_code=getattr(e, "code", "E_RENDER")
            )
        except Exception as e:
            LOG.exception("Error comparing frames")
            return ActionOutput(success=False, error=str(e), error_code="E_RENDER")

    @app.post("/api/v1/compare/report", response_model=ActionOutput)
    async def compare_report(payload: CompareReportRequest) -> ActionOutput:
        """Write the compare gate as markdown beside the project (or where asked)."""

        from omniframe.engines.compositor.compare import render_report_markdown
        from omniframe.engines.compositor.compare import verdict as compute_verdict
        from omniframe.jobs.safety import ensure_within

        compare = dict(payload.compare or {})
        compare.setdefault("project_path", payload.project_path)
        checklist = [dict(row) for row in (compare.get("checklist") or [])]
        if checklist:
            # The verdict is computed here and never taken from the request: a
            # client must not be able to write a PASS it did not earn.
            compare["checklist"] = checklist
            compare["verdict"] = compute_verdict(checklist)
        for row in compare.get("frames") or []:
            try:
                int(row.get("frame") or 0)
            except (TypeError, ValueError):
                return ActionOutput(
                    success=False,
                    error="Compare row has a non-numeric frame.",
                    error_code="E_VALIDATION",
                )
        try:
            text = render_report_markdown(compare)
        except Exception as e:
            LOG.exception("Error rendering compare gate report")
            return ActionOutput(success=False, error=str(e), error_code="E_VALIDATION")
        try:
            project = Path(payload.project_path)
            root = project.parent
            if payload.output_path:
                target = ensure_within(root, payload.output_path)
            else:
                target = ensure_within(
                    root, project.with_name(project.stem + "-compare-gate.md")
                )
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(text, encoding="utf-8")
        except OmniFrameError as e:
            return ActionOutput(
                success=False, error=str(e), error_code=getattr(e, "code", "E_VALIDATION")
            )
        except Exception as e:
            LOG.exception("Error writing compare gate report")
            return ActionOutput(success=False, error=str(e), error_code="E_VALIDATION")
        return ActionOutput(success=True, result={"report_path": str(target)})
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

    # ── Tools and environment/doctor ────────────────────────────────────────

    @app.get("/api/v1/tools")
    async def tools() -> ActionOutput:
        """Return the registered action schemas for the Web UI."""
        from omniframe.core.agent_runtime.actions import ensure_builtin_actions

        registry = ensure_builtin_actions()
        return ActionOutput(
            success=True,
            result={"tools": registry.to_tool_schemas(), "count": len(registry.names())},
        )

    @app.get("/api/v1/environment")
    async def environment() -> ActionOutput:
        """Probe the host machine for runtimes and applications."""
        try:
            report = detect_environment()
            report.pop("capability_map", None)
            return ActionOutput(
                success=True,
                result={
                    "report": report,
                    "output": json.dumps(report, ensure_ascii=False),
                    "errors": "",
                },
            )
        except Exception as e:
            LOG.exception("Error running environment doctor")
            return ActionOutput(success=False, error=str(e))

    # ── Update and restart helpers ──────────────────────────────────────────

    @app.get("/api/v1/system/update-status")
    async def update_status() -> ActionOutput:
        """Return cached or freshly checked GitHub update metadata."""
        status = await asyncio.to_thread(check_for_update)
        return ActionOutput(success=True, result=status)

    @app.post("/api/v1/system/update")
    async def update_system() -> StreamingResponse:
        """Stream explicit self-update progress as newline-delimited JSON."""

        def events() -> Any:
            for event in stream_update_events():
                yield json.dumps(event, ensure_ascii=False) + "\n"

        return StreamingResponse(events(), media_type="application/x-ndjson")

    @app.post("/api/v1/system/restart")
    async def restart_system() -> ActionOutput:
        """Return safe instructions for reloading the updated process."""
        return ActionOutput(success=True, result=restart_instructions())

    # ── Phase 2 job queue (only when the jobs package is importable) ────────
    #
    # JobManager/JobStore are imported here (not at module top) so server.py
    # stays importable without Phase 2. The routes below are registered only
    # when the import succeeds; a build lacking the jobs package exposes no
    # /api/v1/jobs* endpoints, and the UI degrades to a "jobs unavailable"
    # message instead of erroring.
    try:
        from omniframe.jobs import JobManager, JobStore
    except ImportError:
        JobManager = None  # type: ignore[assignment]
        JobStore = None  # type: ignore[assignment]

    if JobManager is not None:
        # Per-app lazily-created manager. Store is SQLite file-backed under a
        # fresh temp dir so operations persist across submit/status/cancel
        # calls (the store opens a new connection per operation, so a pure
        # :memory: db would not survive between calls). Re-created only if the
        # temp dir is somehow removed; Phase 2 store is per-manager, which we
        # mirror.
        _job_holder: list[dict[str, Any]] = [{}]

        def _get_job_manager() -> JobManager:
            if "manager" not in _job_holder[0]:
                db_dir = tempfile.mkdtemp(prefix="omniframe-jobs-")
                store = JobStore(db_path=os.path.join(db_dir, "jobs.db"))
                _job_holder[0]["manager"] = JobManager(store)
            return _job_holder[0]["manager"]  # type: ignore[return-value]

        @app.get("/api/v1/jobs")
        async def list_jobs() -> ActionOutput:
            """Return the Phase 2 job queue (oldest first)."""
            try:
                manager = _get_job_manager()
                jobs = manager._store.list_jobs()
                return ActionOutput(success=True, result=jobs)
            except Exception as e:
                LOG.exception("Error listing jobs")
                return ActionOutput(success=False, error=str(e), error_code="E_JOBS")

        @app.get("/api/v1/jobs/{job_id}")
        async def job_status(job_id: str) -> ActionOutput:
            """Return a single job record for polling."""
            try:
                manager = _get_job_manager()
                job = manager.status(job_id)
                if job is None:
                    return ActionOutput(
                        success=False,
                        error=f"job {job_id!r} not found",
                        error_code="E_JOB_NOT_FOUND",
                    )
                return ActionOutput(success=True, result=job)
            except Exception as e:
                LOG.exception("Error reading job %s", job_id)
                return ActionOutput(success=False, error=str(e), error_code="E_JOBS")

        @app.post("/api/v1/jobs")
        async def submit_job(payload: JobSubmit) -> ActionOutput:
            """Submit a new Phase 2 job and return its job_id immediately."""
            try:
                manager = _get_job_manager()
                job_id = manager.submit(payload.kind, payload.payload, owner=payload.owner)
                return ActionOutput(
                    success=True,
                    result={"job_id": job_id, "kind": payload.kind, "owner": payload.owner},
                )
            except Exception as e:
                LOG.exception("Error submitting job")
                return ActionOutput(success=False, error=str(e), error_code="E_JOBS")

        @app.post("/api/v1/jobs/{job_id}/cancel")
        async def cancel_job(job_id: str) -> ActionOutput:
            """Cancel a queued/running Phase 2 job."""
            try:
                manager = _get_job_manager()
                job = manager.cancel(job_id)
                if job is None:
                    return ActionOutput(
                        success=False,
                        error=f"job {job_id!r} not found",
                        error_code="E_JOB_NOT_FOUND",
                    )
                return ActionOutput(success=True, result=job)
            except Exception as e:
                LOG.exception("Error canceling job %s", job_id)
                return ActionOutput(success=False, error=str(e), error_code="E_JOBS")

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
    async def mcp_call(payload: dict[str, Any]) -> ActionOutput:
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
        ui_path = Path(__file__).resolve().parent.parent / "ui" / "index.html"
        if ui_path.exists():
            content = ui_path.read_text(encoding="utf-8")
            return HTMLResponse(content=content)
        return HTMLResponse(
            content="<h1>OmniFrame Studio UI</h1>"
            "<p>Web UI not yet built. See https://github.com/amitkumardas3624/omniframe-studio</p>",
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