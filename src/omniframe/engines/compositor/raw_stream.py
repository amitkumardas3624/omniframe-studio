"""Backpressure-aware raw RGBA streaming into FFmpeg."""

from __future__ import annotations

import subprocess
from collections.abc import Iterable, Sequence
from pathlib import Path

from ...core.errors import RenderError, ValidationError
from .ffmpeg import ffmpeg_binary


class RawVideoStream:
    """Write raw RGBA frames to an FFmpeg subprocess without shell execution."""

    def __init__(
        self,
        output: str | Path,
        *,
        width: int,
        height: int,
        fps: float,
        video_codec: str = "libx264",
        extra_args: Sequence[str] = (),
        timeout: float = 1800.0,
    ) -> None:
        self.output = Path(output)
        self.output.parent.mkdir(parents=True, exist_ok=True)
        self.width = int(width)
        self.height = int(height)
        self.fps = float(fps)
        self.video_codec = str(video_codec)
        self.timeout = float(timeout)
        if self.width <= 0 or self.height <= 0 or self.fps <= 0:
            raise ValidationError("raw stream width, height, and fps must be positive")
        self.expected_bytes = self.width * self.height * 4
        args = [
            ffmpeg_binary(),
            "-hide_banner",
            "-nostdin",
            "-y",
            "-f",
            "rawvideo",
            "-pix_fmt",
            "rgba",
            "-s",
            f"{self.width}x{self.height}",
            "-r",
            str(self.fps),
            "-i",
            "pipe:0",
            "-an",
            "-c:v",
            self.video_codec,
            *list(extra_args),
            str(self.output),
        ]
        self.argv = args
        try:
            self._process = subprocess.Popen(  # noqa: S603
                args,
                stdin=subprocess.PIPE,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.PIPE,
            )
        except OSError as exc:
            raise RenderError(f"ffmpeg streaming could not start: {exc}", argv=args) from exc
        self._closed = False
        self._frames = 0

    @property
    def frame_count(self) -> int:
        return self._frames

    def write(self, frame_bytes: bytes) -> None:
        if self._closed:
            raise RuntimeError("RawVideoStream is already closed")
        payload = bytes(frame_bytes)
        if len(payload) != self.expected_bytes:
            raise ValidationError(
                f"RGBA frame has {len(payload)} bytes; expected {self.expected_bytes}",
                width=self.width,
                height=self.height,
            )
        assert self._process.stdin is not None
        try:
            self._process.stdin.write(payload)
        except (BrokenPipeError, OSError) as exc:
            self.close(raise_on_error=False)
            raise RenderError("ffmpeg closed the raw frame pipe", argv=self.argv) from exc
        self._frames += 1

    def close(self, *, raise_on_error: bool = True) -> None:
        if self._closed:
            return
        self._closed = True
        if self._process.stdin is not None:
            try:
                self._process.stdin.close()
            except OSError:
                pass
        try:
            _stdout, stderr = self._process.communicate(timeout=self.timeout)
            returncode = self._process.returncode
        except subprocess.TimeoutExpired as exc:
            self._process.kill()
            _stdout, stderr = self._process.communicate(timeout=10)
            raise RenderError(
                f"ffmpeg streaming timed out after {self.timeout:g}s.",
                argv=self.argv,
            ) from exc
        if returncode != 0 and raise_on_error:
            tail = stderr.decode("utf-8", errors="replace").strip()[-1500:]
            raise RenderError(
                f"ffmpeg exited with code {returncode}: {tail}",
                argv=self.argv,
                stderr=tail,
                returncode=returncode,
            )

    def __enter__(self) -> RawVideoStream:
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close(raise_on_error=exc_type is None)


def stream_rgba_frames(
    frames: Iterable[bytes],
    output: str | Path,
    *,
    width: int,
    height: int,
    fps: float,
    video_codec: str = "libx264",
    extra_args: Sequence[str] = (),
    timeout: float = 1800.0,
) -> Path:
    """Encode an iterable of raw RGBA frames directly through FFmpeg stdin."""

    target = Path(output)
    with RawVideoStream(
        target,
        width=width,
        height=height,
        fps=fps,
        video_codec=video_codec,
        extra_args=extra_args,
        timeout=timeout,
    ) as stream:
        for frame in frames:
            stream.write(frame)
    return target


__all__ = ["RawVideoStream", "stream_rgba_frames"]
