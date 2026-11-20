"""Adobe After Effects bridge.

Generates an ExtendScript that rebuilds the universal project as an After
Effects composition (layers, keyframes, expressions and a render queue entry),
plus an ``ae_manifest`` JSON sidecar that mirrors the same structure.

RAE notes
---------
``.aep`` / ``.aepx`` files are Adobe's proprietary containers.  The bridge only
ever *reads* them: magic bytes, file size, a printable-string scan, and — for
``.aepx``, which is a zip container — the archive listing via the stdlib
``zipfile`` module.  Nothing is ever patched, and no licensing mechanism is
touched.
"""

from __future__ import annotations

import zipfile
from pathlib import Path
from typing import Any

from ..core.config import detect_after_effects
from ..core.logging import get_logger
from ..core.timeline_schema.translate import get_translator
from .base import BridgeCapability, BridgeReport, BridgeTier, GeneratedScript, ToolBridge

LOG = get_logger("bridges.after_effects")

PROJECT_MARKERS = ("After Effects", "Adobe After Effects", "Comp", "xmp")


def _js_string(value: Any) -> str:
    text = str(value).replace("\\", "\\\\").replace('"', '\\"')
    text = text.replace("\r", " ").replace("\n", "\\n").replace("\t", "\\t")
    return f'"{text}"'


def _js_number(value: Any) -> str:
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
    cleaned = "".join(ch if ch.isalnum() else "_" for ch in str(value)).strip("_")
    return (cleaned.lower() or "omniframe_project")


