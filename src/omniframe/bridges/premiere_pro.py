"""Adobe Premiere Pro bridge.

Two jobs:

* **Generate** an ExtendScript (``.jsx``) that rebuilds the universal project
  inside Premiere Pro, plus an FCPXML sidecar that Premiere (and Resolve) can
  import natively.
* **Inspect** a ``.prproj`` project file read-only.

RAE notes
---------
``.prproj`` files are Adobe's proprietary compressed containers.  We never patch
them, never write to them and never bypass licensing: the bridge only *reads*
them (magic bytes, size, a printable-string scan and — when the payload turns
out to be plain XML — the sequence names).  Everything else is produced through
the documented ExtendScript DOM, which is stable across Premiere versions.

The generated script is prepared *ahead of time*: it can be produced on a
machine where Premiere Pro is not installed, and executed later by a human
inside the application.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any

from ..core.config import detect_adobe_premiere
from ..core.logging import get_logger
from ..core.timeline_schema.translate import frames_to_timecode, get_translator
from .base import BridgeCapability, BridgeReport, BridgeTier, GeneratedScript, ToolBridge

LOG = get_logger("bridges.premiere_pro")

#: Printable markers we look for when probing a ``.prproj`` container.
PROJECT_MARKERS = (
    "Adobe Premiere Pro",
    "Premiere Pro Project",
    "xmeml",
    "Sequence",
)

#: Element names that carry a sequence name inside an XML ``.prproj`` payload.
_SEQUENCE_TAGS = ("sequence", "Sequence")


def _js_string(value: Any) -> str:
    """Render ``value`` as a JavaScript string literal (ES3 safe)."""

    text = str(value)
    text = text.replace("\\", "\\\\").replace('"', '\\"')
    text = text.replace("\r", " ").replace("\n", "\\n").replace("\t", "\\t")
    return f'"{text}"'


def _js_number(value: Any) -> str:
    """Render a number as a JavaScript literal (never ``NaN``)."""

    try:
        number = float(value)
    except (TypeError, ValueError):
        return "0"
    if number != number or number in (float("inf"), float("-inf")):
        return "0"
    if float(number).is_integer():
        return str(int(number))
    return repr(number)


def _slug(value: str) -> str:
    """Filesystem-safe stem for generated artefacts."""

    cleaned = "".join(ch if ch.isalnum() else "_" for ch in str(value)).strip("_")
    return (cleaned.lower() or "omniframe_project")


class PremiereProBridge(ToolBridge):
    """Adapter for Adobe Premiere Pro (ExtendScript)."""

    id = "premiere_pro"
    host = "Adobe Premiere Pro"
    script_extension = ".jsx"
    description = (
        "Generates ExtendScript that rebuilds an OmniFrame project in Premiere Pro "
        "and inspects .prproj project files read-only."
    )

    # -- detection ------------------------------------------------------
    def detect(self) -> BridgeReport:
        """Probe the machine for Premiere Pro.  Never raises."""

        notes: list[str] = []
        try:
            cap = detect_adobe_premiere()
        except Exception as exc:  # pragma: no cover - detector must never explode
            LOG.debug("premiere detection failed", extra={"error": str(exc)})
            return BridgeReport(
                bridge=self.id,
                host=self.host,
                installed=False,
                scripting_api=False,
                capabilities=self.capabilities(),
                notes=[f"Premiere Pro detection failed: {exc}"],
            )

        if cap.available:
            notes.append("Premiere Pro detected - ExtendScript is available while the app runs.")
            notes.append("Run the generated .jsx via File > Scripts > Run Script File...")
        else:
            notes.append(
                cap.detail
                or "Premiere Pro not detected - scripts can still be generated ahead of time."
            )
            notes.append(
                "ExtendScript is a host-side API: the generated .jsx must be run inside Premiere Pro."
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
        """What this bridge can do, and how it reaches each capability."""

        return [
            BridgeCapability(
                name="sequence_creation",
                tier=BridgeTier.DOCUMENTED_API,
                description="Create a project and a sequence named after the OmniFrame project.",
                requires_host=True,
            ),
            BridgeCapability(
                name="media_import",
                tier=BridgeTier.DOCUMENTED_API,
                description="Import media into the project bin with app.project.importFiles().",
                requires_host=True,
            ),
            BridgeCapability(
                name="track_placement",
                tier=BridgeTier.DOCUMENTED_API,
                description="Create video/audio tracks and place clips at their timeline frame.",
                requires_host=True,
            ),
            BridgeCapability(
                name="cut_trim",
                tier=BridgeTier.DOCUMENTED_API,
                description="Set in/out points on placed clips (cut and trim).",
                requires_host=True,
            ),
            BridgeCapability(
                name="transitions",
                tier=BridgeTier.DOCUMENTED_API,
                description="Add transitions at the transition frames of the timeline.",
                requires_host=True,
            ),
            BridgeCapability(
                name="audio_tracks",
                tier=BridgeTier.DOCUMENTED_API,
                description="Create dedicated audio tracks and lay audio clips onto them.",
                requires_host=True,
            ),
            BridgeCapability(
                name="markers",
                tier=BridgeTier.DOCUMENTED_API,
                description="Add timeline markers for shots and per-clip markers.",
                requires_host=True,
            ),
            BridgeCapability(
                name="render_export",
                tier=BridgeTier.DOCUMENTED_API,
                description="Export the sequence using the render target preset.",
                requires_host=True,
            ),
            BridgeCapability(
                name="project_inspection",
                tier=BridgeTier.REVERSE_ENGINEERED,
                description="Read-only structural probe of a .prproj container.",
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
        """Write an ExtendScript plus an FCPXML sidecar for ``project``."""

        fps = float(project.meta.fps)
        name = project.meta.name or "OmniFrame Project"
        stem = _slug(options.get("stem") or f"{_slug(name)}_premiere_pro")

        tracks = list(project.sorted_tracks())
        clips = [(track, clip) for track in tracks for clip in track.sorted_clips()]

        media, media_index = self._media_table(clips)
        script_text = self._render_script(
            project,
            tracks=tracks,
            clips=clips,
            media=media,
            media_index=media_index,
            fps=fps,
            export_enabled=bool(options.get("export", True)),
        )

        script_path = self._write(output_dir, stem, script_text)

        # FCPXML sidecar - the interchange format Premiere imports natively.
        fcpxml_text = get_translator("fcpxml").from_universal(project)
        out_dir = Path(output_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        fcpxml_path = out_dir / f"{stem}.fcpxml"
        fcpxml_path.write_text(fcpxml_text, encoding="utf-8")

        warnings = self._warnings(project, clips)
        return GeneratedScript(
            bridge=self.id,
            path=str(script_path),
            language="javascript",
            summary=(
                f"ExtendScript for {name}: {len(clips)} clip(s) on {len(tracks)} track(s) "
                f"at {fps:g} fps, plus an FCPXML sidecar."
            ),
            metadata={
                "script_path": str(script_path),
                "fcpxml_path": str(fcpxml_path),
                "script_extension": self.script_extension,
                "project_name": name,
                "fps": fps,
                "track_count": len(tracks),
                "clip_count": len(clips),
                "media_count": len(media),
                "marker_count": len(self._markers(project, fps)),
                "export": bool(options.get("export", True)),
                "tier": BridgeTier.DOCUMENTED_API.value,
                "sidecars": [str(fcpxml_path)],
            },
            warnings=warnings,
        )

    # -- inspection -----------------------------------------------------
    def inspect(self, target: str | Path) -> dict[str, Any]:
        """Read-only probe of a ``.prproj`` file or a project folder."""

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
            entries: list[dict[str, Any]] = []
            for child in sorted(path.rglob("*")):
                if len(entries) >= 300:
                    break
                entries.append(
                    {
                        "path": str(child.relative_to(path)),
                        "dir": child.is_dir(),
                        "size_bytes": child.stat().st_size if child.is_file() else None,
                    }
                )
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
            "sequence_names": self._sequence_names(path),
            "container": "compressed-project",
        }
        report["container"] = (
            "xml-project" if report["sequence_names"] is not None else "compressed-project"
        )
        return report

    # -- internals ------------------------------------------------------
    @staticmethod
    def _media_table(
        clips: list[tuple[Any, Any]],
    ) -> tuple[list[dict[str, Any]], dict[str, int]]:
        """Map clip sources onto Premiere import items (1-based ids)."""

        media: list[dict[str, Any]] = []
        index: dict[str, int] = {}
        for _track, clip in clips:
            source = clip.source
            if not source:
                continue
            key = str(source)
            if key not in index:
                index[key] = len(media) + 1
                media.append(
                    {"id": index[key], "path": key, "name": clip.name or Path(key).name}
                )
        return media, index

    @staticmethod
    def _markers(project: Any, fps: float) -> list[dict[str, str]]:
        """Collect shot markers and per-clip markers."""

        markers: list[dict[str, str]] = []
        for shot in project.sorted_shots():
            markers.append(
                {
                    "time": frames_to_timecode(shot.start_frame, fps),
                    "name": shot.name or shot.id,
                }
            )
        for track in project.sorted_tracks():
            for clip in track.sorted_clips():
                marker = clip.metadata.get("marker")
                if marker:
                    markers.append(
                        {
                            "time": frames_to_timecode(clip.start_frame, fps),
                            "name": str(marker),
                        }
                    )
        return markers

    @staticmethod
    def _sequence_names(path: Path) -> list[str] | None:
        """Read sequence names when the payload is plain XML (older .prproj)."""

        try:
            with path.open("rb") as handle:
                head = handle.read(16)
            if not head.lstrip().startswith(b"<?xml") and not head.lstrip().startswith(b"<"):
                return None
            root = ET.parse(path).getroot()
        except (OSError, ET.ParseError):
            return None
        names: list[str] = []
        for element in root.iter():
            if element.tag in _SEQUENCE_TAGS:
                name = element.get("name")
                if name:
                    names.append(name)
        return names

    def _warnings(self, project: Any, clips: list[tuple[Any, Any]]) -> list[str]:
        warnings: list[str] = []
        report = self.detect()
        if not report.installed:
            warnings.append(
                f"{self.host} was not detected on this machine. The script was still generated; "
                f"run it inside {self.host} (File > Scripts > Run Script File...)."
            )
        missing = [clip.id for _track, clip in clips if not clip.source]
        if missing:
            warnings.append(
                f"{len(missing)} clip(s) have no media source and are skipped by the import step: "
                + ", ".join(missing[:8])
            )
        return warnings

    def _render_script(
        self,
        project: Any,
        *,
        tracks: list[Any],
        clips: list[tuple[Any, Any]],
        media: list[dict[str, Any]],
        media_index: dict[str, int],
        fps: float,
        export_enabled: bool,
    ) -> str:
        """Render the ExtendScript body (ES3 only)."""

        name = project.meta.name or "OmniFrame Project"
        render_target = project.render_targets[0] if project.render_targets else None
        export_path = render_target.path if render_target else "out/render.mp4"
        export_preset = render_target.preset if render_target else "H.264"

        lines: list[str] = []
        add = lines.append

        add("// OmniFrame Studio - Adobe Premiere Pro bridge")
        add("// Generated by omniframe.bridges.premiere_pro")
        add("// ExtendScript / ES3: var only, no arrow functions, no template literals.")
        add("// Run inside Premiere Pro: File > Scripts > Run Script File...")
        add("")
        add("(function () {")
        add(f"    var PROJECT_NAME = {_js_string(name)};")
        add(f"    var SEQUENCE_NAME = {_js_string(name)};")
        add(f"    var FPS = {_js_number(fps)};")
        add(f"    var EXPORT_ENABLED = {'true' if export_enabled else 'false'};")
        add(f"    var EXPORT_PATH = {_js_string(export_path)};")
        add(f"    var EXPORT_PRESET = {_js_string(export_preset)};")

        add("")
        add("    var IMPORT_ITEMS = [")
        for item in media:
            add(
                f"        {{ id: {item['id']}, path: {_js_string(item['path'])}, "
                f"name: {_js_string(item['name'])} }},"
            )
        add("    ];")

        add("")
        add("    var TRACKS = [")
        for track in tracks:
            kind = "audio" if str(getattr(track.kind, "value", track.kind)) == "audio" else "video"
            add(
                f"        {{ name: {_js_string(track.name or track.id)}, kind: {_js_string(kind)} }},"
            )
        add("    ];")

        add("")
        add("    var CLIPS = [")
        for track, clip in clips:
            item_id = media_index.get(str(clip.source), 0) if clip.source else 0
            add(
                "        {{ track: %d, item: %d, start: %s, in: %s, out: %s, name: %s, "
                "marker: %s }},"
                % (
                    tracks.index(track),
                    item_id,
                    _js_string(frames_to_timecode(clip.start_frame, fps)),
                    _js_string(frames_to_timecode(clip.in_frame, fps)),
                    _js_string(frames_to_timecode(clip.in_frame + clip.duration_frames, fps)),
                    _js_string(clip.name or clip.id),
                    _js_string(clip.metadata.get("marker") or ""),
                )
            )
        add("    ];")

        add("")
        add("    var MARKERS = [")
        for marker in self._markers(project, fps):
            add(
                f"        {{ time: {_js_string(marker['time'])}, "
                f"name: {_js_string(marker['name'])} }},"
            )
        add("    ];")

        add("")
        add("    var TRANSITIONS = [")
        for transition in project.transitions:
            add(
                "        {{ at: %s, kind: %s, duration: %d }},"
                % (
                    _js_string(frames_to_timecode(transition.at_frame, fps)),
                    _js_string(transition.kind),
                    int(transition.duration_frames),
                )
            )
        add("    ];")

        add("")
        add(BODY)

        add("    main();")
        add("}());")
        return "\n".join(lines) + "\n"


#: Static ExtendScript body shared by every generated Premiere script.
BODY = """
    function log(message) {
        try {
            $.writeln("OmniFrame: " + message);
        } catch (err) {
        }
    }

    function safeTime(timecode) {
        try {
            return new Time(timecode);
        } catch (err) {
            return timecode;
        }
    }

    function importMedia() {
        var imported = {};
        if (!IMPORT_ITEMS.length) {
            return imported;
        }
        var result = null;
        try {
            result = app.project.importFiles(IMPORT_ITEMS);
        } catch (err) {
            log("import failed: " + err);
            return imported;
        }
        for (var i = 0; i < result.length; i++) {
            imported[result[i].id] = result[i];
        }
        return imported;
    }

    function ensureTracks(seq) {
        var videoNeeded = 0;
        var audioNeeded = 0;
        for (var i = 0; i < TRACKS.length; i++) {
            if (TRACKS[i].kind == "audio") {
                audioNeeded++;
            } else {
                videoNeeded++;
            }
        }
        while (seq.videoTracks.numTracks < videoNeeded) {
            seq.videoTracks.add();
        }
        while (seq.audioTracks.numTracks < audioNeeded) {
            seq.audioTracks.add();
        }
    }

    function trackFor(seq, index) {
        var videoIndex = 0;
        var audioIndex = 0;
        for (var i = 0; i < index; i++) {
            if (TRACKS[i].kind == "audio") {
                audioIndex++;
            } else {
                videoIndex++;
            }
        }
        if (TRACKS[index].kind == "audio") {
            return seq.audioTracks[audioIndex];
        }
        return seq.videoTracks[videoIndex];
    }

    function insertClips(seq, imported) {
        for (var i = 0; i < CLIPS.length; i++) {
            var spec = CLIPS[i];
            if (!spec.item) {
                log("skipping clip without media: " + spec.name);
                continue;
            }
            var item = imported[spec.item];
            if (!item) {
                log("media was not imported: " + spec.name);
                continue;
            }
            try {
                var track = trackFor(seq, spec.track);
                var placed = track.overwriteClip(item, safeTime(spec.start));
                if (placed) {
                    try {
                        placed.setInPoint(safeTime(spec.in));
                    } catch (errIn) {
                    }
                    try {
                        placed.setOutPoint(safeTime(spec.out));
                    } catch (errOut) {
                    }
                }
            } catch (err) {
                log("could not place clip " + spec.name + ": " + err);
            }
        }
    }

    function addTransitions(seq) {
        for (var i = 0; i < TRANSITIONS.length; i++) {
            var spec = TRANSITIONS[i];
            try {
                seq.transitions.addTransition(spec.kind, safeTime(spec.at), spec.duration);
            } catch (err) {
                log("transition skipped (host API differs by version): " + err);
            }
        }
    }

    function addMarkers(seq) {
        for (var i = 0; i < MARKERS.length; i++) {
            try {
                var marker = seq.markers.add(safeTime(MARKERS[i].time));
                marker.name = MARKERS[i].name;
            } catch (err) {
                log("could not add marker: " + err);
            }
        }
    }

    function exportSequence(seq) {
        if (!EXPORT_ENABLED) {
            return;
        }
        try {
            var outFile = new File(EXPORT_PATH);
            seq.exportAsMediaDirect(outFile, EXPORT_PRESET, 0);
            log("export requested to " + EXPORT_PATH);
        } catch (err) {
            log("export failed: " + err);
        }
    }

    function main() {
        try {
            if (!app.project || app.project.name != PROJECT_NAME) {
                app.project = app.newProject(PROJECT_NAME);
            }
        } catch (err) {
            log("could not create the project: " + err);
            return;
        }
        var imported = importMedia();
        var seq = app.project.createNewSequence(SEQUENCE_NAME);
        try {
            seq.setSetting("VideoFrameRate", String(FPS));
        } catch (err) {
        }
        ensureTracks(seq);
        insertClips(seq, imported);
        addTransitions(seq);
        addMarkers(seq);
        exportSequence(seq);
        log("sequence built: " + SEQUENCE_NAME);
    }
"""
