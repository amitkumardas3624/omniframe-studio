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
from .composition import (
    CompositionSpec,
    TrackSpec,
    composition_source,
    parse_composition,
    resolve_composition,
)
from .renderer import CodeVideoRenderer, RenderIssue, RenderResult, render_scene
from .scene import CodeScene
from .seek_adapter import (
    SEEK_KINDS,
    SeekBinding,
    local_time,
    seek_adapter_source,
)

__all__ = [
    "Backend",
    "CodeScene",
    "CodeVideoRenderer",
    "CompositionSpec",
    "PlaywrightBackend",
    "RenderIssue",
    "RenderResult",
    "SEEK_KINDS",
    "SeekBinding",
    "StubBackend",
    "TrackSpec",
    "build_frame_payload",
    "composition_source",
    "local_time",
    "mulberry32_source",
    "parse_composition",
    "parse_stack_location",
    "render_scene",
    "resolve_composition",
    "seek_adapter_source",
    "select_backend",
]