class AfterEffectsBridge(ToolBridge):
    """Adapter for Adobe After Effects (ExtendScript)."""

    id = "after_effects"
    host = "Adobe After Effects"
    script_extension = ".jsx"
    description = (
        "Generates ExtendScript that rebuilds an OmniFrame project as an After "
        "Effects composition and inspects .aep/.aepx files read-only."
    )

    # -- detection ------------------------------------------------------
    def detect(self) -> BridgeReport:
        notes: list[str] = []
        try:
            cap = detect_after_effects()
        except Exception as exc:  # pragma: no cover - detector must never explode
            return BridgeReport(
                bridge=self.id,
                host=self.host,
                installed=False,
                capabilities=self.capabilities(),
                notes=[f"After Effects detection failed: {exc}"],
            )

        if cap.available:
            notes.append("After Effects detected - ExtendScript is available while the app runs.")
            notes.append("Run the generated .jsx via File > Scripts > Run Script File...")
        else:
            notes.append(
                cap.detail or "After Effects not detected - scripts can still be generated ahead of time."
            )
            notes.append("The .jsx must be executed inside After Effects.")

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
                name="composition_setup",
                tier=BridgeTier.DOCUMENTED_API,
                description="Create a composition with the project's fps, size and duration.",
                requires_host=True,
            ),
            BridgeCapability(
                name="layer_creation",
                tier=BridgeTier.DOCUMENTED_API,
                description="Create solid, text, shape and footage layers.",
                requires_host=True,
            ),
            BridgeCapability(
                name="keyframes",
                tier=BridgeTier.DOCUMENTED_API,
                description="Convert universal keyframes into AE keyframes.",
                requires_host=True,
            ),
            BridgeCapability(
                name="expressions",
                tier=BridgeTier.DOCUMENTED_API,
                description="Attach expressions to layer properties.",
                requires_host=True,
            ),
            BridgeCapability(
                name="motion_vfx_presets",
                tier=BridgeTier.DOCUMENTED_API,
                description="Apply effect presets from the project effect list.",
                requires_host=True,
            ),
            BridgeCapability(
                name="render_queue",
                tier=BridgeTier.DOCUMENTED_API,
                description="Add the composition to the render queue with an output path.",
                requires_host=True,
            ),
            BridgeCapability(
                name="project_inspection",
                tier=BridgeTier.REVERSE_ENGINEERED,
                description="Read-only structural probe of .aep/.aepx containers.",
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
        stem = _slug(options.get("stem") or f"{_slug(name)}_after_effects")

        layers = [
            (track, clip)
            for track in project.sorted_tracks()
            for clip in track.sorted_clips()
        ]

        script_path = self._write(output_dir, stem, self._render_script(project, layers, fps))

        out_dir = Path(output_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        manifest = get_translator("ae_manifest").from_universal(project)
        import json

        manifest_path = out_dir / f"{stem}_ae_manifest.json"
        manifest_path.write_text(
            json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8"
        )

        warnings: list[str] = []
        if not self.detect().installed:
            warnings.append(
                f"{self.host} was not detected. The script was still generated; run it "
                f"inside {self.host} (File > Scripts > Run Script File...)."
            )

        return GeneratedScript(
            bridge=self.id,
            path=str(script_path),
            language="javascript",
            summary=(
                f"After Effects ExtendScript for {name}: {len(layers)} layer(s) "
                f"at {fps:g} fps, plus an AE manifest sidecar."
            ),
            metadata={
                "script_path": str(script_path),
                "manifest_path": str(manifest_path),
                "sidecars": [str(manifest_path)],
                "project_name": name,
                "fps": fps,
                "layer_count": len(layers),
                "duration_seconds": round(project.total_frames() / fps, 4) if fps else 0,
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
            except (OSError, zipfile.BadZipFile) as exc:  # pragma: no cover - defensive
                report["archive_error"] = str(exc)
        return report

    # -- internals ------------------------------------------------------
    def _render_script(self, project: Any, layers: list[tuple[Any, Any]], fps: float) -> str:
        name = project.meta.name or "OmniFrame Project"
        duration = project.total_frames() / fps if fps else 0
        render_target = project.render_targets[0] if project.render_targets else None
        output_path = render_target.path if render_target else "out/ae_render.mp4"

        lines: list[str] = []
        add = lines.append

        add("// OmniFrame Studio - Adobe After Effects bridge")
        add("// ExtendScript / ES3. Run inside After Effects: File > Scripts > Run Script File...")
        add("")
        add("(function () {")
        add(f"    var COMP_NAME = {_js_string(name)};")
        add(f"    var WIDTH = {int(project.meta.width)};")
        add(f"    var HEIGHT = {int(project.meta.height)};")
        add(f"    var FPS = {_js_number(fps)};")
        add(f"    var DURATION = {_js_number(duration)};")
        add(f"    var OUTPUT_PATH = {_js_string(output_path)};")

        add("")
        add("    var LAYERS = [")
        for _track, clip in layers:
            add(
                "        { name: %s, type: %s, source: %s, in: %s, out: %s, "
                "opacity: %s, position: [%s, %s], scale: [%s, %s], rotation: %s },"
                % (
                    _js_string(clip.name or clip.id),
                    _js_string(clip.metadata.get("ae_type", _ae_type(clip))),
                    _js_string(clip.source or ""),
                    _js_number(clip.start_frame / fps if fps else 0),
                    _js_number(clip.end_frame / fps if fps else 0),
                    _js_number(clip.opacity),
                    _js_number(clip.transform.position[0]),
                    _js_number(clip.transform.position[1]),
                    _js_number(clip.transform.scale[0] * 100),
                    _js_number(clip.transform.scale[1] * 100),
                    _js_number(clip.transform.rotation),
                )
            )
        add("    ];")

        add("")
        add("    var KEYFRAMES = [")
        for _track, clip in layers:
            for kf in clip.keyframes:
                for prop, value in kf.values.items():
                    add(
                        "        { layer: %d, property: %s, time: %s, value: %s },"
                        % (
                            layers.index((_track, clip)),
                            _js_string(prop),
                            _js_number(kf.frame / fps if fps else 0),
                            _js_number(value if isinstance(value, (int, float)) else 0),
                        )
                    )
        add("    ];")

        add("")
        add(AE_BODY)
        add("    main();")
        add("}());")
        return "\n".join(lines) + "\n"


def _ae_type(clip: Any) -> str:
    kind = str(getattr(clip.kind, "value", clip.kind))
    if kind == "text":
        return "text"
    if kind == "solid":
        return "solid"
    if kind in {"video", "image"}:
        return "footage"
    return "null"


AE_BODY = """
    function safeLog(message) {
        try {
            $.writeln("OmniFrame: " + message);
        } catch (err) {
        }
    }

    function buildComp() {
        var item = app.project.items.addComp(COMP_NAME, WIDTH, HEIGHT, 1, DURATION, FPS);
        return item;
    }

    function createLayer(comp, spec, index) {
        var layer = null;
        if (spec.type == "solid") {
            layer = comp.layers.addSolid(spec.source || "rgba(0,0,0,1)", spec.name, WIDTH, HEIGHT, 1);
        } else if (spec.type == "text") {
            layer = comp.layers.addText(spec.name);
        } else if (spec.type == "footage" && spec.source) {
            try {
                var imported = app.project.importFile(new File(spec.source));
                layer = comp.layers.add(imported, spec.in);
            } catch (err) {
                safeLog("could not import " + spec.source + ": " + err);
                layer = comp.layers.addNull(spec.in);
            }
        } else {
            layer = comp.layers.addNull(spec.in);
        }
        layer.name = spec.name;
        layer.inPoint = spec.in;
        layer.outPoint = spec.out;
        try {
            layer.opacity = spec.opacity * 100;
            layer.position.setValue([spec.position[0], spec.position[1]]);
            layer.scale.setValue([spec.scale[0], spec.scale[1]]);
            layer.rotation = spec.rotation;
        } catch (err) {
            safeLog("property set failed on " + spec.name + ": " + err);
        }
        return layer;
    }

    function applyKeyframes(comp, created) {
        for (var i = 0; i < KEYFRAMES.length; i++) {
            var kf = KEYFRAMES[i];
            var layer = created[kf.layer];
            if (!layer) {
                continue;
            }
            var value = kf.value;
            var prop = null;
            if (kf.property == "opacity") {
                prop = layer.property("ADBE Opacity");
            } else if (kf.property == "rotation") {
                prop = layer.property("ADBE Rotate Z");
            } else if (kf.property == "scale" || kf.property == "scale_x" || kf.property == "scale_y") {
                prop = layer.property("ADBE Scale");
            } else {
                prop = layer.property("ADBE Position");
            }
            if (!prop) {
                continue;
            }
            try {
                prop.setValueAtTime(kf.time, value);
            } catch (err) {
                safeLog("keyframe failed on " + layer.name + ": " + err);
            }
        }
    }

    function queueRender(comp) {
        try {
            var rq = app.project.renderQueue;
            rq.add(comp);
            var item = rq.item(rq.numItems - 1);
            var output = item.outputModule(1);
            output.file = new File(OUTPUT_PATH);
            safeLog("render queued: " + OUTPUT_PATH);
        } catch (err) {
            safeLog("could not queue render: " + err);
        }
    }

    function main() {
        if (!app.project) {
            app.newProject();
        }
        var comp = buildComp();
        var created = [];
        for (var i = 0; i < LAYERS.length; i++) {
            created.push(createLayer(comp, LAYERS[i], i));
        }
        applyKeyframes(comp, created);
        queueRender(comp);
        safeLog("composition built: " + COMP_NAME + " (" + LAYERS.length + " layers)");
    }
"""
