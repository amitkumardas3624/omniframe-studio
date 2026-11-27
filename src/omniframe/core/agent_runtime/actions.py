"""The built-in action catalogue.

Every action is registered on the global registry so that ``omniframe tools``
emits a complete, machine readable contract and an MCP server can expose the
same surface.  Engine and bridge imports are deliberately *lazy* (inside the
handlers) so that a missing optional dependency never breaks ``omniframe
doctor`` or ``omniframe tools``.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from ..config import detect_environment, get_config
from ..errors import EngineUnavailable, ValidationError
from ..logging import get_logger
from .checkpoint import CheckpointStore, diff_projects
from .inspect import (
    build_contact_sheet,
    extract_frames,
    frame_strip,
    list_image_frames,
    timeline_report,
)
from .registry import ActionRegistry, get_registry
from .router import EngineRouter, RoutingRequest

LOG = get_logger("core.agent_runtime.actions")


def _project_path(value: str) -> Path:
    path = Path(value).expanduser()
    if not path.exists():
        raise ValidationError(f"Project file not found: {path}")
    return path


def register_builtin_actions(registry: ActionRegistry | None = None) -> ActionRegistry:
    """Register every built-in action and return the registry."""

    reg = registry or get_registry()

    # -- environment ----------------------------------------------------
    @reg.action(
        "environment.detect",
        description="Probe the host machine for runtimes and host applications.",
        input_schema={"type": "object", "properties": {"include_hosts": {"type": "boolean", "default": True}}},
        output_schema={"type": "object"},
        engine="core",
        tags=("doctor", "diagnostics"),
    )
    def environment_detect(include_hosts: bool = True) -> dict[str, Any]:
        report = detect_environment(include_hosts=include_hosts)
        report.pop("capability_map", None)
        return report

    # -- project --------------------------------------------------------
    @reg.action(
        "project.validate",
        description="Validate an OmniProject document and return every issue found.",
        input_schema={
            "type": "object",
            "properties": {
                "project": {"type": "string", "description": "Path to the project file."},
                "check_assets": {"type": "boolean", "default": True},
            },
            "required": ["project"],
        },
        output_schema={"type": "object"},
        engine="core",
        error_codes=("E_VALIDATION", "E_SCHEMA"),
        tags=("project", "validation"),
    )
    def project_validate(project: str, check_assets: bool = True) -> dict[str, Any]:
        from ..timeline_schema.io import load_project
        from ..timeline_schema.validate import summarize, validate_project

        path = _project_path(project)
        doc = load_project(path)
        issues = validate_project(doc, check_assets=check_assets, base_dir=path.parent)
        return {"project": str(path), **summarize(issues)}

    @reg.action(
        "project.report",
        description="Return a structured, agent-readable summary of a project timeline.",
        input_schema={
            "type": "object",
            "properties": {"project": {"type": "string"}},
            "required": ["project"],
        },
        output_schema={"type": "object"},
        engine="core",
        tags=("project", "timeline"),
    )
    def project_report(project: str) -> dict[str, Any]:
        from ..timeline_schema.io import load_project

        return timeline_report(load_project(_project_path(project)))

    @reg.action(
        "project.translate",
        description="Translate a project between the universal timeline and a host format.",
        input_schema={
            "type": "object",
            "properties": {
                "translator": {"type": "string", "description": "e.g. fcpxml, edl, capcut_draft, ae_manifest"},
                "project": {"type": "string"},
                "output": {"type": "string"},
                "direction": {"type": "string", "enum": ["to_host", "to_universal"], "default": "to_host"},
            },
            "required": ["translator", "project", "output"],
        },
        output_schema={"type": "object"},
        engine="core",
        tags=("project", "translate"),
    )
    def project_translate(
        translator: str, project: str, output: str, direction: str = "to_host"
    ) -> dict[str, Any]:
        import json

        from ..timeline_schema.io import load_document, load_project
        from ..timeline_schema.translate import get_translator

        trans = get_translator(translator)
        out = Path(output)
        out.parent.mkdir(parents=True, exist_ok=True)

        if direction == "to_universal":
            doc = load_document(_project_path(project))
            result = trans.to_universal(doc)
            out.write_text(
                json.dumps(result.model_dump(mode="json"), indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
        else:
            result = trans.from_universal(load_project(_project_path(project)))
            if isinstance(result, str):
                out.write_text(result, encoding="utf-8")
            else:
                out.write_text(
                    json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8"
                )
        return {"translator": translator, "output": str(out), "direction": direction}

    # -- routing --------------------------------------------------------
    @reg.action(
        "engine.route",
        description="Choose the best engine for a task given what is installed.",
        input_schema={
            "type": "object",
            "properties": {
                "capability": {"type": ["string", "null"], "default": None},
                "preferred_engine": {"type": ["string", "null"], "default": None},
                "required_capabilities": {"type": "array", "items": {"type": "string"}, "default": []},
                "excluded_engines": {"type": "array", "items": {"type": "string"}, "default": []},
            },
        },
        output_schema={"type": "object"},
        engine="core",
        tags=("planner",),
    )
    def engine_route(
        capability: str | None = None,
        preferred_engine: str | None = None,
        required_capabilities: list[str] | None = None,
        excluded_engines: list[str] | None = None,
    ) -> dict[str, Any]:
        router = EngineRouter()
        choice = router.route(
            RoutingRequest(
                capability=capability,
                preferred_engine=preferred_engine,
                required_capabilities=list(required_capabilities or []),
                excluded_engines=list(excluded_engines or []),
            )
        )
        return choice.to_dict()

    # -- checkpoints ----------------------------------------------------
    @reg.action(
        "checkpoint.save",
        description="Snapshot a project so a destructive edit can be rolled back.",
        input_schema={
            "type": "object",
            "properties": {
                "project": {"type": "string"},
                "label": {"type": "string", "default": "auto"},
            },
            "required": ["project"],
        },
        output_schema={"type": "object"},
        engine="core",
        mutating=True,
        tags=("checkpoint", "safety"),
    )
    def checkpoint_save(project: str, label: str = "auto") -> dict[str, Any]:
        from ..timeline_schema.io import load_project

        cfg = get_config()
        cfg.ensure_dirs()
        store = CheckpointStore(cfg.checkpoints_dir)
        cp = store.save(load_project(_project_path(project)), label=label)
        return {"checkpoint": cp.to_dict()}

    @reg.action(
        "checkpoint.list",
        description="List every stored checkpoint, newest first.",
        input_schema={"type": "object"},
        output_schema={"type": "object"},
        engine="core",
        tags=("checkpoint",),
    )
    def checkpoint_list() -> dict[str, Any]:
        cfg = get_config()
        store = CheckpointStore(cfg.checkpoints_dir)
        return {"checkpoints": [c.to_dict() for c in store.list()]}

    @reg.action(
        "checkpoint.restore",
        description="Restore a checkpoint back over a project file.",
        input_schema={
            "type": "object",
            "properties": {
                "checkpoint_id": {"type": "string"},
                "project": {"type": "string"},
            },
            "required": ["checkpoint_id", "project"],
        },
        output_schema={"type": "object"},
        engine="core",
        mutating=True,
        tags=("checkpoint", "rollback"),
    )
    def checkpoint_restore(checkpoint_id: str, project: str) -> dict[str, Any]:
        cfg = get_config()
        store = CheckpointStore(cfg.checkpoints_dir)
        target = store.restore(checkpoint_id, _project_path(project))
        return {"restored": str(target), "checkpoint_id": checkpoint_id}

    @reg.action(
        "checkpoint.diff",
        description="Diff two checkpoints and report the changes.",
        input_schema={
            "type": "object",
            "properties": {
                "before": {"type": "string"},
                "after": {"type": "string"},
            },
            "required": ["before", "after"],
        },
        output_schema={"type": "object"},
        engine="core",
        tags=("checkpoint", "diff"),
    )
    def checkpoint_diff(before: str, after: str) -> dict[str, Any]:
        cfg = get_config()
        store = CheckpointStore(cfg.checkpoints_dir)
        return store.diff(before, after)

    # -- rendering ------------------------------------------------------
    @reg.action(
        "render.code_scene",
        description="Render an HTML/CSS/JS scene frame-by-frame to PNG frames.",
        input_schema={
            "type": "object",
            "properties": {
                "html": {"type": "string"},
                "css": {"type": "string", "default": ""},
                "javascript": {"type": "string", "default": ""},
                "width": {"type": "integer", "default": 1920},
                "height": {"type": "integer", "default": 1080},
                "fps": {"type": "number", "default": 30.0},
                "duration_frames": {"type": "integer", "default": 60},
                "seed": {"type": "integer", "default": 0},
                "transparent": {"type": "boolean", "default": False},
                "output_dir": {"type": "string"},
                "resume": {"type": "boolean", "default": False},
            },
            "required": ["html", "output_dir"],
        },
        output_schema={"type": "object"},
        engine="code_video",
        error_codes=("E_RENDER", "E_ENGINE_UNAVAILABLE", "E_DEPENDENCY_MISSING"),
        tags=("render", "code"),
    )
    def render_code_scene(
        html: str,
        output_dir: str,
        css: str = "",
        javascript: str = "",
        width: int = 1920,
        height: int = 1080,
        fps: float = 30.0,
        duration_frames: int = 60,
        seed: int = 0,
        transparent: bool = False,
        resume: bool = False,
    ) -> dict[str, Any]:
        from ...engines.code_video import CodeScene, CodeVideoRenderer

        scene = CodeScene(
            html=html,
            css=css,
            javascript=javascript,
            width=width,
            height=height,
            fps=fps,
            duration_frames=duration_frames,
            seed=seed,
            transparent=transparent,
        )
        renderer = CodeVideoRenderer()
        result = renderer.render(scene, output_dir, resume=resume)
        return result.to_dict()

    @reg.action(
        "render.cartoon_frames",
        description="Render a 2D cartoon scene to a PNG frame sequence.",
        input_schema={
            "type": "object",
            "properties": {
                "scene": {"type": "object", "description": "CartoonSceneSpec shaped dict."},
                "fps": {"type": "number", "default": 30.0},
                "duration_frames": {"type": "integer", "default": 60},
                "output_dir": {"type": "string"},
                "resume": {"type": "boolean", "default": False},
            },
            "required": ["scene", "output_dir"],
        },
        output_schema={"type": "object"},
        engine="cartoon_2d",
        tags=("render", "2d"),
    )
    def render_cartoon_frames(
        scene: dict[str, Any],
        output_dir: str,
        fps: float = 30.0,
        duration_frames: int = 60,
        resume: bool = False,
    ) -> dict[str, Any]:
        from ...engines.cartoon_2d import CartoonScene, render_frames
        from ..timeline_schema.models import CartoonSceneSpec

        spec = CartoonSceneSpec.model_validate(scene)
        cartoon = CartoonScene.from_spec(spec)
        cartoon.fps = fps
        cartoon.duration_frames = duration_frames
        paths = render_frames(cartoon, output_dir, resume=resume)
        return {
            "frames": [str(p) for p in paths],
            "count": len(paths),
            "output_dir": str(Path(output_dir)),
        }

    @reg.action(
        "compose.video",
        description="Assemble PNG frames into a video with FFmpeg.",
        input_schema={
            "type": "object",
            "properties": {
                "frames": {"type": "array", "items": {"type": "string"}},
                "output": {"type": "string"},
                "fps": {"type": "number", "default": 30.0},
                "preset": {"type": "string", "default": "h264"},
            },
            "required": ["frames", "output"],
        },
        output_schema={"type": "object"},
        engine="compositor",
        error_codes=("E_RENDER", "E_ENGINE_UNAVAILABLE"),
        tags=("compose", "export"),
    )
    def compose_video(
        frames: list[str], output: str, fps: float = 30.0, preset: str = "h264"
    ) -> dict[str, Any]:
        from ...engines.compositor import Compositor

        compositor = Compositor()
        path = compositor.frames_to_video(frames, output, fps=fps, preset=preset)
        return {"output": str(path)}

    # -- inspection -----------------------------------------------------
    @reg.action(
        "inspect.media",
        description="Extract frames from a video and build a contact sheet for visual review.",
        input_schema={
            "type": "object",
            "properties": {
                "video": {"type": "string"},
                "output_dir": {"type": "string"},
                "count": {"type": "integer", "default": 12},
                "contact_sheet": {"type": ["string", "null"], "default": None},
            },
            "required": ["video", "output_dir"],
        },
        output_schema={"type": "object"},
        engine="core",
        tags=("inspect", "vision"),
    )
    def inspect_media(
        video: str, output_dir: str, count: int = 12, contact_sheet: str | None = None
    ) -> dict[str, Any]:
        frames = extract_frames(video, output_dir, count=count)
        sheet = None
        if contact_sheet:
            sheet = str(build_contact_sheet(frames, contact_sheet))
        return {
            "video": str(video),
            "frames": [str(f) for f in frames],
            "contact_sheet": sheet,
        }

    @reg.action(
        "inspect.frames",
        description="Build a contact sheet / frame strip from an existing frame directory.",
        input_schema={
            "type": "object",
            "properties": {
                "directory": {"type": "string"},
                "output": {"type": "string"},
                "columns": {"type": "integer", "default": 4},
                "strip": {"type": "boolean", "default": False},
            },
            "required": ["directory", "output"],
        },
        output_schema={"type": "object"},
        engine="core",
        tags=("inspect", "vision"),
    )
    def inspect_frames(
        directory: str, output: str, columns: int = 4, strip: bool = False
    ) -> dict[str, Any]:
        frames = list_image_frames(directory)
        path = (
            frame_strip(frames, output)
            if strip
            else build_contact_sheet(frames, output, columns=columns)
        )
        return {"output": str(path), "frames": len(frames)}

    # -- bridges --------------------------------------------------------
    @reg.action(
        "bridge.list",
        description="List every DCC bridge and its current availability.",
        input_schema={"type": "object"},
        output_schema={"type": "object"},
        engine="bridges",
        tags=("bridge", "doctor"),
    )
    def bridge_list() -> dict[str, Any]:
        from ...bridges import list_bridges

        return {"bridges": list_bridges()}

    @reg.action(
        "bridge.detect",
        description="Detect whether a host application is installed on this machine.",
        input_schema={
            "type": "object",
            "properties": {"bridge": {"type": "string"}},
            "required": ["bridge"],
        },
        output_schema={"type": "object"},
        engine="bridges",
        tags=("bridge", "doctor"),
    )
    def bridge_detect(bridge: str) -> dict[str, Any]:
        from ...bridges import get_bridge

        return get_bridge(bridge).detect().to_dict()

    @reg.action(
        "bridge.generate_script",
        description="Generate a host script or project document for an OmniProject.",
        input_schema={
            "type": "object",
            "properties": {
                "bridge": {"type": "string"},
                "project": {"type": "string"},
                "output_dir": {"type": "string"},
            },
            "required": ["bridge", "project", "output_dir"],
        },
        output_schema={"type": "object"},
        engine="bridges",
        tags=("bridge", "automation"),
    )
    def bridge_generate_script(bridge: str, project: str, output_dir: str) -> dict[str, Any]:
        from ...bridges import get_bridge
        from ..timeline_schema.io import load_project

        doc = load_project(_project_path(project))
        script = get_bridge(bridge).generate_script(doc, output_dir)
        return script.to_dict()

    @reg.action(
        "bridge.inspect",
        description="Read-only structural inspection of a host project file or folder.",
        input_schema={
            "type": "object",
            "properties": {
                "bridge": {"type": "string"},
                "target": {"type": "string"},
            },
            "required": ["bridge", "target"],
        },
        output_schema={"type": "object"},
        engine="bridges",
        tags=("bridge", "rae", "inspect"),
    )
    def bridge_inspect(bridge: str, target: str) -> dict[str, Any]:
        from ...bridges import get_bridge

        return get_bridge(bridge).inspect(target)

    # -- diffing --------------------------------------------------------
    @reg.action(
        "timeline.diff",
        description="Diff two project documents.",
        input_schema={
            "type": "object",
            "properties": {
                "before": {"type": "string"},
                "after": {"type": "string"},
            },
            "required": ["before", "after"],
        },
        output_schema={"type": "object"},
        engine="core",
        tags=("diff", "timeline"),
    )
    def timeline_diff_action(before: str, after: str) -> dict[str, Any]:
        from ..timeline_schema.io import load_project

        return diff_projects(
            load_project(_project_path(before)), load_project(_project_path(after))
        )

    # -- compare gate ---------------------------------------------------
    @reg.action(
        "compare.frames",
        description="Render frame pairs against a reference reel and report the 7A gate verdict.",
        input_schema={
            "type": "object",
            "properties": {
                "project": {"type": "string", "description": "Path to the project file."},
                "frames": {
                    "type": "array",
                    "items": {"type": "integer"},
                    "description": "Frames to compare; defaults to frame 0.",
                    "default": [0],
                },
                "reference_video": {"type": ["string", "null"], "default": None},
                "reference_frames_dir": {"type": ["string", "null"], "default": None},
                "width": {"type": ["integer", "null"], "default": None},
                "height": {"type": ["integer", "null"], "default": None},
                "backend": {"type": "string", "default": "stub"},
            },
            "required": ["project"],
        },
        output_schema={"type": "object"},
        engine="compositor",
        error_codes=("E_VALIDATION", "E_RENDER", "E_ENGINE_UNAVAILABLE"),
        tags=("compare", "gate"),
    )
    def compare_frames(
        project: str,
        frames: list[int] | None = None,
        reference_video: str | None = None,
        reference_frames_dir: str | None = None,
        width: int | None = None,
        height: int | None = None,
        backend: str = "stub",
    ) -> dict[str, Any]:
        """Render the frames once each and gate them against the reference.

        The frame bytes are dropped from the result on purpose: an action
        result is read by a CLI, an MCP client and the Studio panel, and none
        of them wants several megabytes of base64 for a verdict that is four
        lists. The HTTP endpoint keeps the bytes for the image pairs.
        """

        from ...engines.compositor.compare import build_compare
        from ..timeline_schema.io import load_project

        try:
            # Reused rather than copied: one implementation of the
            # frame-override trick keeps the action and the preview honest.
            from ...backend.server import _render_preview_frame as render_preview_frame
        except ImportError as exc:
            raise EngineUnavailable(
                "compare.frames needs the preview renderer from the ui extra."
            ) from exc

        path = _project_path(project)
        document = load_project(path)
        total = int(document.meta.duration_frames)
        wanted = [int(frame) for frame in (frames or [0])]
        for frame in wanted:
            if frame < 0 or frame >= total:
                raise ValidationError(
                    "Compare frame is outside the project range.",
                    frame=frame,
                    duration_frames=total,
                )

        report = build_compare(
            wanted,
            render_frame=lambda frame: render_preview_frame(
                document, frame, width, height, backend
            ),
            project_path=path,
            project_fps=float(document.meta.fps),
            total_frames=total,
            reference_video=reference_video,
            reference_frames_dir=reference_frames_dir,
            width=width,
            height=height,
            backend=backend,
        )
        return {
            "project_path": report.get("project_path"),
            "total_frames": report.get("total_frames"),
            "reference_supplied": report.get("reference_supplied"),
            "reference_kind": report.get("reference_kind"),
            "reference_fps": report.get("reference_fps"),
            "frames": [
                {
                    "frame": row.get("frame"),
                    "reference_frame": row.get("reference_frame"),
                    "diff": row.get("diff"),
                    "verification_level": row.get("verification_level"),
                }
                for row in report.get("frames") or []
            ],
            "checklist": [
                {"id": item.get("id"), "status": item.get("status")}
                for item in report.get("checklist") or []
            ],
            "verdict": report.get("verdict"),
        }

    return reg


def ensure_builtin_actions() -> ActionRegistry:
    """Register the built-ins once per process."""

    reg = get_registry()
    if not reg.has("environment.detect"):
        register_builtin_actions(reg)
    return reg
