"""The scene description handed to the code-video engine."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class CodeScene:
    """An HTML/CSS/JS scene that is rendered frame by frame.

    The scene code is deterministic by construction: it receives the current
    frame number and the project fps, and it may use ``__OMNIFRAME_RANDOM__``
    for seeded randomness.  Nothing in the engine depends on wall-clock time.
    """

    html: str = "<div id='scene'></div>"
    css: str = ""
    javascript: str = ""
    bootstrap: str | None = None
    width: int = 1920
    height: int = 1080
    fps: float = 30.0
    duration_frames: int = 60
    seed: int = 0
    transparent: bool = False
    background: str = "#00000000"
    params: dict[str, Any] = field(default_factory=dict)
    settle_timeout_ms: int = 250
    #: Optional CSS selector that must exist before a frame is captured.
    settle_selector: str | None = None

    def __post_init__(self) -> None:
        if self.duration_frames < 1:
            raise ValueError("duration_frames must be >= 1")
        if self.width < 1 or self.height < 1:
            raise ValueError("width and height must be >= 1")
        if self.fps <= 0:
            raise ValueError("fps must be > 0")

    @classmethod
    def from_clip(cls, clip: Any, project: Any) -> "CodeScene":
        """Build a scene from a ``Clip`` and its owning ``OmniProject``."""

        from ...core.errors import SchemaError

        payload = getattr(clip, "code", None)
        if payload is None:
            raise SchemaError(
                f"Clip '{getattr(clip, 'id', '?')}' is a code_scene but carries no code payload."
            )

        meta = project.meta
        return cls(
            html=payload.html,
            css=payload.css,
            javascript=payload.javascript,
            bootstrap=payload.bootstrap,
            width=int(meta.width),
            height=int(meta.height),
            fps=float(meta.fps),
            duration_frames=int(clip.duration_frames),
            seed=int(payload.seed),
            transparent=bool(payload.transparent),
            background=payload.background,
            params=dict(payload.params),
            settle_timeout_ms=int(payload.settle_timeout_ms),
        )
