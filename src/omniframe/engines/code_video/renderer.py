"""The code-video renderer.

``CodeVideoRenderer`` turns a :class:`~omniframe.engines.code_video.scene.CodeScene`
into a deterministic sequence of PNG frames and reports every problem it hit
as a structured :class:`RenderIssue` — including the exact line and column of a
JavaScript error, so an agent can fix its own scene code without guessing.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from ...core.errors import ValidationError
from ...core.logging import get_logger
from ..compositor.raw_stream import RawVideoStream
from .backends import Backend, select_backend
from .scene import CodeScene

LOG = get_logger("engines.code_video.renderer")


@dataclass
class RenderIssue:
    """One problem detected while rendering."""

    severity: str = "error"
    message: str = ""
    source: str = "console"
    line: int | None = None
    column: int | None = None
    frame: int | None = None
    stack: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "severity": self.severity,
            "message": self.message,
            "source": self.source,
            "line": self.line,
            "column": self.column,
            "frame": self.frame,
            "stack": self.stack,
        }

    def __str__(self) -> str:  # pragma: no cover - trivial
        where = f" (line {self.line}" + (f", column {self.column}" if self.column else "") + ")" if self.line else ""
        at = f" [frame {self.frame}]" if self.frame is not None else ""
        return f"{self.severity.upper()}{at}{where}: {self.message}"


@dataclass
class RenderResult:
    """The outcome of a render run."""

    frames: list[Path] = field(default_factory=list)
    frame_dir: Path = Path(".")
    fps: float = 30.0
    duration_frames: int = 0
    width: int = 0
    height: int = 0
    issues: list[RenderIssue] = field(default_factory=list)
    ok: bool = True
    backend: str = "unknown"
    duration_seconds: float = 0.0
    stream_output: str | None = None
    #: Whether the underlying backend finished all frames without a fatal error.
    completed: bool = True
    #: How far along the render pipeline this result can claim to be.
    #: One of ``generated | structurally_checked | import_tested | render_tested | production_candidate``.
    verification_level: str = "generated"
    #: Whether the resolved backend was functional when the render started.
    backend_available: bool = False
    #: Whether this run was resuming a previous checkpoint.
    resume_requested: bool = False
    #: Optional :class:`~omniframe.engines.compositor.golden.GoldenReport` dict
    #: attached when a ``verify_against`` reference was supplied to ``render``.
    golden: dict | None = None

    @property
    def errors(self) -> list[RenderIssue]:
        """Every issue with severity ``error``."""

        return [issue for issue in self.issues if issue.severity == "error"]

    @property
    def warnings(self) -> list[RenderIssue]:
        return [issue for issue in self.issues if issue.severity == "warning"]

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "backend": self.backend,
            "frame_dir": str(self.frame_dir),
            "frames": [str(f) for f in self.frames],
            "frame_count": len(self.frames),
            "fps": self.fps,
            "duration_frames": self.duration_frames,
            "width": self.width,
            "height": self.height,
            "duration_seconds": round(self.duration_seconds, 3),
            "stream_output": self.stream_output,
            "stream_mode": self.stream_output is not None,
            "completed": self.completed,
            "verification_level": self.verification_level,
            "backend_available": self.backend_available,
            "resume_requested": self.resume_requested,
            "golden": self.golden,
            "issues": [issue.to_dict() for issue in self.issues],
            "error_count": len(self.errors),
        }


class CodeVideoRenderer:
    """Render HTML/CSS/JS scenes frame by frame."""

    def __init__(
        self,
        *,
        backend: str = "auto",
        headless: bool = True,
        browser_args: list[str] | None = None,
        timeout_ms: int = 30000,
    ) -> None:
        self.backend_preference = backend
        self.headless = headless
        self.browser_args = list(browser_args) if browser_args else None
        self.timeout_ms = timeout_ms
        self._backend: Backend | None = None

    # -- backend --------------------------------------------------------
    @property
    def backend(self) -> Backend:
        """The backend actually in use (resolved lazily)."""

        if self._backend is None:
            self._backend = select_backend(
                self.backend_preference,
                headless=self.headless,
                browser_args=self.browser_args,
                timeout_ms=self.timeout_ms,
            )
        return self._backend

    @property
    def backend_name(self) -> str:
        return self.backend.name

    def available(self) -> bool:
        """Whether a real (non-stub) renderer is usable on this machine."""

        try:
            return self.backend.available() and self.backend.name != "stub"
        except Exception:  # pragma: no cover - defensive
            return False

    # -- rendering ------------------------------------------------------
    def render(
        self,
        scene: CodeScene,
        output_dir: str | Path,
        *,
        resume: bool = False,
        stream_to_ffmpeg: str | Path | None = None,
        verify_against: str | Path | None = None,
    ) -> RenderResult:
        """Render ``scene`` into PNGs or stream raw RGBA frames to FFmpeg.

        When ``verify_against`` is set and the render completes, the produced
        frames in ``output_dir`` are checked against that golden reference
        directory and the resulting :class:`GoldenReport` dict is attached to
        the ``golden`` result field.
        """

        if stream_to_ffmpeg is not None and resume:
            raise ValidationError(
                "stream_to_ffmpeg cannot be combined with resume/checkpoint rendering",
                stream_to_ffmpeg=str(stream_to_ffmpeg),
            )

        target_dir = Path(output_dir)
        target_dir.mkdir(parents=True, exist_ok=True)

        issues: list[RenderIssue] = []

        def sink(
            severity: str,
            message: str,
            line: int | None,
            column: int | None,
            source: str | None,
            frame: int | None,
        ) -> None:
            issues.append(
                RenderIssue(
                    severity=severity,
                    message=message,
                    source=source or "console",
                    line=line,
                    column=column,
                    frame=frame,
                )
            )

        started = time.monotonic()
        if stream_to_ffmpeg is None:
            frames, completed = self.backend.render(
                scene,
                target_dir,
                resume=resume,
                on_issue=sink,
            )
        else:
            with RawVideoStream(
                stream_to_ffmpeg,
                width=scene.width,
                height=scene.height,
                fps=scene.fps,
                extra_args=("-pix_fmt", "yuv420p"),
            ) as stream:
                frames, completed = self.backend.render(
                    scene,
                    target_dir,
                    resume=False,
                    on_issue=sink,
                    on_frame=stream.write,
                )
        elapsed = time.monotonic() - started

        ok = completed and not [i for i in issues if i.severity == "error"]
        if not completed:
            ok = False

        golden: dict | None = None
        if verify_against is not None and completed:
            # Lazy import keeps the hash-only golden path Pillow-independent and
            # avoids an import cycle between the code_video and compositor engines.
            from ..compositor.golden import verify_frames

            golden = verify_frames(verify_against, target_dir).to_dict()

        backend_name = self.backend.name
        try:
            backend_available = self.backend.available()
        except Exception:  # pragma: no cover - defensive
            backend_available = False

        if backend_name not in {"stub", "unknown"} and completed and ok:
            verification_level = "render_tested"
        elif backend_name == "stub":
            verification_level = "import_tested"
        else:
            verification_level = "generated"

        result = RenderResult(
            frames=list(frames),
            frame_dir=target_dir,
            fps=scene.fps,
            duration_frames=scene.duration_frames,
            width=scene.width,
            height=scene.height,
            issues=issues,
            ok=ok,
            backend=backend_name,
            duration_seconds=elapsed,
            stream_output=str(stream_to_ffmpeg) if stream_to_ffmpeg is not None else None,
            completed=completed,
            verification_level=verification_level,
            backend_available=backend_available,
            resume_requested=bool(resume),
            golden=golden,
        )

        if issues:
            LOG.warning(
                "render finished with issues",
                extra={"issues": len(issues), "errors": len(result.errors)},
            )
        return result

    def render_clip(
        self,
        clip: Any,
        project: Any,
        output_dir: str | Path,
        *,
        resume: bool = False,
    ) -> RenderResult:
        """Render a project ``clip`` that carries a code-scene payload."""

        scene = CodeScene.from_clip(clip, project)
        return self.render(scene, output_dir, resume=resume)


def render_scene(scene: CodeScene, output_dir: str | Path, **kwargs: Any) -> RenderResult:
    """Convenience wrapper around :meth:`CodeVideoRenderer.render`."""

    renderer = CodeVideoRenderer(
        backend=kwargs.pop("backend", "auto"),
        headless=kwargs.pop("headless", True),
    )
    return renderer.render(scene, output_dir, **kwargs)
