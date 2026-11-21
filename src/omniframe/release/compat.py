"""Evidence-based compatibility reporting for OmniFrame export presets.

An export preset is a promise: "this delivery format works". A promise here is
only worth something when it is tied to a file that was actually produced and then
read back. That is why this module reports **evidence**, not capability:

``render_tested``
    A probe encoded a real file with the preset's codec, and ``ffprobe`` read a
    video stream back out of that file.
``import_tested``
    A file was consumed or produced outside this call and the caller recorded it
    in ``evidence``; this module never makes that claim on the caller's behalf.
``unverified``
    No produced artifact backs the claim.

A codec merely appearing in ``ffmpeg -encoders`` is *not* evidence. That listing is
reported separately under ``capability`` and never promotes ``status``. It is also
why ``qtrle`` and ``prores`` stay ``unverified``: they are presets we ship, but no
artifact was produced with them on this machine.
"""

from __future__ import annotations

import shutil
import subprocess
import tempfile
from collections.abc import Callable, Iterable, Mapping
from pathlib import Path
from typing import Any

from ..core.errors import OmniFrameError, ValidationError
from ..engines.compositor.ffmpeg import ffprobe_info, run_ffmpeg
from ..engines.compositor.presets import list_presets

__all__ = [
    "PROBED_CODECS",
    "VERIFICATION_LEVELS",
    "compatibility_report",
    "probe_preset",
]

#: Ordered verification vocabulary, loosest first.
VERIFICATION_LEVELS = ("unverified", "import_tested", "render_tested")

#: Codecs this report actively encodes and reads back on the local machine.
PROBED_CODECS = frozenset({"libx264", "libvpx-vp9", "gif"})

#: Container -> file extension used for probe artifacts.
_CONTAINER_EXTENSIONS = {"mp4": ".mp4", "mov": ".mov", "webm": ".webm", "gif": ".gif"}

_FRAME_SIZE = 16
_FRAME_COUNT = 3
_PROBE_TIMEOUT = 120.0

Probe = Callable[[Mapping[str, Any]], tuple[bool, str]]

_PROBE_CACHE: dict[str, tuple[bool, str]] = {}
_ENCODER_CACHE: dict[str, set[str] | None] = {}


def _ffmpeg_binary() -> str | None:
    """Absolute path to ffmpeg, or ``None`` when it is not installed."""
    return shutil.which("ffmpeg")


