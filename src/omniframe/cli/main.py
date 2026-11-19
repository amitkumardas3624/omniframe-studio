"""The ``omniframe`` command line interface.

Every command works head-lessly and can emit JSON, so an agent can drive the
whole platform without scraping human-readable output.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any, Optional

import typer

from .. import __version__
from ..core.config import detect_environment, get_config
from ..core.errors import OmniFrameError
from ..core.logging import get_logger, setup_logging

LOG = get_logger("cli")

app = typer.Typer(
    name="omniframe",
    help="OmniFrame Studio — agent-first video and animation control platform.",
    no_args_is_help=True,
    add_completion=False,
)

project_app = typer.Typer(help="Project lifecycle commands.", no_args_is_help=True)
checkpoint_app = typer.Typer(help="Checkpoint and rollback commands.", no_args_is_help=True)
bridge_app = typer.Typer(help="Host application bridge commands.", no_args_is_help=True)
app.add_typer(project_app, name="project")
app.add_typer(checkpoint_app, name="checkpoint")
app.add_typer(bridge_app, name="bridge")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _echo_json(payload: Any) -> None:
    typer.echo(json.dumps(payload, indent=2, ensure_ascii=False, default=str))


def _fail(message: str, code: int = 1) -> None:
    typer.secho(message, fg=typer.colors.RED, err=True)
    raise typer.Exit(code)


def _load_project(path: str):
    from ..core.timeline_schema.io import load_project

    target = Path(path).expanduser()
    if not target.exists():
        _fail(f"Project file not found: {target}")
    return load_project(target)


# ---------------------------------------------------------------------------
# Root commands
# ---------------------------------------------------------------------------

@app.command()
def version() -> None:
    """Print the OmniFrame Studio version."""

    _echo_json({"name": "omniframe-studio", "version": __version__, "python": sys.version.split()[0]})


@app.command()
def doctor(
    json_output: bool = typer.Option(False, "--json", help="Emit the report as JSON."),
    fix: bool = typer.Option(False, "--fix", help="Try to install missing optional dependencies."),
) -> None:
    """Check the machine: runtimes, FFmpeg, browser and host applications."""

    report = detect_environment()
    report.pop("capability_map", None)

    if fix:
        report["fix_attempts"] = _run_fixes(report)

    if json_output:
        _echo_json(report)
        raise typer.Exit(0 if report["ready"] else 1)

    typer.secho("OmniFrame Studio — environment doctor", bold=True)
    typer.secho("─" * 60)
    for cap in report["capabilities"]:
        mark = typer.style("✓", fg=typer.colors.GREEN) if cap["available"] else typer.style("✗", fg=typer.colors.RED)
        version = f"  {cap['version']}" if cap.get("version") else ""
        typer.echo(f"{mark} {cap['name']:<18}{version}")
        if not cap["available"] and cap.get("detail"):
            typer.secho(f"    {cap['detail']}", fg=typer.colors.YELLOW)
    typer.secho("─" * 60)
    if report["missing"]:
        typer.secho(f"missing: {', '.join(report['missing'])}", fg=typer.colors.YELLOW)
    typer.secho(
        "ready" if report["ready"] else "not ready — install the missing pieces above",
        fg=typer.colors.GREEN if report["ready"] else typer.colors.RED,
    )
    raise typer.Exit(0 if report["ready"] else 1)


def _run_fixes(report: dict[str, Any]) -> list[dict[str, Any]]:
    """Best-effort installation of missing optional dependencies."""

    attempts: list[dict[str, Any]] = []
    missing = {c["name"] for c in report["capabilities"] if not c["available"]}

    if "chromium" in missing:
        try:
            subprocess.run(
                [sys.executable, "-m", "playwright", "install", "chromium"],
                check=True,
                capture_output=True,
            )
            attempts.append({"component": "chromium", "status": "installed"})
        except Exception as exc:
            attempts.append({"component": "chromium", "status": "failed", "error": str(exc)})

    return attempts


@app.command()
def tools(
    output: Optional[str] = typer.Option(None, "--out", help="Write the tool manifest to a file."),
    list_only: bool = typer.Option(False, "--list", help="Print just the action names."),
) -> None:
    """Print the JSON tool manifest that agents program against."""

    from ..core.agent_runtime.actions import ensure_builtin_actions

    registry = ensure_builtin_actions()
    if list_only:
        for name in registry.names():
            typer.echo(name)
        return

    manifest = registry.to_json_document()
    if output:
        target = Path(output).expanduser()
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(
            json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        typer.secho(f"tool manifest written to {target}", fg=typer.colors.GREEN)
        return
    _echo_json(manifest)


@app.command()
def run_tool(
    name: str = typer.Argument(..., help="Action name, e.g. environment.detect."),
    params: Optional[str] = typer.Option(None, "--params", help="JSON object of arguments."),
) -> None:
    """Execute a registered action and print its JSON result."""

    from ..core.agent_runtime.actions import ensure_builtin_actions

    registry = ensure_builtin_actions()
    payload: dict[str, Any] = {}
    if params:
        try:
            payload = json.loads(params)
        except json.JSONDecodeError as exc:
            _fail(f"--params is not valid JSON: {exc}")
    try:
        result = registry.execute(name, payload)
    except OmniFrameError as exc:
        _echo_json(exc.to_dict())
        raise typer.Exit(1)
    _echo_json(result)


@app.command()
def route(
    capability: Optional[str] = typer.Option(None, "--capability", help="Capability to satisfy."),
    preferred: Optional[str] = typer.Option(None, "--preferred", help="Preferred engine id."),
) -> None:
    """Show which engine would be selected for a task."""

    from ..core.agent_runtime.router import EngineRouter, RoutingRequest

    router = EngineRouter()
    choice = router.route(RoutingRequest(capability=capability, preferred_engine=preferred))
    _echo_json(choice.to_dict())


# ---------------------------------------------------------------------------
# Project commands
# ---------------------------------------------------------------------------

@project_app.command("init")
def project_init(
    name: str = typer.Argument(..., help="Project name."),
    directory: str = typer.Option(".", "--dir", help="Where to create the project folder."),
    fps: float = typer.Option(30.0, "--fps"),
    width: int = typer.Option(1920, "--width"),
    height: int = typer.Option(1080, "--height"),
) -> None:
    """Create a new OmniFrame project from the starter template."""

    from ..core.timeline_schema.models import OmniProject, ProjectMeta

    root = Path(directory).expanduser() / name
    root.mkdir(parents=True, exist_ok=True)

    project = OmniProject(
        meta=ProjectMeta(name=name, fps=fps, width=width, height=height, duration_frames=0),
        metadata={"created_by": "omniframe-studio", "template": "starter"},
    )
    project_path = root / "project.json"
    project_path.write_text(
        json.dumps(project.model_dump(mode="json"), indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    scenes = root / "scenes"
    scenes.mkdir(exist_ok=True)
    (scenes / "hello.js").write_text(
        "// Draw a frame number badge. __OMNIFRAME_FRAME__ is the current frame.\n"
        "const el = document.getElementById('badge');\n"
        "if (el) { el.textContent = 'Frame ' + __OMNIFRAME_FRAME__; }\n",
        encoding="utf-8",
    )

    typer.secho(f"created {project_path}", fg=typer.colors.GREEN)
    _echo_json({"project": str(project_path), "scenes_dir": str(scenes)})


@project_app.command("validate")
def project_validate(
    project: str = typer.Argument(..., help="Path to the project file."),
    json_output: bool = typer.Option(False, "--json"),
) -> None:
    """Validate a project document and report every issue."""

    from ..core.timeline_schema.validate import summarize, validate_project

    target = Path(project).expanduser()
    doc = _load_project(project)
    issues = validate_project(doc, check_assets=True, base_dir=target.parent)
    report = summarize(issues)

    if json_output:
        _echo_json(report)
        raise typer.Exit(0 if report["ok"] else 1)

    if report["ok"]:
        typer.secho("project is valid", fg=typer.colors.GREEN)
    else:
        typer.secho(f"{report['counts'].get('error', 0)} error(s) found", fg=typer.colors.RED)
    for issue in report["issues"]:
        colour = {
            "error": typer.colors.RED,
            "warning": typer.colors.YELLOW,
            "info": typer.colors.CYAN,
        }.get(issue["severity"], typer.colors.WHITE)
        typer.secho(
            f"  [{issue['severity']}] {issue['code']} {issue['path']}: {issue['message']}",
            fg=colour,
        )
    raise typer.Exit(0 if report["ok"] else 1)


@project_app.command("report")
def project_report(
    project: str = typer.Argument(...),
    json_output: bool = typer.Option(False, "--json"),
) -> None:
    """Print a structured timeline summary of a project."""

    from ..core.agent_runtime.inspect import timeline_report

    doc = _load_project(project)
    report = timeline_report(doc)
    if json_output:
        _echo_json(report)
        return
    typer.secho(f"{report['name']} — {report['resolution'][0]}x{report['resolution'][1]} @ {report['fps']}fps")
    typer.secho(f"duration: {report['duration_seconds']}s ({report['timecode']})")
    for track in report["tracks"]:
        typer.echo(f"  [{track['kind']}] {track['name']} — {track['clip_count']} clip(s)")
        for clip in track["clips"]:
            typer.echo(f"      {clip['id']:<16}{clip['timecode']}  {clip['name']}")


@project_app.command("render")
def project_render(
    project: str = typer.Argument(...),
    output: str = typer.Option("renders", "--out", help="Directory for the rendered frames."),
    engine: str = typer.Option("auto", "--engine", help="auto | code_video | cartoon_2d"),
    backend: str = typer.Option("auto", "--backend", help="auto | playwright | stub"),
    resume: bool = typer.Option(False, "--resume", help="Skip frames that already exist."),
) -> None:
    """Render every renderable clip of a project to PNG frames."""

    doc = _load_project(project)
    out_dir = Path(output).expanduser()
    out_dir.mkdir(parents=True, exist_ok=True)

    results: list[dict[str, Any]] = []
    for track in doc.sorted_tracks():
        for clip in track.sorted_clips():
            kind = clip.kind.value
            if kind == "code_scene":
                from ..engines.code_video import CodeScene, CodeVideoRenderer

                if clip.code is None:
                    _fail(f"clip '{clip.id}' is a code_scene but has no code payload")
                scene = CodeScene(
                    html=clip.code.html,
                    css=clip.code.css,
                    javascript=clip.code.javascript,
                    bootstrap=clip.code.bootstrap,
                    width=doc.meta.width,
                    height=doc.meta.height,
                    fps=doc.meta.fps,
                    duration_frames=clip.duration_frames,
                    seed=clip.code.seed,
                    transparent=clip.code.transparent,
                    background=clip.code.background,
                    params=clip.code.params,
                    settle_timeout_ms=clip.code.settle_timeout_ms,
                )
                renderer = CodeVideoRenderer(backend=backend)
                result = renderer.render(scene, out_dir / clip.id, resume=resume)
                results.append({"clip": clip.id, **result.to_dict()})
            elif kind == "cartoon_layer":
                from ..engines.cartoon_2d import CartoonScene, render_frames

                if clip.cartoon is None:
                    _fail(f"clip '{clip.id}' is a cartoon_layer but has no cartoon payload")
                cartoon = CartoonScene.from_spec(clip.cartoon)
                cartoon.fps = doc.meta.fps
                cartoon.duration_frames = clip.duration_frames
                paths = render_frames(cartoon, out_dir / clip.id, resume=resume)
                results.append(
                    {
                        "clip": clip.id,
                        "frames": [str(p) for p in paths],
                        "count": len(paths),
                        "ok": True,
                    }
                )
            else:
                continue

    _echo_json({"output_dir": str(out_dir), "results": results})
    failed = [r for r in results if not r.get("ok", True)]
    raise typer.Exit(1 if failed else 0)


@project_app.command("compose")
def project_compose(
    project: str = typer.Argument(...),
    output: Optional[str] = typer.Option(None, "--out", help="Output video file."),
    preset: str = typer.Option("h264", "--preset"),
    frames_dir: Optional[str] = typer.Option(None, "--frames", help="Directory of PNG frames."),
) -> None:
    """Compose rendered frames into a video with FFmpeg."""

    from ..engines.compositor import Compositor

    doc = _load_project(project)
    target = Path(output).expanduser() if output else Path("out") / f"{doc.meta.name}.mp4"

    source = Path(frames_dir).expanduser() if frames_dir else None
    if source is None:
        _fail("provide --frames pointing at the rendered PNG frames")
    if not source.is_dir():
        _fail(f"frames directory not found: {source}")

    frames = sorted(source.glob("*.png"))
    if not frames:
        _fail(f"no PNG frames found in {source}")

    compositor = Compositor()
    path = compositor.frames_to_video(
        frames, target, fps=doc.meta.fps, preset=preset
    )
    _echo_json({"output": str(path), "frames": len(frames), "preset": preset})


@project_app.command("translate")
def project_translate(
    translator: str = typer.Option(..., "--translator", help="fcpxml | edl | capcut_draft | ae_manifest"),
    project: str = typer.Argument(...),
    output: str = typer.Option(..., "--out"),
    direction: str = typer.Option("to_host", "--direction", help="to_host | to_universal"),
) -> None:
    """Translate a project to or from a host format."""

    from ..core.timeline_schema.io import load_document
    from ..core.timeline_schema.translate import get_translator

    try:
        trans = get_translator(translator)
    except KeyError as exc:
        _fail(str(exc))

    out = Path(output).expanduser()
    out.parent.mkdir(parents=True, exist_ok=True)

    if direction == "to_universal":
        result = trans.to_universal(load_document(project))
        out.write_text(
            json.dumps(result.model_dump(mode="json"), indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
    else:
        result = trans.from_universal(_load_project(project))
        if isinstance(result, str):
            out.write_text(result, encoding="utf-8")
        else:
            out.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")

    _echo_json({"translator": translator, "output": str(out), "direction": direction})


# ---------------------------------------------------------------------------
# Checkpoints
# ---------------------------------------------------------------------------

@checkpoint_app.command("save")
def checkpoint_save(
    project: str = typer.Argument(...),
    label: str = typer.Option("auto", "--label"),
) -> None:
    """Snapshot a project before a destructive edit."""

    from ..core.agent_runtime.checkpoint import CheckpointStore

    cfg = get_config()
    cfg.ensure_dirs()
    store = CheckpointStore(cfg.checkpoints_dir)
    cp = store.save(_load_project(project), label=label)
    _echo_json(cp.to_dict())


@checkpoint_app.command("list")
def checkpoint_list() -> None:
    """List every stored checkpoint."""

    from ..core.agent_runtime.checkpoint import CheckpointStore

    cfg = get_config()
    store = CheckpointStore(cfg.checkpoints_dir)
    entries = store.list()
    if not entries:
        typer.echo("no checkpoints stored")
        return
    for entry in entries:
        typer.echo(f"{entry.id:<44}{entry.created_at}  {entry.label}")


@checkpoint_app.command("restore")
def checkpoint_restore(
    checkpoint_id: str = typer.Argument(...),
    project: str = typer.Option(..., "--project", help="Project file to overwrite."),
) -> None:
    """Restore a checkpoint over a project file."""

    from ..core.agent_runtime.checkpoint import CheckpointStore

    cfg = get_config()
    store = CheckpointStore(cfg.checkpoints_dir)
    target = store.restore(checkpoint_id, Path(project).expanduser())
    _echo_json({"restored": str(target), "checkpoint_id": checkpoint_id})


@checkpoint_app.command("diff")
def checkpoint_diff(
    before: str = typer.Argument(...),
    after: str = typer.Argument(...),
) -> None:
    """Diff two checkpoints."""

    from ..core.agent_runtime.checkpoint import CheckpointStore

    cfg = get_config()
    store = CheckpointStore(cfg.checkpoints_dir)
    _echo_json(store.diff(before, after))


# ---------------------------------------------------------------------------
# Bridges
# ---------------------------------------------------------------------------

@bridge_app.command("list")
def bridge_list(json_output: bool = typer.Option(False, "--json")) -> None:
    """List the host bridges and whether the host is installed."""

    from ..bridges import list_bridges

    bridges = list_bridges()
    if json_output:
        _echo_json({"bridges": bridges})
        return
    for entry in bridges:
        mark = typer.style("✓", fg=typer.colors.GREEN) if entry.get("installed") else typer.style("✗", fg=typer.colors.YELLOW)
        typer.echo(f"{mark} {entry['id']:<18}{entry['host']}")


@bridge_app.command("detect")
def bridge_detect(bridge: str = typer.Argument(...)) -> None:
    """Report what a specific bridge can do on this machine."""

    from ..bridges import get_bridge

    try:
        report = get_bridge(bridge).detect()
    except KeyError as exc:
        _fail(str(exc))
    _echo_json(report.to_dict())


@bridge_app.command("inspect")
def bridge_inspect(
    bridge: str = typer.Argument(...),
    target: str = typer.Argument(...),
) -> None:
    """Read-only structural inspection of a host project (RAE)."""

    from ..bridges import get_bridge

    try:
        result = get_bridge(bridge).inspect(target)
    except KeyError as exc:
        _fail(str(exc))
    _echo_json(result)


@bridge_app.command("script")
def bridge_script(
    bridge: str = typer.Argument(...),
    project: str = typer.Argument(...),
    output_dir: str = typer.Option("out/bridges", "--out"),
) -> None:
    """Generate a host script or project document for a project."""

    from ..bridges import get_bridge

    try:
        result = get_bridge(bridge).generate_script(
            _load_project(project), Path(output_dir).expanduser()
        )
    except KeyError as exc:
        _fail(str(exc))
    _echo_json(result.to_dict())


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def run() -> None:
    """Console-script entry point."""

    setup_logging()
    try:
        app()
    except OmniFrameError as exc:
        _echo_json(exc.to_dict())
        raise SystemExit(1) from exc


if __name__ == "__main__":  # pragma: no cover
    run()
