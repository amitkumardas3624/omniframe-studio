from __future__ import annotations

from omniframe.engines.compositor import compositor as compositor_module
from omniframe.engines.compositor import ffmpeg as ffmpeg_module
from omniframe.engines.compositor.compositor import Compositor


def test_compatible_mux_uses_video_copy(monkeypatch, tmp_path):
    calls = []
    monkeypatch.setattr(compositor_module, "run_ffmpeg", lambda args: calls.append(args) or "")
    Compositor().mux_audio(
        "video.mp4",
        "audio.wav",
        tmp_path / "out.mp4",
        video_copy=True,
    )
    assert "-c:v" in calls[0]
    assert calls[0][calls[0].index("-c:v") + 1] == "copy"


def test_auto_copy_falls_back_for_incompatible_stream(monkeypatch, tmp_path):
    monkeypatch.setattr(
        compositor_module,
        "video_copy_compatible",
        lambda path, preset: (False, "codec mismatch"),
    )
    calls = []
    monkeypatch.setattr(compositor_module, "run_ffmpeg", lambda args: calls.append(args) or "")
    Compositor().mux_audio(
        "video.mp4",
        "audio.wav",
        tmp_path / "out.mp4",
        video_copy="auto",
    )
    assert calls[0][calls[0].index("-c:v") + 1] != "copy"


def test_concat_auto_copy_uses_stream_copy(monkeypatch, tmp_path):
    info = {
        "streams": [
            {
                "codec_type": "video",
                "codec_name": "h264",
                "pix_fmt": "yuv420p",
                "width": 16,
                "height": 16,
                "r_frame_rate": "24/1",
            },
            {"codec_type": "audio", "codec_name": "aac", "sample_rate": "48000"},
        ]
    }
    monkeypatch.setattr(ffmpeg_module, "ffprobe_info", lambda path: info)
    monkeypatch.setattr(compositor_module, "ffprobe_info", lambda path: info)
    calls = []
    monkeypatch.setattr(compositor_module, "run_ffmpeg", lambda args: calls.append(args) or "")
    Compositor().concat_videos(
        ["a.mp4", "b.mp4"],
        tmp_path / "out.mp4",
        reencode="auto",
    )
    assert "-c" in calls[0]
    assert calls[0][calls[0].index("-c") + 1] == "copy"


def test_explicit_concat_reencode_true_keeps_encoder(monkeypatch, tmp_path):
    calls = []
    monkeypatch.setattr(compositor_module, "run_ffmpeg", lambda args: calls.append(args) or "")
    Compositor().concat_videos(["a.mp4"], tmp_path / "out.mp4", reencode=True)
    assert calls[0][calls[0].index("-c:v") + 1] == "libx264"
