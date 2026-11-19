"""Render engines.

Sub-packages:

``code_video``
    Deterministic HTML/CSS/JS/Canvas frame-by-frame renderer.
``cartoon_2d``
    Frame-by-frame 2D cartoon pipeline (layers, x-sheets, lip-sync).
``compositor``
    FFmpeg based assembly, mixing, subtitles and export.

Each engine is importable independently; none of them import the others, so
an agent can install only the parts it needs.
"""

from __future__ import annotations

__all__ = ["cartoon_2d", "code_video", "compositor"]
