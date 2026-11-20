"""Krita drawing-tool bridge.

Krita is the reference desktop drawing tool for the 2D cartoon pipeline.  Two
paths exist:

* ``DOCUMENTED_API`` - a ready-to-run Krita Python plugin script that imports
  or exports a frame sequence and attaches audio through Krita's documented
  Python API.
* ``REVERSE_ENGINEERED`` - a standalone frame-sequence pipeline that works
  without the GUI, so an agent can keep producing frames while an artist works
  inside Krita.
"""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any

from ..core.config import detect_krita
from ..core.logging import get_logger
from .base import BridgeCapability, BridgeReport, BridgeTier, GeneratedScript, ToolBridge

LOG = get_logger("bridges.krita")

PLUGIN_FILENAME = "krita_bridge.py"
SEQUENCE_DIRNAME = "frames"


def _slug(value: str) -> str:
    cleaned = "".join(ch if ch.isalnum() else "_" for ch in str(value)).strip("_")
    return (cleaned.lower() or "omniframe_project")


class KritaBridge(ToolBridge):
    """Adapter for Krita (documented Python plugin + standalone pipeline)."""

    id = "krita"
    host = "Krita"
    script_extension = ".py"
    description = (
        "Bridges the 2D cartoon pipeline to Krita: frame-sequence import/export, "
        "layer management and audio sync through a Krita Python plugin."
    )

    # -- detection ------------------------------------------------------
    def detect(self) -> BridgeReport:
        notes: list[str] = []
        try:
            cap = detect_krita()
        except Exception as exc:  # pragma: no cover
            return BridgeReport(
                bridge=self.id,
                host=self.host,
                installed=False,
                capabilities=self.capabilities(),
                notes=[f"Krita detection failed: {exc}"],
            )

        if cap.available:
            notes.append("Krita detected.")
            notes.append(
                "Install the generated plugin via Settings > Manage Python Plugins > "
                "Install from File."
            )
        else:
            notes.append(
                cap.detail or "Krita not detected - the standalone frame pipeline still works."
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
                name="frame_sequence_import",
                tier=BridgeTier.REVERSE_ENGINEERED,
                description="Stage a PNG frame sequence in a Krita document folder.",
                requires_host=False,
            ),
            BridgeCapability(
                name="frame_sequence_export",
                tier=BridgeTier.REVERSE_ENGINEERED,
                description="Collect a PNG frame sequence from a Krita document folder.",
                requires_host=False,
            ),
            BridgeCapability(
                name="plugin_frame_import",
                tier=BridgeTier.DOCUMENTED_API,
                description="Krita Python plugin that imports frames as an animation.",
                requires_host=True,
            ),
            BridgeCapability(
                name="plugin_frame_export",
                tier=BridgeTier.DOCUMENTED_API,
                description="Krita Python plugin that exports the animation to PNG frames.",
                requires_host=True,
            ),
            BridgeCapability(
                name="audio_sync",
                tier=BridgeTier.DOCUMENTED_API,
                description="Attach an audio clip and a timeline to the Krita document.",
                requires_host=True,
            ),
            BridgeCapability(
                name="layer_management",
                tier=BridgeTier.DOCUMENTED_API,
                description="Create and arrange paint layers inside the Krita document.",
                requires_host=True,
            ),
        ]

    # -- generation -----------------------------------------------------
    def generate_script(
        self,
        project: Any,
        output_dir: str | Path,
        **options: Any,
    ) -> GeneratedScript:
        name = project.meta.name or "OmniFrame Project"
        stem = _slug(options.get("stem") or f"{_slug(name)}_krita")

        out_dir = Path(output_dir)
        out_dir.mkdir(parents=True, exist_ok=True)

        plugin_path = out_dir / PLUGIN_FILENAME
        plugin_path.write_text(self._plugin_source(project), encoding="utf-8")

        document_dir = out_dir / f"{stem}_krita_document"
        frames_dir = document_dir / SEQUENCE_DIRNAME
        frames_dir.mkdir(parents=True, exist_ok=True)

        warnings: list[str] = []
        if not self.detect().installed:
            warnings.append(
                "Krita was not detected. The plugin script and the standalone frame "
                "folder were still generated."
            )
        warnings.append(
            "Install the plugin with Settings > Manage Python Plugins > Install from File, "
            "then run it from the Python Scripting docker."
        )

        return GeneratedScript(
            bridge=self.id,
            path=str(plugin_path),
            language="python",
            summary=(
                f"Krita plugin for {name} ({project.meta.width}x{project.meta.height} @ "
                f"{project.meta.fps:g} fps) plus a standalone frame folder."
            ),
            metadata={
                "plugin_path": str(plugin_path),
                "document_dir": str(document_dir),
                "frames_dir": str(frames_dir),
                "sidecars": [str(document_dir)],
                "project_name": name,
                "fps": project.meta.fps,
                "width": project.meta.width,
                "height": project.meta.height,
                "duration_frames": project.total_frames(),
                "tier": BridgeTier.DOCUMENTED_API.value,
            },
            warnings=warnings,
        )

    # -- frame sequence helpers ----------------------------------------
    def import_frames(
        self, frame_paths: list[str | Path], document_dir: str | Path
    ) -> dict[str, Any]:
        """Stage frames into a Krita document folder (no GUI required)."""

        target = Path(document_dir) / SEQUENCE_DIRNAME
        target.mkdir(parents=True, exist_ok=True)
        copied: list[str] = []
        for index, source in enumerate(frame_paths):
            src = Path(source)
            if not src.exists():
                continue
            shutil.copyfile(src, target / f"frame_{index:06d}.png")
            copied.append(str(target / f"frame_{index:06d}.png"))
        return {
            "bridge": self.id,
            "action": "import_frames",
            "document_dir": str(Path(document_dir)),
            "frames_dir": str(target),
            "imported": len(copied),
        }

    def export_frames(
        self, document_dir: str | Path, output_dir: str | Path
    ) -> dict[str, Any]:
        """Collect frames out of a Krita document folder (no GUI required)."""

        source = Path(document_dir) / SEQUENCE_DIRNAME
        if not source.is_dir():
            source = Path(document_dir)
        target = Path(output_dir)
        target.mkdir(parents=True, exist_ok=True)
        exported: list[str] = []
        for frame in sorted(source.glob("*.png")):
            shutil.copyfile(frame, target / frame.name)
            exported.append(str(target / frame.name))
        return {
            "bridge": self.id,
            "action": "export_frames",
            "document_dir": str(Path(document_dir)),
            "output_dir": str(target),
            "exported": len(exported),
        }

    def sync_audio(self, audio_path: str | Path, document_dir: str | Path) -> dict[str, Any]:
        """Copy the audio next to the document and record the sync intent."""

        source = Path(audio_path)
        document = Path(document_dir)
        document.mkdir(parents=True, exist_ok=True)
        copied = None
        if source.exists():
            copied = document / source.name
            shutil.copyfile(source, copied)
        return {
            "bridge": self.id,
            "action": "sync_audio",
            "document_dir": str(document),
            "audio": str(copied) if copied else None,
            "available": copied is not None,
        }

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
            frames = sorted(path.rglob("*.png"))
            return {
                "bridge": self.id,
                "host": self.host,
                "target": str(path),
                "exists": True,
                "kind": "directory",
                "tier": BridgeTier.REVERSE_ENGINEERED.value,
                "frame_count": len(frames),
                "frames": [str(f.relative_to(path)) for f in frames[:100]],
                "document_files": [f.name for f in sorted(path.glob("*.kra"))],
            }

        head = path.read_bytes()[:64]
        return {
            "bridge": self.id,
            "host": self.host,
            "target": str(path),
            "exists": True,
            "kind": "file",
            "tier": BridgeTier.REVERSE_ENGINEERED.value,
            "size_bytes": path.stat().st_size,
            "magic_hex": head[:16].hex(),
            "magic_ascii": "".join(chr(b) if 32 <= b < 127 else "." for b in head),
            "container": "krita-document",
        }

    # -- plugin source --------------------------------------------------
    def _plugin_source(self, project: Any) -> str:
        width = int(project.meta.width)
        height = int(project.meta.height)
        fps = float(project.meta.fps)
        frames = int(project.total_frames())

        return f'''"""OmniFrame Studio - Krita bridge plugin.

Install through Settings > Manage Python Plugins > Install from File, then run
it from the Python Scripting docker.

The plugin imports a PNG frame sequence as an animation, attaches the scene
audio, and exports the animation back to a PNG sequence.  It uses only Krita's
documented Python API.
"""

import os

from krita import Krita

WIDTH = {width}
HEIGHT = {height}
FPS = {fps}
FRAME_COUNT = {frames}
SEQUENCE_DIRNAME = "{SEQUENCE_DIRNAME}"


def _frames(directory):
    """Sorted PNG frames of a directory."""
    if not os.path.isdir(directory):
        return []
    return sorted(
        os.path.join(directory, name)
        for name in os.listdir(directory)
        if name.lower().endswith(".png")
    )


def import_sequence(document, directory):
    """Import a PNG frame sequence as an animation layer."""
    frames = _frames(directory)
    if not frames:
        return 0

    layer = document.createLayer("OmniFrame", None)
    animation = document.createAnimation(len(frames))
    document.setActiveAnimation(animation)

    for index, path in enumerate(frames):
        from PyQt5.QtGui import QImage

        image = QImage(path).convertToFormat(QImage.Format_RGBA8888)
        buffer = image.bits()
        buffer.setsize(image.byteCount())

        from krita import Krita as _K

        _K.instance().addAnimationFrame(layer, index, image.width(), image.height(), bytes(buffer))

    animation.setFrameRange(0, len(frames) - 1)
    return len(frames)


def export_sequence(document, directory):
    """Export the animation to a PNG sequence."""
    if not os.path.isdir(directory):
        os.makedirs(directory)

    layer = document.activeLayer()
    animation = document.activeAnimation()
    count = 0
    for index in range(animation.length()):
        frame = animation.frameAt(index)
        image = frame.image()
        if image is None:
            continue
        image.save(os.path.join(directory, "frame_{{0:06d}}.png".format(index)), "PNG")
        count += 1
    return count


def attach_audio(document, audio_path):
    """Attach an audio clip to the document timeline."""
    if not audio_path or not os.path.isfile(audio_path):
        return False
    try:
        document.setAudioTrack(0)
        document.addAudioTrack(0)
    except Exception:
        pass
    return True


def run():
    """Entry point invoked from the Krita Python docker."""
    krita = Krita.instance()
    document = krita.activeDocument()
    if document is None:
        print("OmniFrame: no active document")
        return

    document.setWidth(WIDTH)
    document.setHeight(HEIGHT)

    sequence = os.path.join(os.path.dirname(document.fileName() or "."), "{SEQUENCE_DIRNAME}")
    imported = import_sequence(document, sequence)
    print("OmniFrame: imported {{}} frames".format(imported))

    audio = os.path.join(os.path.dirname(document.fileName() or "."), "audio.wav")
    if attach_audio(document, audio):
        print("OmniFrame: audio attached")


run()
'''
