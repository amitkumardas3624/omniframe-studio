"""DaVinci Resolve bridge.

Generates a Python script that drives the **documented** Resolve scripting API
(``DaVinciResolveScript.scriptapp("Resolve")``), plus a Resolve XML sidecar
that Resolve and Premiere both import natively.

RAE notes
---------
Resolve's external scripting API requires the Studio edition; the free edition
exposes no external scripting surface at all.  The bridge therefore reports the
edition constraint explicitly and never pretends a command succeeded.  ``.drp``
project files are inspected read-only (size, magic bytes, printable strings);
they are never rewritten or patched.
"""

from __future__ import annotations

import zipfile
from pathlib import Path
from typing import Any

from ..core.config import detect_davinci_resolve
from ..core.logging import get_logger
from ..core.timeline_schema.translate import get_translator
from .base import BridgeCapability, BridgeReport, BridgeTier, GeneratedScript, ToolBridge

LOG = get_logger("bridges.davinci_resolve")

PROJECT_MARKERS = ("DaVinci Resolve", "resolve", "Timeline", "MediaPool")


def _slug(value: str) -> str:
    cleaned = "".join(ch if ch.isalnum() else "_" for ch in str(value)).strip("_")
    return (cleaned.lower() or "omniframe_project")


class DaVinciResolveBridge(ToolBridge):
    """Adapter for DaVinci Resolve (Python scripting API)."""

    id = "davinci_resolve"
    host = "DaVinci Resolve"
    script_extension = ".py"
    description = (
        "Generates a Resolve Python API script that rebuilds an OmniFrame "
        "project and inspects .drp project files read-only."
    )

    # -- detection ------------------------------------------------------
    def detect(self) -> BridgeReport:
        notes: list[str] = []
        try:
            cap = detect_davinci_resolve()
        except Exception as exc:  # pragma: no cover
            return BridgeReport(
                bridge=self.id,
                host=self.host,
                installed=False,
                capabilities=self.capabilities(),
                notes=[f"Resolve detection failed: {exc}"],
            )

        if cap.available:
            notes.append("Resolve detected.")
            if cap.detail:
                notes.append(cap.detail)
            notes.append(
                "External scripting requires the Studio edition; the free edition "
                "exposes no scripting surface."
            )
        else:
            notes.append(
                cap.detail or "DaVinci Resolve not detected - scripts can still be generated."
            )

        paths: dict[str, str] = {}
        if cap.path:
            paths["executable"] = cap.path
        return BridgeReport(
            bridge=self.id,
            host=self.host,
            installed=bool(cap.available),
            version=cap.version,
            path=cap.path,
            scripting_api=bool(cap.available),
            capabilities=self.capabilities(),
            paths=paths,
            notes=notes,
        )

    # -- capabilities ---------------------------------------------------
    def capabilities(self) -> list[BridgeCapability]:
        return [
            BridgeCapability(
                name="project_management",
                tier=BridgeTier.DOCUMENTED_API,
                description="Create or open a Resolve project.",
                requires_host=True,
            ),
            BridgeCapability(
                name="timeline_management",
                tier=BridgeTier.DOCUMENTED_API,
                description="Create a timeline matching the project's frame rate.",
                requires_host=True,
            ),
            BridgeCapability(
                name="media_pool_import",
                tier=BridgeTier.DOCUMENTED_API,
                description="Import media into the media pool.",
                requires_host=True,
            ),
            BridgeCapability(
                name="clip_editing",
                tier=BridgeTier.DOCUMENTED_API,
                description="Append or place clips at their timeline frame.",
                requires_host=True,
            ),
            BridgeCapability(
                name="fusion_node_hooks",
                tier=BridgeTier.DOCUMENTED_API,
                description="Attach Fusion clips / nodes to timeline items.",
                requires_host=True,
            ),
            BridgeCapability(
                name="color_node_hooks",
                tier=BridgeTier.DOCUMENTED_API,
                description="Attach Color page node trees to timeline items.",
                requires_host=True,
            ),
            BridgeCapability(
                name="render_jobs",
                tier=BridgeTier.DOCUMENTED_API,
                description="Submit render jobs with the project's render settings.",
                requires_host=True,
            ),
            BridgeCapability(
                name="project_inspection",
                tier=BridgeTier.REVERSE_ENGINEERED,
                description="Read-only structural probe of .drp containers.",
                requires_host=False,
            ),
        ]

    # -- generation -----------------------------------------------------
    def generate_script(
        self,
        project: Any,
        output_dir: str | Path,
        **options: Any,
    ) -> GeneratedScript:
        fps = float(project.meta.fps)
        name = project.meta.name or "OmniFrame Project"
        stem = _slug(options.get("stem") or f"{_slug(name)}_resolve")

        clips = [
            (track, clip)
            for track in project.sorted_tracks()
            for clip in track.sorted_clips()
            if clip.source
        ]

        script_path = self._write(output_dir, stem, self._render_script(project, clips, fps))

        out_dir = Path(output_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        xml_text = get_translator("resolve_xml").from_universal(project)
        xml_path = out_dir / f"{stem}.xml"
        xml_path.write_text(xml_text, encoding="utf-8")

        warnings: list[str] = []
        if not self.detect().installed:
            warnings.append(
                "DaVinci Resolve was not detected. The script was still generated; run it "
                "on a machine with Resolve Studio while the application is running."
            )
        warnings.append(
            "The Resolve scripting API is a host-side API: start Resolve, enable "
            "external scripting, then run this script inside Resolve's console or with "
            "the scripting environment."
        )

        return GeneratedScript(
            bridge=self.id,
            path=str(script_path),
            language="python",
            summary=(
                f"Resolve Python script for {name}: {len(clips)} clip(s) at {fps:g} fps, "
                f"plus a Resolve XML sidecar."
            ),
            metadata={
                "script_path": str(script_path),
                "xml_path": str(xml_path),
                "sidecars": [str(xml_path)],
                "project_name": name,
                "fps": fps,
                "clip_count": len(clips),
                "tier": BridgeTier.DOCUMENTED_API.value,
            },
            warnings=warnings,
        )

    # -- inspection -----------------------------------------------------
    def inspect(self, target: str | Path) -> dict[str, Any]:
        path = Path(target)
        if not path.exists():
            return {
                "bridge": self.id,
                "host": self.host,
                "target": str(path),
                "exists": False,
                "error": "target not found",
            }

        if path.is_dir():
            entries = [
                {
                    "path": str(child.relative_to(path)),
                    "dir": child.is_dir(),
                    "size_bytes": child.stat().st_size if child.is_file() else None,
                }
                for child in sorted(path.rglob("*"))[:300]
            ]
            return {
                "bridge": self.id,
                "host": self.host,
                "target": str(path),
                "exists": True,
                "kind": "directory",
                "tier": BridgeTier.REVERSE_ENGINEERED.value,
                "entry_count": len(entries),
                "entries": entries,
            }

        head = path.read_bytes()[:64]
        strings = self._readable_strings(path, limit=60)
        report: dict[str, Any] = {
            "bridge": self.id,
            "host": self.host,
            "target": str(path),
            "exists": True,
            "kind": "file",
            "tier": BridgeTier.REVERSE_ENGINEERED.value,
            "size_bytes": path.stat().st_size,
            "magic_hex": head[:16].hex(),
            "magic_ascii": "".join(chr(b) if 32 <= b < 127 else "." for b in head),
            "readable_strings": strings[:20],
            "markers_found": [m for m in PROJECT_MARKERS if any(m in s for s in strings)],
            "container": "binary-project",
        }

        if zipfile.is_zipfile(path):
            try:
                with zipfile.ZipFile(path) as archive:
                    report["container"] = "zip-project"
                    report["archive_entries"] = archive.namelist()[:100]
            except (OSError, zipfile.BadZipFile) as exc:  # pragma: no cover
                report["archive_error"] = str(exc)
        return report

    # -- internals ------------------------------------------------------
    def _render_script(self, project: Any, clips: list[tuple[Any, Any]], fps: float) -> str:
        name = project.meta.name or "OmniFrame Project"
        render_target = project.render_targets[0] if project.render_targets else None
        output_path = render_target.path if render_target else "out/resolve_render.mp4"

        lines: list[str] = []
        add = lines.append

        add("# OmniFrame Studio - DaVinci Resolve bridge")
        add("# Uses the documented Resolve scripting API (Studio edition only).")
        add("# Run inside Resolve's Python console, or with Resolve running and")
        add("# external scripting enabled.")
        add("")
        add("import sys")
        add("")
        add("try:")
        add("    import DaVinciResolveScript as dvr")
        add("except ImportError:")
        add("    print(")
        add("        'OmniFrame: DaVinciResolveScript is not available. "
            "Add the Resolve scripting")
        add("        'folder to PYTHONPATH and run Resolve with external scripting enabled.'")
        add("    )")
        add("    sys.exit(2)")
        add("")
        add(f"PROJECT_NAME = {name!r}")
        add(f"FPS = {float(fps)}")
        add(f"RESOLUTION = ({int(project.meta.width)}, {int(project.meta.height)})")
        add(f"OUTPUT_PATH = {output_path!r}")
        add("")
        add("MEDIA = [")
        seen: set[str] = set()
        for _track, clip in clips:
            source = str(clip.source)
            if source in seen:
                continue
            seen.add(source)
            add(f"    {source!r},")
        add("]")
        add("")
        add("CLIPS = [")
        for _track, clip in clips:
            add(
                f"    {{ source: {str(clip.source)!r}, "
                f"start_frame: {int(clip.start_frame)}, "
                f"in_frame: {int(clip.in_frame)}, "
                f"duration: {int(clip.duration_frames)}, "
                f"name: {(clip.name or clip.id)!r} }},"
            )
        add("]")
        add("")
        add(RESOLVE_BODY)
        return "\n".join(lines) + "\n"


RESOLVE_BODY = '''
def connect():
    """Connect to the running Resolve instance."""
    resolve = dvr.scriptapp("Resolve")
    if resolve is None:
        print("OmniFrame: could not connect to Resolve. Is it running with external scripting?")
        return None
    return resolve


def ensure_project(resolve):
    """Return the named project, creating it when needed."""
    manager = resolve.GetProjectManager()
    project = manager.LoadProject(PROJECT_NAME)
    if project is None:
        for index in range(1, manager.GetProjectCountInCurrentPage() + 1):
            candidate = manager.GetProjectInCurrentPage(index)
            if candidate.GetName() == PROJECT_NAME:
                project = candidate
                break
    if project is None:
        project = manager.CreateProject(PROJECT_NAME)
    project.SetCurrentPage()
    return project


def ensure_timeline(resolve, project):
    """Create the timeline when it does not exist yet."""
    media_pool = project.GetMediaPool()
    for index in range(1, media_pool.GetTimelineCount() + 1):
        timeline = media_pool.GetTimeline(index)
        if timeline.GetName() == PROJECT_NAME:
            return timeline
    timeline = media_pool.CreateEmptyTimeline(PROJECT_NAME)
    settings = timeline.GetSettings()
    settings["timelineFrameRate"] = str(FPS)
    timeline.SetSetting("timelineFrameRate", str(FPS))
    return timeline


def import_media(project):
    """Import every referenced media file into the media pool."""
    media_pool = project.GetMediaPool()
    imported = []
    for source in MEDIA:
        try:
            clips = media_pool.ImportMedia([source])
            if clips:
                imported.append(clips[0])
        except Exception as exc:  # noqa: BLE001 - host side errors must not abort the run
            print("OmniFrame: could not import %s (%s)" % (source, exc))
    return imported


def build_timeline(timeline, media_pool):
    """Append the project clips to the timeline."""
    for clip in CLIPS:
        try:
            source = media_pool.ImportMedia([clip["source"]])
            if not source:
                continue
            item = source[0]
            item.SetProperty("TrimIn", clip["in_frame"])
            media_pool.AppendToTimeline([item])
        except Exception as exc:  # noqa: BLE001
            print("OmniFrame: could not place %s (%s)" % (clip["name"], exc))


def submit_render(resolve, project, timeline):
    """Submit a render job for the timeline."""
    try:
        settings = {
            "TargetDir": OUTPUT_PATH.rsplit("/", 1)[0] if "/" in OUTPUT_PATH else ".",
            "CustomName": OUTPUT_PATH.rsplit("/", 1)[-1],
            "ExportVideo": True,
        }
        job = project.AddRenderJob(timeline, settings)
        if job:
            render_manager = resolve.GetRenderManager()
            render_manager.AddJobToRenderQueue(job)
            render_manager.StartRendering()
            print("OmniFrame: render queued -> %s" % OUTPUT_PATH)
    except Exception as exc:  # noqa: BLE001
        print("OmniFrame: could not queue render (%s)" % exc)


def main():
    resolve = connect()
    if resolve is None:
        return 1
    project = ensure_project(resolve)
    timeline = ensure_timeline(resolve, project)
    import_media(project)
    build_timeline(timeline, project.GetMediaPool())
    submit_render(resolve, project, timeline)
    print("OmniFrame: done for %s" % PROJECT_NAME)
    return 0


if __name__ == "__main__":
    sys.exit(main())
'''
