"""Pure-Python implementations used when the optional native module is absent."""

from __future__ import annotations

from pathlib import Path
from typing import Any


class FramePipeSink:
    """Write raw RGBA frames as canonical PNG files.

    The sink deliberately mirrors the native sink's small public contract.  It
    is useful for opt-in streaming callers that still want deterministic PNG
    output, and it keeps the default renderer independent from the extension.
    """

    backend = "python"

    def __init__(
        self,
        output_dir: str | Path,
        *,
        fps: float,
        width: int,
        height: int,
        start_frame: int = 0,
        **_: Any,
    ) -> None:
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.fps = float(fps)
        self.width = int(width)
        self.height = int(height)
        self._frame_index = int(start_frame)
        self._closed = False
        if self.width <= 0 or self.height <= 0:
            raise ValueError("width and height must be positive")
        if self.fps <= 0:
            raise ValueError("fps must be positive")

    @property
    def frame_count(self) -> int:
        return self._frame_index

    def write_rgba(self, frame_bytes: bytes, width: int, height: int) -> None:
        """Validate and write one RGBA frame as ``frame_NNNNNN.png``."""

        if self._closed:
            raise RuntimeError("FramePipeSink is already closed")
        width = int(width)
        height = int(height)
        if width != self.width or height != self.height:
            raise ValueError(
                f"frame dimensions {width}x{height} do not match sink "
                f"{self.width}x{self.height}"
            )
        payload = bytes(frame_bytes)
        expected = width * height * 4
        if len(payload) != expected:
            raise ValueError(f"RGBA frame has {len(payload)} bytes; expected {expected}")

        from PIL import Image

        target = self.output_dir / f"frame_{self._frame_index:06d}.png"
        image = Image.frombytes("RGBA", (width, height), payload)
        image.save(target, format="PNG")
        self._frame_index += 1

    def close(self) -> None:
        """Close the sink; repeated calls are harmless."""

        self._closed = True


__all__ = ["FramePipeSink"]
