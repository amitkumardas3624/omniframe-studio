"""OmniFrame Studio — agent-first video & animation control platform.

The package is intentionally layered so that an autonomous agent can operate
every capability head-lessly:

``omniframe.core.timeline_schema``
    Canonical, vendor-neutral project model shared by every engine.
``omniframe.core.agent_runtime``
    Action registry, engine router, checkpoints and visual inspection.
``omniframe.engines``
    Code-driven frame renderer, 2D cartoon pipeline and the FFmpeg compositor.
``omniframe.bridges``
    Adapters for Premiere Pro, After Effects, DaVinci Resolve, CapCut, Krita.
"""

from __future__ import annotations

__version__ = "0.2.0"


def has_native_accelerator() -> bool:
    """Return whether the optional compiled accelerator is available."""

    from ._native import native_available

    return native_available()


__all__ = ["__version__", "has_native_accelerator"]
