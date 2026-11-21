"""Tests for the render-result metadata recorded by the renderer."""

from __future__ import annotations

import pytest

from omniframe.engines.code_video import CodeScene, CodeVideoRenderer
from omniframe.engines.code_video.backends import Backend


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


class IncompleteBackend(Backend):
    """A backend that always reports it did not finish rendering."""

    name = "incomplete"

    def available(self) -> bool:
        return True

    def render(self, scene, output_dir, *, resume, on_issue, on_frame=None):
        return [], False


def test_stub_backend_metadata(tmp_path):
    result = CodeVideoRenderer(backend="stub").render(make_scene(), tmp_path / "f")

    assert result.backend == "stub"
    assert result.verification_level == "import_tested"
    assert result.backend_available is True
    assert result.completed is True
    assert result.resume_requested is False

    data = result.to_dict()
    for key in ("verification_level", "backend_available", "resume_requested", "completed"):
        assert key in data


def test_resume_sets_resume_requested(tmp_path):
    target = tmp_path / "f"
    renderer = CodeVideoRenderer(backend="stub")
    renderer.render(make_scene(), target)
    resumed = renderer.render(make_scene(), target, resume=True)

    assert resumed.resume_requested is True
    assert resumed.to_dict()["resume_requested"] is True


def test_uncompleted_render_is_generated(tmp_path):
    renderer = CodeVideoRenderer(backend="stub")
    renderer._backend = IncompleteBackend()  # noqa: SLF001 - deterministic incomplete render
    result = renderer.render(make_scene(), tmp_path / "f")

    assert result.completed is False
    assert result.ok is False
    assert result.verification_level == "generated"


@pytest.mark.render
def test_playwright_backend_metadata(tmp_path):
    renderer = CodeVideoRenderer(backend="playwright")
    if not renderer.available():
        pytest.skip("Chromium is not available")
    result = renderer.render(make_scene(duration_frames=3), tmp_path / "f")
    assert result.verification_level == "render_tested"
    assert result.backend == "playwright"
    assert result.backend_available is True