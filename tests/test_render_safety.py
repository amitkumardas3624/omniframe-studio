"""Safety tests for cancellation, timeout and bounded temp-dir cleanup."""

from __future__ import annotations

import tempfile

import pytest

from omniframe.core.errors import RenderCanceled, RenderError
from omniframe.engines.code_video import CodeScene
from omniframe.engines.code_video.backends import StubBackend
from omniframe.engines.compositor import ffmpeg as ffmpeg_mod
from omniframe.engines.compositor.ffmpeg import (
    CancelFlag,
    build_video_from_frames,
    run_ffmpeg,
)


def make_scene(**overrides) -> CodeScene:
    defaults = dict(
        html="<html><body><div id='box'>hi</div></body></html>",
        css="#box { color: #7cf; }",
        javascript="document.getElementById('box').textContent = __OMNIFRAME_FRAME__;",
        width=32,
        height=24,
        fps=24,
        duration_frames=5,
    )
    defaults.update(overrides)
    return CodeScene(**defaults)


def make_issue_sink(issues: list):
    def sink(severity, message, line, column, source, frame):
        issues.append((severity, message, source, frame))

    return sink


class TestCancelFlag:
    def test_default_not_cancelled(self):
        flag = CancelFlag()
        assert flag.cancelled is False

    def test_cancel_sets_flag(self):
        flag = CancelFlag()
        flag.cancel()
        assert flag.cancelled is True


class TestRunFfmpegCancel:
    def test_pre_cancelled_raises_without_launching(self, monkeypatch):
        """A pre-cancelled flag must raise before ffmpeg is ever invoked."""

        def should_not_launch(*_args, **_kwargs):
            raise AssertionError("Popen must not be called for a pre-cancelled flag")

        def should_not_resolve_binary():
            raise AssertionError("ffmpeg binary must not be resolved when pre-cancelled")

        monkeypatch.setattr(ffmpeg_mod, "ffmpeg_binary", should_not_resolve_binary)
        monkeypatch.setattr(ffmpeg_mod.subprocess, "Popen", should_not_launch)

        flag = CancelFlag()
        flag.cancel()

        with pytest.raises(RenderCanceled):
            run_ffmpeg(["-i", "in.mp4", "out.mp4"], cancel=flag)
        assert issubclass(RenderCanceled, RenderError)


class TestStubBackendCancel:
    def test_pre_cancelled_returns_fewer_frames_and_not_ok(self, tmp_path):
        issues: list = []
        flag = CancelFlag()
        flag.cancel()

        frames, ok = StubBackend().render(
            make_scene(),
            tmp_path / "frames",
            resume=False,
            on_issue=make_issue_sink(issues),
            cancel=flag,
        )

        assert ok is False
        assert len(frames) < 5
        assert any(message == "render canceled by request" for _, message, _, _ in issues)


class TestTempDirCleanup:
    def test_build_video_from_frames_cleans_tmp_dir_on_failure(self, tmp_path, monkeypatch):
        """A failing run_ffmpeg must still remove the temp dir in the finally block."""

        fake_tmp = tmp_path / "omniframe-fake-tmp"

        def fake_mkdtemp(*args, **kwargs):
            fake_tmp.mkdir(parents=True, exist_ok=True)
            return str(fake_tmp)

        def failing_run_ffmpeg(*_args, **_kwargs):
            raise RenderError("boom", returncode=1)

        monkeypatch.setattr(tempfile, "mkdtemp", fake_mkdtemp)
        monkeypatch.setattr(ffmpeg_mod, "run_ffmpeg", failing_run_ffmpeg)

        output = tmp_path / "out.mp4"
        with pytest.raises(RenderError):
            build_video_from_frames(["a.png", "b.png"], output)

        assert not fake_tmp.exists()