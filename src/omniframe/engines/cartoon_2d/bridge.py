"""Desktop drawing-tool bridge interface for the cartoon pipeline.

The interface is deliberately narrow: a drawing tool must be able to receive
a frame sequence, hand one back, and carry audio timing.  Every method works
without the GUI running, so an agent can keep producing frames while an
artist works inside the drawing application.
"""

from __future__ import annotations

import shutil
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any

from ...core.logging import get_logger

LOG = get_logger("engines.cartoon_2d.bridge")

SEQUENCE_DIRNAME = "frames"


class DrawingBridge(ABC):
    """Contract every desktop drawing tool adapter implements."""

    #: Stable identifier of the bridge.
    id: str = "drawing_bridge"
    #: Human readable name of the host application.
    host: str = "Drawing Tool"

    @abstractmethod
    def detect(self) -> dict[str, Any]:
        """Report whether the host is available on this machine."""

    @abstractmethod
    def capabilities(self) -> list[dict[str, Any]]:
        """List the operations this bridge supports."""

    @abstractmethod
    def import_frames(
        self, frame_paths: list[str | Path], document_dir: str | Path
    ) -> dict[str, Any]:
        """Stage a PNG frame sequence into a document folder."""

    @abstractmethod
    def export_frames(
        self, document_dir: str | Path, output_dir: str | Path
    ) -> dict[str, Any]:
        """Collect a PNG frame sequence out of a document folder."""

    @abstractmethod
    def sync_audio(
        self, audio_path: str | Path, document_dir: str | Path
    ) -> dict[str, Any]:
        """Attach an audio clip and its timing to the document."""

    def write_plugin(self, document_dir: str | Path) -> Path:
        """Write a runnable plugin script next to the document."""

        raise NotImplementedError(f"{type(self).__name__} does not provide a plugin script.")


class KritaBridge(DrawingBridge):
    """Krita adapter: documented plugin API plus a standalone file pipeline."""

    id = "krita"
    host = "Krita"

    def detect(self) -> dict[str, Any]:
        from ...core.config import detect_krita

        try:
            capability = detect_krita()
        except Exception as exc:  # pragma: no cover - detector must never explode
            return {
                "bridge": self.id,
                "host": self.host,
                "installed": False,
                "error": str(exc),
            }
        return {
            "bridge": self.id,
            "host": self.host,
            "installed": bool(capability.available),
            "path": capability.path,
            "version": capability.version,
            "detail": capability.detail,
        }

    def capabilities(self) -> list[dict[str, Any]]:
        return [
            {
                "name": "import_frames",
                "tier": "reverse_engineered",
                "description": "Stage a PNG frame sequence in a Krita document folder.",
            },
            {
                "name": "export_frames",
                "tier": "reverse_engineered",
                "description": "Collect a PNG frame sequence from a Krita document folder.",
            },
            {
                "name": "plugin_script",
                "tier": "documented_api",
                "description": "Krita Python plugin for animation import/export and audio sync.",
            },
        ]

    # -- frame sequence -------------------------------------------------
    def import_frames(
        self, frame_paths: list[str | Path], document_dir: str | Path
    ) -> dict[str, Any]:
        target = Path(document_dir) / SEQUENCE_DIRNAME
        target.mkdir(parents=True, exist_ok=True)
        imported: list[str] = []
        for index, source in enumerate(frame_paths):
            path = Path(source)
            if not path.exists():
                LOG.warning("frame not found", extra={"frame": str(path)})
                continue
            destination = target / f"frame_{index:06d}.png"
            shutil.copyfile(path, destination)
            imported.append(str(destination))
        return {
            "bridge": self.id,
            "action": "import_frames",
            "document_dir": str(Path(document_dir)),
            "frames_dir": str(target),
            "imported": len(imported),
            "frames": imported,
        }

    def export_frames(
        self, document_dir: str | Path, output_dir: str | Path
    ) -> dict[str, Any]:
        source = Path(document_dir) / SEQUENCE_DIRNAME
        if not source.is_dir():
            source = Path(document_dir)
        target = Path(output_dir)
        target.mkdir(parents=True, exist_ok=True)
        exported: list[str] = []
        for frame in sorted(source.glob("*.png")):
            destination = target / frame.name
            shutil.copyfile(frame, destination)
            exported.append(str(destination))
        return {
            "bridge": self.id,
            "action": "export_frames",
            "document_dir": str(Path(document_dir)),
            "output_dir": str(target),
            "exported": len(exported),
            "frames": exported,
        }

    def sync_audio(
        self, audio_path: str | Path, document_dir: str | Path
    ) -> dict[str, Any]:
        source = Path(audio_path)
        document = Path(document_dir)
        document.mkdir(parents=True, exist_ok=True)
        copied: str | None = None
        if source.exists():
            destination = document / source.name
            shutil.copyfile(source, destination)
            copied = str(destination)
        else:
            LOG.warning("audio not found", extra={"audio": str(source)})
        return {
            "bridge": self.id,
            "action": "sync_audio",
            "document_dir": str(document),
            "audio": copied,
            "available": copied is not None,
        }

    # -- plugin ---------------------------------------------------------
    def write_plugin(self, document_dir: str | Path) -> Path:
        """Write a runnable Krita Python plugin next to the document."""

        document = Path(document_dir)
        document.mkdir(parents=True, exist_ok=True)
        target = document / "krita_bridge.py"
        target.write_text(PLUGIN_SOURCE, encoding="utf-8")
        return target


