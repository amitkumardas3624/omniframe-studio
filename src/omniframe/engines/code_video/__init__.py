"""Engine 1 — deterministic HTML/CSS/JS frame-by-frame video rendering.

An agent writes scene code; this engine renders exact frames ``0 .. N-1`` and
hands back both the PNGs and any JavaScript error with its line and column.

    >>> from omniframe.engines.code_video import CodeScene, CodeVideoRenderer
    >>> scene = CodeScene(html="<h1 id='t'>hi</h1>",
    ...                    javascript="document.getElementById('t').textContent = __OMNIFRAME_FRAME__;",
    ...                    width=640, height=360, duration_frames=12)
    >>> result = CodeVideoRenderer().render(scene, "out/scene")
    >>> result.ok
    True
"""

from __future__ import annotations

from .backends import (
    Backend,
    PlaywrightBackend,
    StubBackend,
    build_frame_payload,
    mulberry32_source,
    parse_stack_location,
    select_backend,
)
from .renderer import CodeVideoRenderer, RenderIssue, RenderResult, render_scene
from .scene import CodeScene

__all__ = [
    "Backend",
    "CodeScene",
    "CodeVideoRenderer",
    "PlaywrightBackend",
    "RenderIssue",
    "RenderResult",
    "StubBackend",
    "build_frame_payload",
    "mulberry32_source",
    "parse_stack_location",
    "render_scene",
    "select_backend",
]
