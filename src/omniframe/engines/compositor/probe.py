"""FFmpeg media matrix: probe a set of media files against every export preset.

The matrix is a *best-effort diagnostic*. It never crashes on a single bad
file: each input maps to exactly one entry, and any failure (missing file,
ffprobe unavailable, unparseable stream) is reported inline as an error so the
rest of the matrix is still produced. This makes the matrix safe to run over a
directory that a user hands us without pre-validation.

Entry shape (one per input file)::

    {
        "path": "<absolute or verbatim path>",
        "container": "<ffprobe format_name, e.g. mov,mp4,m4a,... or png_pipe>",
        "video_codec": "<first video stream codec_name> or None",
        "audio_codec": "<first audio stream codec_name> or None",
        "width": "<video width> or None",
        "height": "<video height> or None",
        "duration_seconds": "<format/video duration as float> or None",
        "fps": "<video r_frame_rate parsed to float> or None",
        "compatible_with": {
            "<preset name>": {"ok": bool, "reason": "<JSON-safe reason string>"},
            ...
        },
    }

For a file that cannot be probed the scalar fields are ``None``, ``reason_stem``
per file is absent, and an ``"error"`` key carries the message so callers can
still tell the file apart from a successfully probed one. ``compatible_with`` is
always present (``{}`` on error) so consumers never hit a ``KeyError``.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from pathlib import Path
from typing import Any

from .ffmpeg import ffprobe_info, video_copy_compatible
from .presets import list_presets

__all__ = ["probe_media_matrix"]


def _parse_rational(value: Any) -> float | None:
    """Parse an ffmpeg frame-rate string such as ``"30000/1001"`` to a float.

    Returns ``None`` for empty, ``"0/0"``, ``"N/A"`` or any unparseable value so
    callers can fall back gracefully rather than raise.
    """

    if value is None:
        return None
    text = str(value).strip()
    if not text or text in {"0/0", "N/A", "-nan"}:
        return None
    if "/" in text:
        numerator, _, denominator = text.partition("/")
        try:
            num = float(numerator)
            den = float(denominator)
        except (TypeError, ValueError):
            return None
        if den == 0:
            return None
        return num / den
    try:
        return float(text)
    except (TypeError, ValueError):
        return None


def _duration_seconds(info: dict[str, Any]) -> float | None:
    """Best-effort duration from ``format``, falling back to the video stream."""

    try:
        text = str(info.get("format", {}).get("duration") or "").strip()
        if text:
            return float(text)
    except (TypeError, ValueError):
        pass
    for stream in info.get("streams") or []:
        candidate = (stream or {}).get("duration")
        if candidate not in (None, "", "N/A"):
            try:
                return float(candidate)
            except (TypeError, ValueError):
                continue
    return None


def _find_stream(info: dict[str, Any], codec_type: str) -> dict[str, Any] | None:
    for stream in info.get("streams") or []:
        if (stream or {}).get("codec_type") == codec_type:
            return stream
    return None


def _probe_one(path: str | Path) -> dict[str, Any]:
    """Build a single matrix entry for ``path`` without raising on media errors."""

    target = Path(path)
    entry: dict[str, Any] = {
        "path": str(target),
        "container": None,
        "video_codec": None,
        "audio_codec": None,
        "width": None,
        "height": None,
        "duration_seconds": None,
        "fps": None,
        "compatible_with": {},
    }

    try:
        info = ffprobe_info(target)
    except Exception as exc:  # noqa: BLE001 - matrix must never crash on a file
        entry["error"] = f"error: {exc}"
        return entry
    # Re-probe failures inside compatibility are caught per preset below.

    entry["container"] = str(info.get("format", {}).get("format_name") or None) or None
    entry["duration_seconds"] = _duration_seconds(info)

    video_stream = _find_stream(info, "video")
    if video_stream:
        entry["video_codec"] = video_stream.get("codec_name")
        try:
            entry["width"] = int(video_stream.get("width"))
        except (TypeError, ValueError):
            entry["width"] = None
        try:
            entry["height"] = int(video_stream.get("height"))
        except (TypeError, ValueError):
            entry["height"] = None
        entry["fps"] = _parse_rational(
            video_stream.get("r_frame_rate")
            or video_stream.get("avg_frame_rate")
        )

    audio_stream = _find_stream(info, "audio")
    if audio_stream:
        entry["audio_codec"] = audio_stream.get("codec_name")

    compatible: dict[str, Any] = {}
    for preset in list_presets():
        name = preset["name"]
        try:
            ok, reason = video_copy_compatible(target, name)
        except Exception as exc:  # noqa: BLE001 - never crash the matrix
            compatible[name] = {"ok": False, "reason": f"error: {exc}"}
            continue
        compatible[name] = {"ok": bool(ok), "reason": str(reason)}
    entry["compatible_with"] = compatible
    return entry


def probe_media_matrix(media_files: Sequence[str | Path] | Iterable[str | Path]) -> list[dict]:
    """Probe ``media_files`` and return a per-file matrix entry.

    Raises never propagate from this function: every input becomes exactly one
    entry. ``probe_media_matrix([])`` returns ``[]``.
    """

    return [_probe_one(path) for path in media_files]