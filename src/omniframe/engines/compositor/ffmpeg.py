"""Thin, well-behaved wrappers around the ``ffmpeg`` / ``ffprobe`` binaries."""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path
from typing import Any, Iterable, Sequence

from ...core.errors import EngineUnavailable, RenderError, ValidationError
from ...core.logging import get_logger

LOG = get_logger("engines.compositor.ffmpeg")


def ffmpeg_binary() -> str:
    """The path to the ffmpeg executable."""

    path = shutil.which("ffmpeg")
    if not path:
        raise EngineUnavailable(
            "ffmpeg was not found on PATH. Install FFmpeg and re-run `omniframe doctor`.",
            binary="ffmpeg",
        )
    return path


def ffprobe_binary() -> str:
    """The path to the ffprobe executable."""

    path = shutil.which("ffprobe")
    if not path:
        raise EngineUnavailable(
            "ffprobe was not found on PATH. Install FFmpeg and re-run `omniframe doctor`.",
            binary="ffprobe",
        )
    return path


def ffmpeg_available() -> bool:
    """Whether ffmpeg can be executed."""

    return shutil.which("ffmpeg") is not None


def run_ffmpeg(args: Sequence[str], *, timeout: float = 1800.0) -> str:
    """Run ffmpeg with ``args`` and return its stderr.

    Raises :class:`RenderError` with the tail of stderr when ffmpeg fails.
    """

    binary = ffmpeg_binary()
    argv = [binary, "-hide_banner", "-nostdin", "-y", *args]
    LOG.debug("ffmpeg", extra={"argv": " ".join(argv)})
    try:
        proc = subprocess.run(  # noqa: S603
            argv, capture_output=True, text=True, timeout=timeout, check=False
        )
    except subprocess.TimeoutExpired as exc:
        raise RenderError(
            f"ffmpeg timed out after {timeout:g}s.", argv=argv
        ) from exc
    except OSError as exc:
        raise EngineUnavailable(f"ffmpeg could not be executed: {exc}", argv=argv) from exc

    if proc.returncode != 0:
        tail = (proc.stderr or "").strip()[-1500:]
        raise RenderError(
            f"ffmpeg exited with code {proc.returncode}: {tail}",
            argv=argv,
            stderr=tail,
            returncode=proc.returncode,
        )
    return proc.stderr or ""


def ffprobe_info(path: str | Path) -> dict[str, Any]:
    """Return the ffprobe JSON description of a media file."""

    target = Path(path)
    if not target.exists():
        raise ValidationError(f"Media file not found: {target}", path=str(target))

    argv = [
        ffprobe_binary(),
        "-v", "quiet",
        "-print_format", "json",
        "-show_format",
        "-show_streams",
        str(target),
    ]
    try:
        proc = subprocess.run(  # noqa: S603
            argv, capture_output=True, text=True, timeout=60, check=False
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise RenderError(f"ffprobe could not be executed: {exc}", argv=argv) from exc

    if proc.returncode != 0:
        raise RenderError(
            f"ffprobe failed: {(proc.stderr or '').strip()[-600:]}",
            argv=argv,
            path=str(target),
        )
    try:
        return json.loads(proc.stdout or "{}")
    except json.JSONDecodeError as exc:
        raise RenderError(f"ffprobe returned invalid JSON: {exc}", path=str(target)) from exc


def escape_filter_path(path: str | Path) -> str:
    """Escape a path so it can be used inside an ffmpeg filter argument."""

    text = str(path).replace("\\", "/")
    text = text.replace(":", r"\:").replace("'", r"\'")
    return text


def write_concat_list(frames: Sequence[str | Path], list_path: str | Path, fps: float) -> Path:
    """Write an ffmpeg concat-demuxer list for a frame sequence.

    The concat demuxer is used instead of an image pattern so that frames with
    arbitrary names and gaps still assemble correctly.
    """

    if not frames:
        raise ValidationError("Cannot build a concat list from an empty frame list.")

    duration = 1.0 / float(fps) if fps else 0.04
    target = Path(list_path)
    target.parent.mkdir(parents=True, exist_ok=True)

    lines: list[str] = []
    for frame in frames:
        absolute = Path(frame).resolve()
        escaped = str(absolute).replace("\\", "/").replace("'", r"\'")
        lines.append(f"file '{escaped}'")
        lines.append(f"duration {duration:.9f}")
    # The concat demuxer needs the last file repeated to emit its duration.
    last = Path(frames[-1]).resolve()
    escaped_last = str(last).replace("\\", "/").replace("'", r"\'")
    lines.append(f"file '{escaped_last}'")

    target.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return target


def build_video_from_frames(
    frames: Sequence[str | Path],
    output: str | Path,
    *,
    fps: float = 30.0,
    video_codec: str = "libx264",
    audio_codec: str | None = None,
    extra_args: Sequence[str] = (),
    crf: int | None = None,
    bitrate: str | None = None,
    background: str | None = None,
    transparent: bool = False,
    list_path: str | Path | None = None,
) -> Path:
    """Assemble PNG frames into a video file."""

    import tempfile

    target = Path(output)
    target.parent.mkdir(parents=True, exist_ok=True)

    tmp_dir = Path(tempfile.mkdtemp(prefix="omniframe-compose-"))
    list_file = Path(list_path) if list_path else tmp_dir / "frames.txt"
    write_concat_list(frames, list_file, fps)

    args: list[str] = ["-f", "concat", "-safe", "0", "-i", str(list_file)]

    if background:
        args += ["-f", "lavfi", "-i", f"color=c={background}:s={_guess_size(frames)}:r={fps}"]
        args += ["-shortest"]

    args += ["-c:v", video_codec]
    if audio_codec and audio_codec != "none":
        args += ["-c:a", audio_codec]
    if crf is not None:
        args += ["-crf", str(crf)]
    if bitrate:
        args += ["-b:v", str(bitrate)]
    if transparent:
        args += ["-pix_fmt", "argb"]
    args += ["-r", str(fps)]
    args += list(extra_args)
    args += [str(target)]

    try:
        run_ffmpeg(args)
    finally:
        if list_path is None:
            shutil.rmtree(tmp_dir, ignore_errors=True)
    return target


def _guess_size(frames: Sequence[str | Path]) -> str:
    """Best-effort frame size for a solid background."""

    if not frames:
        return "1920x1080"
    try:
        from PIL import Image

        with Image.open(frames[0]) as image:
            return f"{image.width}x{image.height}"
    except Exception:  # pragma: no cover - defensive
        return "1920x1080"


def __getattr__(name: str):
    """Lazily expose raw streaming without creating an import cycle."""

    if name in {"RawVideoStream", "stream_rgba_frames"}:
        from .raw_stream import RawVideoStream, stream_rgba_frames

        return {"RawVideoStream": RawVideoStream, "stream_rgba_frames": stream_rgba_frames}[name]
    raise AttributeError(name)


__all__ = [
    "RawVideoStream",
    "build_video_from_frames",
    "escape_filter_path",
    "ffmpeg_available",
    "ffmpeg_binary",
    "ffprobe_binary",
    "ffprobe_info",
    "run_ffmpeg",
    "stream_rgba_frames",
    "write_concat_list",
]
