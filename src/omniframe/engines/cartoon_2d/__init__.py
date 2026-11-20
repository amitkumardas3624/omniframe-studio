"""Engine 2 — frame-by-frame 2D cartoon and drawing pipeline.

Layers are animated with per-property keyframes, evaluated into effective
values for every frame, and composited into a PNG sequence.  An exposure
sheet (x-sheet) exposes the timing of the whole scene, and dialogue / beat
markers carry the audio sync information.

    >>> from omniframe.engines.cartoon_2d import CartoonScene, Layer, render_frames
    >>> scene = CartoonScene(width=320, height=180, duration_frames=4,
    ...                      layers=[Layer(id="bg", kind="solid", color="#FF3366FF")])
    >>> frames = render_frames(scene, "out/cartoon")
    >>> len(frames)
    4
"""

from __future__ import annotations

from .bridge import BRIDGES, DrawingBridge, KritaBridge, get_bridge
from .render import (
    build_contact_sheet,
    build_frame_strip,
    frame_filename,
    parse_color,
    render_frame,
    render_frames,
)
from .scene import (
    CartoonProject,
    CartoonScene,
    Keyframe,
    Layer,
    evaluate_layer,
    evaluate_scene,
    lower_native_scene,
    resolve_source,
)
from .tween import Easing, interpolate, tween_value
from .xsheet import build_xsheet, xsheet_summary

__all__ = [
    "BRIDGES",
    "CartoonProject",
    "CartoonScene",
    "DrawingBridge",
    "Easing",
    "Keyframe",
    "KritaBridge",
    "Layer",
    "build_contact_sheet",
    "build_frame_strip",
    "build_xsheet",
    "evaluate_layer",
    "evaluate_scene",
    "frame_filename",
    "get_bridge",
    "interpolate",
    "lower_native_scene",
    "parse_color",
    "render_frame",
    "render_frames",
    "resolve_source",
    "tween_value",
    "xsheet_summary",
]
