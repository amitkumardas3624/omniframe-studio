"""Tests for the code-video engine."""

from __future__ import annotations

import pytest

from omniframe.core.errors import SchemaError
from omniframe.engines.code_video import (
    CodeScene,
    CodeVideoRenderer,
    build_frame_payload,
    parse_stack_location,
)


def make_scene(**overrides) -> CodeScene:
    defaults = dict(
        html="<html><body><div id='box'>hi</div></body></html>",
        css="#box { color: #7cf; }",
        javascript="document.getElementById('box').textContent = __OMNIFRAME_FRAME__;",
        width=320,
        height=180,
        fps=24,
        duration_frames=5,
    )
    defaults.update(overrides)
    return CodeScene(**defaults)


class TestScene:
    def test_rejects_empty_duration(self):
        with pytest.raises(ValueError):
            CodeScene(duration_frames=0)

    def test_from_clip_requires_code_payload(self):
        class FakeClip:
            id = "c1"
            duration_frames = 10
            code = None

        class FakeMeta:
            fps = 30
            width = 100
            height = 100

        class FakeProject:
            meta = FakeMeta()

        with pytest.raises(SchemaError):
            CodeScene.from_clip(FakeClip(), FakeProject())


class TestPayload:
    def test_payload_keys(self):
        payload = build_frame_payload(make_scene(), 3)
        assert payload["frame"] == 3
        assert payload["fps"] == 24
        assert payload["total_frames"] == 5
        assert payload["seed"] == 0
        assert "params" in payload


class TestStackParsing:
    def test_extracts_line_and_column(self):
        stack = (
            "Page.evaluate: Error: boom\n"
            "    at eval (eval at evaluate (:311:30), <anonymous>:1:22)\n"
        )
        line, column = parse_stack_location(stack)
        assert line == 1
        assert column == 22

    def test_empty_stack(self):
        assert parse_stack_location(None) == (None, None)
        assert parse_stack_location("no location here") == (None, None)


class TestStubBackend:
    def test_renders_every_frame(self, tmp_path):
        renderer = CodeVideoRenderer(backend="stub")
        result = renderer.render(make_scene(), tmp_path / "frames")
        assert result.ok
        assert result.backend == "stub"
        assert len(result.frames) == 5
        assert result.frames[0].name == "frame_000000.png"
        assert result.frames[-1].name == "frame_000004.png"
        assert all(path.exists() for path in result.frames)

    def test_is_deterministic(self, tmp_path):
        renderer = CodeVideoRenderer(backend="stub")
        first = renderer.render(make_scene(), tmp_path / "a")
        second = renderer.render(make_scene(), tmp_path / "b")
        for left, right in zip(first.frames, second.frames, strict=False):
            assert left.read_bytes() == right.read_bytes()

    def test_resume_skips_existing_frames(self, tmp_path):
        renderer = CodeVideoRenderer(backend="stub")
        target = tmp_path / "frames"
        renderer.render(make_scene(), target)
        first = target / "frame_000000.png"
        stamp = first.stat().st_mtime_ns
        result = renderer.render(make_scene(), target, resume=True)
        assert len(result.frames) == 5
        assert first.stat().st_mtime_ns == stamp

    def test_stub_backend_warns(self, tmp_path):
        result = CodeVideoRenderer(backend="stub").render(make_scene(), tmp_path / "f")
        assert any(issue.source == "backend" for issue in result.issues)


@pytest.mark.render
class TestPlaywrightBackend:
    def test_renders_frames(self, tmp_path):
        renderer = CodeVideoRenderer(backend="playwright")
        if not renderer.available():
            pytest.skip("Chromium is not available")
        result = renderer.render(make_scene(duration_frames=3), tmp_path / "frames")
        assert result.ok, [str(issue) for issue in result.issues]
        assert result.backend == "playwright"
        assert len(result.frames) == 3
        assert all(path.exists() for path in result.frames)

    def test_scene_error_is_reported(self, tmp_path):
        renderer = CodeVideoRenderer(backend="playwright")
        if not renderer.available():
            pytest.skip("Chromium is not available")
        scene = make_scene(javascript="throw new Error('boom');", duration_frames=3)
        result = renderer.render(scene, tmp_path / "frames")
        assert result.ok is False
        assert result.errors
        assert "boom" in result.errors[0].message