def _tool_banner(binary: str) -> str | None:
    """First line of ``<binary> -version`` (``None`` when it cannot run)."""

    try:
        completed = subprocess.run(  # noqa: S603 - fixed argv, no shell
            [binary, "-version"],
            capture_output=True,
            text=True,
            timeout=15,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if completed.returncode != 0:
        return None
    lines = (completed.stdout or "").splitlines()
    return lines[0].strip() if lines else None


def _encoder_names() -> set[str] | None:
    """Encoder names ffmpeg lists locally, or ``None`` when it is absent."""
    binary = _ffmpeg_binary()
    if binary is None:
        return None
    cached = _ENCODER_CACHE.get("names")
    if cached is not None:
        return cached
    try:
        completed = subprocess.run(  # noqa: S603 - fixed argv, no shell
            [binary, "-hide_banner", "-encoders"],
            capture_output=True,
            text=True,
            timeout=30,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    names: set[str] = set()
    for line in (completed.stdout or "").splitlines():
        parts = line.split()
        if len(parts) < 2 or len(parts[0]) == 0:
            continue
        flags = parts[0]
        if len(flags) != 6 or flags[0] not in "VAS":
            continue
        names.add(parts[1])
    _ENCODER_CACHE["names"] = names
    return names


def _capability(codec: str, encoders: set[str] | None) -> str:
    """Describe raw encoder availability without claiming a test was run."""
    if encoders is None:
        return "unknown"
    return "encoder_present" if codec in encoders else "encoder_missing"


def probe_preset(preset: Mapping[str, Any]) -> tuple[bool, str]:
    """Encode a few synthetic frames with ``preset`` and read them back.

    Returns ``(ok, detail)``. ``detail`` is the sentence recorded in the report as
    the status reason, so it names both what was produced and what ``ffprobe`` saw
    in the produced file -- the two facts that make a ``render_tested`` claim
    checkable by someone else.
    """
    codec = str(preset.get("video_codec") or "")
    if not codec:
        return False, "preset declares no video codec"
    if _ffmpeg_binary() is None:
        return False, "ffmpeg is not installed on this machine"
    extension = _CONTAINER_EXTENSIONS.get(str(preset.get("container") or ""))
    if extension is None:
        return False, f"no probe container for {preset.get('container')!r}"

    black = bytes([0, 0, 0]) * (_FRAME_SIZE * _FRAME_SIZE)
    white = bytes([255, 255, 255]) * (_FRAME_SIZE * _FRAME_SIZE)
    frames = b"".join(
        black if index % 2 == 0 else white for index in range(_FRAME_COUNT)
    )

    with tempfile.TemporaryDirectory(prefix="omniframe-compat-") as directory:
        source = Path(directory) / "frames.rgb"
        source.write_bytes(frames)
        output = Path(directory) / f"probe{extension}"
        args = [
            "-f", "rawvideo",
            "-pix_fmt", "rgb24",
            "-s", f"{_FRAME_SIZE}x{_FRAME_SIZE}",
            "-r", "12",
            "-i", str(source),
            "-c:v", codec,
            *[str(item) for item in preset.get("extra_args") or ()],
            "-frames:v", str(_FRAME_COUNT),
            str(output),
        ]
        try:
            run_ffmpeg(args, timeout=_PROBE_TIMEOUT)
        except OmniFrameError as exc:
            return False, f"{codec} encode failed: {exc}"
        if not output.is_file() or output.stat().st_size == 0:
            return False, f"{codec} encoder produced no bytes"
        size = output.stat().st_size
        try:
            info = ffprobe_info(output)
        except OmniFrameError as exc:
            return False, f"{codec} artifact could not be probed: {exc}"

    streams = [
        stream
        for stream in info.get("streams") or []
        if (stream or {}).get("codec_type") == "video"
    ]
    if not streams:
        return False, f"{codec} artifact carries no video stream"
    return True, (
        f"encoded {size} bytes and probed codec_name="
        f"{streams[0].get('codec_name')!r}"
    )


def _default_probe(preset: Mapping[str, Any]) -> tuple[bool, str]:
    """Memoized :func:`probe_preset` (one real encode per preset per process)."""
    name = str(preset["name"])
    if name not in _PROBE_CACHE:
        _PROBE_CACHE[name] = probe_preset(preset)
    return _PROBE_CACHE[name]


def _selected_presets(presets: Iterable[str] | None) -> list[dict[str, Any]]:
    """Return the requested presets, or all of them, refusing unknown names."""
    available = list_presets()
    if presets is None:
        return available
    known = {preset["name"] for preset in available}
    wanted = [str(name).lower() for name in presets]
    missing = sorted({name for name in wanted if name not in known})
    if missing:
        raise ValidationError(
            f"unknown export preset(s) {missing}; available: {sorted(known)}",
            presets=missing,
            available=sorted(known),
        )
    keep = set(wanted)
    return [preset for preset in available if preset["name"] in keep]


def compatibility_report(
    env: Mapping[str, Any],
    presets: Iterable[str] | None = None,
    *,
    probe: Probe | None = None,
    evidence: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    """Map every export preset to a verification status for this machine.

    ``env`` is recorded verbatim under ``"env"`` so a reader can tell *which*
    machine the report describes; it is not validated, interpreted or guessed.
    ``presets`` narrows the report to named presets. ``probe`` replaces the real
    encoder for tests (``(preset) -> (ok, detail)``).  ``evidence`` records levels
    established outside this call, typically by a real export run:
    ``{"prores": "render_tested"}``.

    Statuses are ``render_tested`` (a file was produced and probed here),
    ``import_tested`` (the caller supplied evidence of an import test), or
    ``unverified``. Encoder availability alone never promotes a status; it is
    reported beside it as ``capability``.
    """
    selected = _selected_presets(presets)
    all_names = {preset["name"] for preset in list_presets()}

    recorded: dict[str, str] = {}
    for raw_name, raw_level in (evidence or {}).items():
        name = str(raw_name).lower()
        level = str(raw_level)
        if name not in all_names:
            raise ValidationError(
                f"evidence names an unknown preset {name!r}",
                preset=name,
                available=sorted(all_names),
            )
        if level not in VERIFICATION_LEVELS:
            raise ValidationError(
                f"evidence level {level!r} is not one of {list(VERIFICATION_LEVELS)}",
                preset=name,
                level=level,
                levels=list(VERIFICATION_LEVELS),
            )
        recorded[name] = level

    prober: Probe = probe if probe is not None else _default_probe
    encoders = _encoder_names()
    binary = _ffmpeg_binary()

    entries: dict[str, dict[str, Any]] = {}
    for preset in selected:
        name = preset["name"]
        codec = preset["video_codec"]
        if name in recorded:
            status = recorded[name]
            reason = "recorded by the caller in evidence"
        elif codec in PROBED_CODECS:
            ok, detail = prober(preset)
            status = "render_tested" if ok else "unverified"
            reason = detail
        else:
            status = "unverified"
            reason = f"no artifact was produced with {codec} on this machine"
        entries[name] = {
            "container": preset["container"],
            "video_codec": codec,
            "audio_codec": preset["audio_codec"],
            "supports_transparency": preset["supports_transparency"],
            "capability": _capability(codec, encoders),
            "status": status,
            "reason": reason,
        }

    summary = dict.fromkeys(VERIFICATION_LEVELS, 0)
    for entry in entries.values():
        summary[entry["status"]] += 1

    return {
        "env": dict(env),
        "ffmpeg": {
            "available": binary is not None,
            "version": _tool_banner(binary) if binary is not None else None,
        },
        "levels": list(VERIFICATION_LEVELS),
        "probed_codecs": sorted(PROBED_CODECS),
        "presets": entries,
        "summary": summary,
    }



