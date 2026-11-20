"""Export presets for the compositor.

A preset is a named delivery format: container + video codec + audio codec +
the extra ffmpeg flags that make the file "correct" for that target (pixel
format, faststart, alpha, ...).  Presets are intentionally data-only so an
agent can enumerate them and reason about the trade-offs.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from ...core.errors import ValidationError


@dataclass
class ExportPreset:
    """One concrete delivery format."""

    name: str
    container: str
    video_codec: str
    audio_codec: str = "none"
    extra_args: list[str] = field(default_factory=list)
    description: str = ""
    supports_transparency: bool = False

    def to_dict(self) -> dict:
        """Return a JSON-serialisable description of the preset."""

        return {
            "name": self.name,
            "container": self.container,
            "video_codec": self.video_codec,
            "audio_codec": self.audio_codec,
            "extra_args": list(self.extra_args),
            "description": self.description,
            "supports_transparency": self.supports_transparency,
        }


#: Every preset the compositor knows about, keyed by name.
_PRESETS: dict[str, ExportPreset] = {
    "h264": ExportPreset(
        name="h264",
        container="mp4",
        video_codec="libx264",
        audio_codec="aac",
        extra_args=["-pix_fmt", "yuv420p", "-movflags", "+faststart"],
        description="Universal MP4 / H.264 delivery.",
    ),
    "h265": ExportPreset(
        name="h265",
        container="mp4",
        video_codec="hevc",
        audio_codec="aac",
        extra_args=["-pix_fmt", "yuv420p", "-tag:v", "hvc1"],
        description="MP4 / HEVC (H.265) for smaller files.",
    ),
    "prores": ExportPreset(
        name="prores",
        container="mov",
        video_codec="prores_ks",
        audio_codec="pcm_s16le",
        extra_args=["-profile:v", "3", "-pix_fmt", "yuv422p10le"],
        description="Apple ProRes 422 HQ mezzanine master.",
    ),
    "webm": ExportPreset(
        name="webm",
        container="webm",
        video_codec="libvpx-vp9",
        audio_codec="libopus",
        extra_args=["-b:v", "0", "-crf", "32"],
        description="WebM / VP9 + Opus for the open web.",
    ),
    "gif": ExportPreset(
        name="gif",
        container="gif",
        video_codec="gif",
        audio_codec="none",
        extra_args=["-loop", "0"],
        description="Animated GIF (no audio).",
    ),
    "png_sequence": ExportPreset(
        name="png_sequence",
        container="image2",
        video_codec="png",
        audio_codec="none",
        extra_args=["-fps_mode", "passthrough"],
        description="Lossless PNG frame sequence (supports alpha).",
        supports_transparency=True,
    ),
    "qtrle_alpha": ExportPreset(
        name="qtrle_alpha",
        container="mov",
        video_codec="qtrle",
        audio_codec="none",
        extra_args=["-pix_fmt", "argb"],
        description="QuickTime RLE with an alpha channel.",
        supports_transparency=True,
    ),
}


def get_preset(name: str) -> ExportPreset:
    """Return the preset called ``name``.

    Raises :class:`ValidationError` when the preset does not exist; the error
    details list every valid name so an agent can recover without guessing.
    """

    try:
        return _PRESETS[str(name).lower()]
    except KeyError as exc:
        raise ValidationError(
            f"Unknown export preset '{name}'. Available: {', '.join(sorted(_PRESETS))}",
            preset=name,
            available=sorted(_PRESETS),
        ) from exc


def list_presets() -> list[dict]:
    """Describe every available preset, sorted by name."""

    return [_PRESETS[name].to_dict() for name in sorted(_PRESETS)]