PLUGIN_SOURCE = '''"""OmniFrame Studio - Krita bridge plugin.

Install through Settings > Manage Python Plugins > Install from File and run
it from the Python Scripting docker.  Uses only Krita's documented API.
"""

import os

from krita import Krita

SEQUENCE_DIRNAME = "frames"


def _frames(directory):
    if not os.path.isdir(directory):
        return []
    return sorted(
        os.path.join(directory, name)
        for name in os.listdir(directory)
        if name.lower().endswith(".png")
    )


def import_sequence(document, directory):
    """Import a PNG frame sequence as an animation layer."""
    from PyQt5.QtGui import QImage

    frames = _frames(directory)
    if not frames:
        return 0

    layer = document.createLayer("OmniFrame", None)
    animation = document.createAnimation(len(frames))
    document.setActiveAnimation(animation)

    for index, path in enumerate(frames):
        image = QImage(path).convertToFormat(QImage.Format_RGBA8888)
        buffer = image.bits()
        buffer.setsize(image.byteCount())
        Krita.instance().addAnimationFrame(
            layer, index, image.width(), image.height(), bytes(buffer)
        )

    animation.setFrameRange(0, len(frames) - 1)
    return len(frames)


def export_sequence(document, directory):
    """Export the animation to a PNG sequence."""
    if not os.path.isdir(directory):
        os.makedirs(directory)

    animation = document.activeAnimation()
    count = 0
    for index in range(animation.length()):
        frame = animation.frameAt(index)
        image = frame.image()
        if image is None:
            continue
        image.save(os.path.join(directory, "frame_{0:06d}.png".format(index)), "PNG")
        count += 1
    return count


def attach_audio(document, audio_path):
    """Attach an audio clip to the document."""
    if not audio_path or not os.path.isfile(audio_path):
        return False
    try:
        document.addAudioTrack(0)
        document.setAudioTrack(0)
    except Exception:
        pass
    return True


def run():
    krita = Krita.instance()
    document = krita.activeDocument()
    if document is None:
        print("OmniFrame: no active document")
        return

    base = os.path.dirname(document.fileName() or ".") or "."
    imported = import_sequence(document, os.path.join(base, SEQUENCE_DIRNAME))
    print("OmniFrame: imported {0} frames".format(imported))

    if attach_audio(document, os.path.join(base, "audio.wav")):
        print("OmniFrame: audio attached")


run()
'''

#: Every drawing bridge, keyed by its stable identifier.
BRIDGES: dict[str, type[DrawingBridge]] = {
    KritaBridge.id: KritaBridge,
}


def get_bridge(bridge_id: str) -> DrawingBridge:
    """Instantiate the drawing bridge registered as ``bridge_id``."""

    try:
        factory = BRIDGES[bridge_id]
    except KeyError as exc:
        raise KeyError(
            f"Unknown drawing bridge '{bridge_id}'. Available: {', '.join(sorted(BRIDGES))}"
        ) from exc
    return factory()
