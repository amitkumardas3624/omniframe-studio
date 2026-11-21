"""The master media compositor and export pipeline.

Assembles frame sequences, mixes audio (with ducking and normalisation),
burns subtitles, applies LUTs and produces the final delivery files.

    >>> from omniframe.engines.compositor import Compositor
    >>> Compositor().frames_to_video(["f0.png", "f1.png"], "out/demo.mp4", fps=6)
"""

from __future__ import annotations

from .artifact import write_artifact_manifest
from .audio import AudioTrack, SubtitleTrack, mix_audio
from .compositor import Compositor
from .ffmpeg import (
    build_video_from_frames,
    escape_filter_path,
    ffmpeg_available,
    ffprobe_info,
    run_ffmpeg,
    write_concat_list,
)
from .presets import ExportPreset, get_preset, list_presets

__all__ = [
    "AudioTrack",
    "Compositor",
    "ExportPreset",
    "SubtitleTrack",
    "build_video_from_frames",
    "escape_filter_path",
    "ffmpeg_available",
    "ffprobe_info",
    "get_preset",
    "list_presets",
    "mix_audio",
    "run_ffmpeg",
    "write_artifact_manifest",
    "write_concat_list",
]
