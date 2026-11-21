"""Thin, well-behaved wrappers around the ``ffmpeg`` / ``ffprobe`` binaries."""

from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
import threading
import time
from pathlib import Path
from typing import Any, Iterable, Sequence

from ...core.errors import EngineUnavailable, RenderCanceled, RenderError, ValidationError
from ...core.logging import get_logger

LOG = get_logger("engines.compositor.ffmpeg")


class CancelFlag:
    """A thread-safe signal used to request early cancellation of a render.

    Wraps a :class:`threading.Event` so it can be handed to :func:`run_ffmpeg`
    and to render backends running in a different thread, letting an external
    agent stop a long render without tearing down the process.
    """

    def __init__(self) -> None:
        self._event = threading.Event()

    def cancel(self) -> None:
        self._event.set()

    @property
    def cancelled(self) -> bool:
        return self._event.is_set()


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


def run_ffmpeg(
    args: Sequence[str], *, timeout: float = 1800.0, cancel: CancelFlag | None = None
) -> str:
    """Run ffmpeg with ``args`` and return its stderr.

    Unless ``cancel`` is already set, launches ffmpeg with :class:`subprocess.Popen`
    and polls a short-interval loop until it exits, the ``timeout`` elapses, or
    ``cancel.cancelled`` becomes ``True``.  stderr is redirected to a temporary
    file so the child never blocks on a full pipe while we poll.

    Raises :class:`RenderError` (with the tail of stderr) when ffmpeg fails or
    times out, and :class:`RenderCanceled` when cancellation is signalled before
    launch or during the run.
    """

    if cancel is not None and cancel.cancelled:
        raise RenderCanceled(
            "ffmpeg canceled before launch.", argv=list(args)
        )

    binary = ffmpeg_binary()
    argv = [binary, "-hide_banner", "-nostdin", "-y", *args]
    LOG.debug("ffmpeg", extra={"argv": " ".join(argv)})

    deadline = time.monotonic() + timeout
    tmp_stream = tempfile.TemporaryFile(mode="w+t", encoding="utf-8")
    proc: subprocess.Popen[str] | None = None
    try:
        proc = subprocess.Popen(  # noqa: S603
            argv,
            stdout=subprocess.DEVNULL,
            stderr=tmp_stream,
            text=True,
        )
    except OSError as exc:
        tmp_stream.close()
        raise EngineUnavailable(f"ffmpeg could not be executed: {exc}", argv=argv) from exc

    assert proc is not None
    stderr: str
    try:
        while proc.poll() is None:
            if cancel is not None and cancel.cancelled:
                _terminate(proc, argv, timeout, canceled=True)
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                _terminate(proc, argv, timeout, canceled=False)
            time.sleep(min(0.25, max(remaining, 0.0)))
    except (RenderError, RenderCanceled):
        raise
    except OSError as exc:
        raise EngineUnavailable(f"ffmpeg could not be executed: {exc}", argv=argv) from exc
    finally:
        proc.wait()
        tmp_stream.flush()
        tmp_stream.seek(0)
        stderr = tmp_stream.read()
        tmp_stream.close()

    if proc.returncode != 0:
        tail = (stderr or "").strip()[-1500:]
        raise RenderError(
            f"ffmpeg exited with code {proc.returncode}: {tail}",
            argv=argv,
            stderr=tail,
            returncode=proc.returncode,
        )
    return stderr or ""


def _terminate(
    proc: subprocess.Popen[str],
    argv: list[str],
    timeout: float,
    *,
    canceled: bool,
) -> None:
    """Kill ``proc`` and raise the appropriate error for a timeout/cancel."""
    try:
        proc.kill()
    except OSError:  # pragma: no cover - already gone
        pass
    try:
        proc.wait()
    except OSError:  # pragma: no cover - already gone
        pass
    if canceled:
        raise RenderCanceled("ffmpeg canceled during encoding.", argv=argv)
    raise RenderError(f"ffmpeg timed out after {timeout:g}s.", argv=argv)


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


