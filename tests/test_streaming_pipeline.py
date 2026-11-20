from __future__ import annotations

import json
import shutil
import subprocess

import pytest

from omniframe.core.errors import ValidationError
from omniframe.engines.code_video import CodeScene, CodeVideoRenderer
from omniframe.engines.compositor.raw_stream import stream_rgba_frames


def _ffprobe(path):
    proc = subprocess.run(
        [
            shutil.which("ffprobe") or "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "json",
            str(path),
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    return json.loads(proc.stdout)


def test_stream_rgba_frames_produces_expected_duration(tmp_path):
    frames = [bytes([255, 0, 0, 255]) * 4 for _ in range(4)]
    output = tmp_path / "stream.mp4"
    stream_rgba_frames(frames, output, width=2, height=2, fps=2, extra_args=("-pix_fmt", "yuv420p"))
    info = _ffprobe(output)
    assert float(info["format"]["duration"]) == pytest.approx(2.0, abs=0.1)


def test_stream_rejects_invalid_frame_length(tmp_path):
    with pytest.raises(ValidationError):
        stream_rgba_frames([b"bad"], tmp_path / "stream.mp4", width=2, height=2, fps=2)


def test_renderer_streams_without_png_frames(tmp_path):
    scene = CodeScene(
        html="<html><body><div>hello</div></body></html>",
        width=32,
        height=18,
        fps=2,
        duration_frames=4,
    )
    output = tmp_path / "rendered.mp4"
    result = CodeVideoRenderer(backend="stub").render(
        scene,
        tmp_path / "frames",
        stream_to_ffmpeg=output,
    )
    assert result.ok
    assert result.stream_output == str(output)
    assert result.frames == []
    assert output.exists()
    info = _ffprobe(output)
    assert float(info["format"]["duration"]) == pytest.approx(2.0, abs=0.1)


def test_renderer_streaming_resume_fails_closed(tmp_path):
    scene = CodeScene(width=2, height=2, fps=2, duration_frames=1)
    with pytest.raises(ValidationError):
        CodeVideoRenderer(backend="stub").render(
            scene,
            tmp_path / "frames",
            resume=True,
            stream_to_ffmpeg=tmp_path / "rendered.mp4",
        )