_CODEC_ALIASES = {
    "libx264": {"h264", "avc1"},
    "libx265": {"hevc", "h265"},
    "hevc": {"hevc", "h265"},
    "prores_ks": {"prores", "prores_ks"},
    "libvpx-vp9": {"vp9", "libvpx-vp9"},
}


def _requested_pixel_format(preset: Any) -> str | None:
    args = list(getattr(preset, "extra_args", ()))
    for index, value in enumerate(args[:-1]):
        if value == "-pix_fmt":
            return str(args[index + 1])
    return None


def _container_from_path(path: str | Path) -> str:
    suffix = Path(path).suffix.lower().lstrip(".")
    return {"mp4": "mp4", "mov": "mov", "webm": "webm", "gif": "gif"}.get(suffix, suffix)


def video_copy_compatible(video: str | Path, preset: Any = "h264") -> tuple[bool, str]:
    """Explain whether a video can be copied into a preset without re-encoding."""

    from .presets import get_preset

    chosen = get_preset(preset) if isinstance(preset, str) else preset
    if _container_from_path(video) != chosen.container:
        return False, f"container {_container_from_path(video)!r} is not {chosen.container!r}"
    try:
        info = ffprobe_info(video)
    except Exception as exc:
        return False, f"ffprobe unavailable: {exc}"
    streams = info.get("streams") or []
    video_stream = next((s for s in streams if s.get("codec_type") == "video"), None)
    if video_stream is None:
        return False, "no video stream found"
    accepted_codecs = _CODEC_ALIASES.get(chosen.video_codec, {chosen.video_codec})
    codec = str(video_stream.get("codec_name") or "")
    if codec not in accepted_codecs:
        return False, f"video codec {codec!r} is not compatible with {chosen.video_codec!r}"
    width = int(video_stream.get("width") or 0)
    height = int(video_stream.get("height") or 0)
    if width <= 0 or height <= 0:
        return False, "video dimensions are missing"
    pixel_format = _requested_pixel_format(chosen)
    source_pixel_format = str(video_stream.get("pix_fmt") or "")
    if pixel_format and source_pixel_format and pixel_format != source_pixel_format:
        return False, f"pixel format {source_pixel_format!r} is not {pixel_format!r}"
    rate = str(video_stream.get("r_frame_rate") or "")
    if rate in {"", "0/0", "N/A"}:
        return False, "frame rate metadata is missing"
    return True, "codec, pixel format, dimensions, frame rate, and container are compatible"


def concat_copy_compatible(videos: Sequence[str | Path], preset: Any = "h264") -> tuple[bool, str]:
    """Return whether every segment has matching stream metadata for ``-c copy``."""

    if not videos:
        return False, "no videos supplied"
    first_ok, first_reason = video_copy_compatible(videos[0], preset)
    if not first_ok:
        return False, f"first segment is incompatible: {first_reason}"
    signatures: list[tuple[Any, ...]] = []
    for video in videos:
        try:
            info = ffprobe_info(video)
        except Exception as exc:
            return False, f"ffprobe unavailable: {exc}"
        streams = info.get("streams") or []
        video_stream = next((s for s in streams if s.get("codec_type") == "video"), None)
        audio_stream = next((s for s in streams if s.get("codec_type") == "audio"), None)
        if video_stream is None:
            return False, f"segment {video} has no video stream"
        signatures.append(
            (
                video_stream.get("codec_name"),
                video_stream.get("pix_fmt"),
                video_stream.get("width"),
                video_stream.get("height"),
                video_stream.get("r_frame_rate"),
                audio_stream.get("codec_name") if audio_stream else None,
                audio_stream.get("sample_rate") if audio_stream else None,
            )
        )
    if any(signature != signatures[0] for signature in signatures[1:]):
        return False, "segment stream metadata differs"
    return True, "all segment audio/video stream metadata matches"


def __getattr__(name: str):
    """Lazily expose raw streaming without creating an import cycle."""

    if name in {"RawVideoStream", "stream_rgba_frames"}:
        from .raw_stream import RawVideoStream, stream_rgba_frames

        return {"RawVideoStream": RawVideoStream, "stream_rgba_frames": stream_rgba_frames}[name]
    raise AttributeError(name)


__all__ = [
    "CancelFlag",
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
