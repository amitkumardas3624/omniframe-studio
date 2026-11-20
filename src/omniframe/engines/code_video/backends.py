"""Render backends for the code-video engine.

Two backends implement the same contract:

``PlaywrightBackend``
    The real thing: a headless Chromium renders each frame from the scene
    code.  Requires the optional ``playwright`` extra.

``StubBackend``
    A dependency-free Pillow fallback that renders a deterministic placeholder
    frame.  It exists so that the whole pipeline (render -> inspect -> compose)
    stays testable on machines without a browser.  It is always reported as a
    degraded result.

Both backends receive the *same* scene payload, so a scene that renders under
one backend renders under the other with the same frame numbering.
"""

from __future__ import annotations

import json
import re
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Callable

from ...core.errors import DependencyMissing, EngineUnavailable
from ...core.logging import get_logger
from .scene import CodeScene

LOG = get_logger("engines.code_video.backends")

#: ``(severity, message, line, column, source, frame)``
IssueSink = Callable[[str, str, int | None, int | None, str | None, int | None], None]

#: Matches the ``<file>:<line>:<column>`` part of a V8 stack frame.
_LOCATION_RE = re.compile(r":(\d+):(\d+)")


def parse_stack_location(stack: str | None) -> tuple[int | None, int | None]:
    """Extract ``(line, column)`` from a V8 style stack trace.

    The *last* ``file:line:column`` pair is preferred: Playwright wraps scene
    code in a utility script, so the first pair usually points at the wrapper
    rather than at the agent's own source.
    """

    if not stack:
        return (None, None)
    found: tuple[int, int] | None = None
    for match in _LOCATION_RE.finditer(stack):
        found = (int(match.group(1)), int(match.group(2)))
    if found is None:
        return (None, None)
    return found


def mulberry32_source() -> str:
    """Return the JavaScript source of the seeded PRNG injected into a scene."""

    return """
window.__omniframe_mulberry32 = function (a) {
    return function () {
        a |= 0;
        a = (a + 0x6D2B79F5) | 0;
        var t = Math.imul(a ^ (a >>> 15), 1 | a);
        t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
        return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
    };
};
""";


def build_frame_payload(scene: CodeScene, frame: int) -> dict[str, Any]:
    """The payload injected into the page before every frame."""

    return {
        "frame": int(frame),
        "fps": float(scene.fps),
        "total_frames": int(scene.duration_frames),
        "seed": int(scene.seed),
        "params": dict(scene.params),
        "width": int(scene.width),
        "height": int(scene.height),
    }


def frame_filename(frame: int) -> str:
    """The canonical frame file name."""

    return f"frame_{frame:06d}.png"


class Backend(ABC):
    """Common contract for render backends."""

    name: str = "base"

    @abstractmethod
    def available(self) -> bool:
        """Whether this backend can run right now."""

    @abstractmethod
    def render(
        self,
        scene: CodeScene,
        output_dir: Path,
        *,
        resume: bool,
        on_issue: IssueSink,
    ) -> tuple[list[Path], bool]:
        """Render the scene.

        Returns the ordered frame paths and whether rendering completed
        without a fatal error.
        """

    def close(self) -> None:
        """Release any resources held by the backend."""


# ---------------------------------------------------------------------------
# Playwright backend
# ---------------------------------------------------------------------------

class PlaywrightBackend(Backend):
    """Renders scenes with a headless Chromium via Playwright."""

    name = "playwright"

    def __init__(self, *, headless: bool = True, browser_args: list[str] | None = None,
                 timeout_ms: int = 30000) -> None:
        self.headless = headless
        self.browser_args = list(browser_args or ["--force-color-profile=srgb",
                                                  "--disable-lcd-text",
                                                  "--font-render-hinting=none"])
        self.timeout_ms = timeout_ms
        self._playwright = None
        self._browser = None
        self._page = None

    # -- availability ---------------------------------------------------
    def available(self) -> bool:
        try:
            from playwright.sync_api import sync_playwright  # noqa: F401
        except Exception:
            return False
        try:
            with self._probe() as pw:
                browser = pw.chromium.launch(headless=True)
                browser.close()
        except Exception as exc:
            LOG.debug("chromium probe failed", extra={"error": str(exc)})
            return False
        return True

    def _probe(self):
        from playwright.sync_api import sync_playwright

        return sync_playwright()

    # -- rendering ------------------------------------------------------
    def render(
        self,
        scene: CodeScene,
        output_dir: Path,
        *,
        resume: bool,
        on_issue: IssueSink,
    ) -> tuple[list[Path], bool]:
        try:
            from playwright.sync_api import sync_playwright
        except Exception as exc:
            raise DependencyMissing(
                "The Playwright backend needs the 'playwright' extra. "
                "Install it with: pip install \"omniframe-studio[render]\" "
                "&& playwright install chromium",
                detail=str(exc),
            ) from exc

        output_dir.mkdir(parents=True, exist_ok=True)
        frames: list[Path] = []
        fatal = False
        current_frame = -1
        reported_frames: set[int] = set()

        with sync_playwright() as playwright:
            try:
                browser = playwright.chromium.launch(
                    headless=self.headless, args=self.browser_args
                )
            except Exception as exc:
                raise EngineUnavailable(
                    "Chromium could not be launched. Run `omniframe doctor --fix` "
                    "or `playwright install chromium`.",
                    detail=str(exc),
                ) from exc

            try:
                page = browser.new_page(
                    viewport={"width": scene.width, "height": scene.height},
                    device_scale_factor=1,
                )
                page.set_default_timeout(self.timeout_ms)

                def frame_of() -> int:
                    return current_frame

                def event_error(
                    severity: str,
                    message: str,
                    line: int | None,
                    column: int | None,
                    source: str | None,
                    frame: int | None,
                ) -> None:
                    if frame is not None and severity == "error":
                        reported_frames.add(frame)
                    on_issue(severity, message, line, column, source, frame)

                page.on("console", self._console_handler(event_error, frame_of))
                page.on("pageerror", self._page_error_handler(event_error, frame_of))

                self._prepare_page(page, scene)

                for frame in range(scene.duration_frames):
                    current_frame = frame
                    target = output_dir / frame_filename(frame)
                    if resume and target.exists():
                        frames.append(target)
                        continue

                    if not self._apply_frame(page, scene, frame, event_error, reported_frames):
                        fatal = True
                        break

                    if not self._settle(page, scene, event_error):
                        fatal = True
                        break

                    page.screenshot(
                        path=str(target),
                        omit_background=bool(scene.transparent),
                        animations="disabled",
                    )
                    frames.append(target)
            finally:
                try:
                    browser.close()
                except Exception:  # pragma: no cover - best effort
                    pass

        return frames, not fatal

    # -- internals ------------------------------------------------------
    def _prepare_page(self, page: Any, scene: CodeScene) -> None:
        page.set_content(scene.html, wait_until="load")

        base_css = (
            "html, body { margin: 0; padding: 0; width: 100%; height: 100%; "
            f"overflow: hidden; background: {scene.background}; }}"
        )
        page.add_style_tag(content=base_css)

        if scene.css:
            page.add_style_tag(content=scene.css)

        # Freeze CSS animation unless the scene explicitly opts in.
        if not self._wants_animation(page):
            page.add_style_tag(
                content=(
                    "*, *::before, *::after { "
                    "animation-play-state: paused !important; "
                    "transition: none !important; "
                    "animation-delay: 0s !important; }"
                )
            )

        page.evaluate(mulberry32_source())
        page.evaluate(
            """
            () => {
                window.__OMNIFRAME_PARAMS__ = {};
                window.__OMNIFRAME_FRAME__ = 0;
                window.__OMNIFRAME_FPS__ = 0;
                window.__OMNIFRAME_TOTAL_FRAMES__ = 0;
                window.__OMNIFRAME_SEED__ = 0;
                window.__OMNIFRAME_RANDOM__ = function () { return 0; };
            }
            """
        )

        if scene.bootstrap:
            try:
                page.evaluate(f"(function () {{ {scene.bootstrap} }})()")
            except Exception as exc:
                LOG.warning("bootstrap failed", extra={"error": str(exc)})

    @staticmethod
    def _wants_animation(page: Any) -> bool:
        try:
            return bool(
                page.evaluate(
                    """
                    () => {
                        const root = document.documentElement;
                        const body = document.body;
                        return !!(
                            (root && root.getAttribute('data-omniframe-animate') !== null) ||
                            (body && body.getAttribute('data-omniframe-animate') !== null)
                        );
                    }
                    """
                )
            )
        except Exception:  # pragma: no cover - defensive
            return False

    def _apply_frame(
        self,
        page: Any,
        scene: CodeScene,
        frame: int,
        on_issue: IssueSink,
        reported_frames: set[int],
    ) -> bool:
        """Push the frame state and run the scene code.

        Returns ``False`` when the scene raised, which stops the render.
        """

        payload = build_frame_payload(scene, frame)
        try:
            page.evaluate("window.__OMNIFRAME_PAYLOAD__ = " + json.dumps(payload))
            page.evaluate(
                """
                () => {
                    const p = window.__OMNIFRAME_PAYLOAD__;
                    window.__OMNIFRAME_FRAME__ = p.frame;
                    window.__OMNIFRAME_FPS__ = p.fps;
                    window.__OMNIFRAME_TOTAL_FRAMES__ = p.total_frames;
                    window.__OMNIFRAME_SEED__ = p.seed;
                    window.__OMNIFRAME_PARAMS__ = p.params;
                    window.__OMNIFRAME_RANDOM__ = window.__omniframe_mulberry32(p.seed + p.frame);
                }
                """
            )
            if scene.javascript:
                page.evaluate(f"(function () {{ {scene.javascript} }})()")
        except Exception as exc:
            text = str(exc)
            line, column = parse_stack_location(text)
            message = text.splitlines()[0] if text else type(exc).__name__
            if frame not in reported_frames:
                on_issue("error", message, line, column, "pageerror", frame)
            return False
        return True

    def _settle(self, page: Any, scene: CodeScene, on_issue: IssueSink) -> bool:
        """Wait for the frame to be visually stable.  Returns False on a fatal error."""

        try:
            page.evaluate(
                """
                () => new Promise((resolve) => {
                    requestAnimationFrame(() => requestAnimationFrame(() => resolve(true)));
                })
                """
            )
        except Exception as exc:
            LOG.debug("settle failed", extra={"error": str(exc)})

        if scene.settle_selector:
            try:
                page.wait_for_selector(scene.settle_selector, state="attached")
            except Exception as exc:
                LOG.debug("settle selector timeout", extra={"error": str(exc)})

        try:
            waits = page.evaluate("() => !!window.__OMNIFRAME_WAIT_FOR_READY__")
        except Exception:
            waits = False

        if waits:
            try:
                page.wait_for_function(
                    "() => window.__OMNIFRAME_READY__ === true",
                    timeout=scene.settle_timeout_ms,
                )
            except Exception as exc:
                LOG.debug("ready timeout", extra={"error": str(exc)})
                on_issue(
                    "error",
                    "The scene never set window.__OMNIFRAME_READY__ within the settle timeout.",
                    None,
                    None,
                    "settle",
                    None,
                )
                return False

        return True

    # -- event handlers -------------------------------------------------
    @staticmethod
    def _console_handler(on_issue: IssueSink, frame_of: Callable[[], int]):
        def handler(message: Any) -> None:
            kind = getattr(message, "type", "log")
            if kind not in {"error", "warning"}:
                return
            location = {}
            try:
                location = message.location or {}
            except Exception:  # pragma: no cover - defensive
                location = {}
            line = location.get("lineNumber")
            column = location.get("columnNumber")
            on_issue(
                "error" if kind == "error" else "warning",
                getattr(message, "text", str(message)),
                int(line) if isinstance(line, int) and line > 0 else None,
                int(column) if isinstance(column, int) and column > 0 else None,
                "console",
                frame_of(),
            )

        return handler

    @staticmethod
    def _page_error_handler(on_issue: IssueSink, frame_of: Callable[[], int]):
        def handler(error: Any) -> None:
            message = getattr(error, "message", None) or str(error)
            stack = getattr(error, "stack", None)
            line, column = parse_stack_location(stack)
            on_issue("error", message, line, column, "pageerror", frame_of())

        return handler


# ---------------------------------------------------------------------------
# Stub backend
# ---------------------------------------------------------------------------

class StubBackend(Backend):
    """A dependency-free deterministic placeholder renderer.

    It renders the scene background, the frame number and any ``text`` entry
    in ``scene.params``.  It exists so that CI and machines without Chromium
    can still exercise the full render -> inspect -> compose pipeline.
    """

    name = "stub"

    def available(self) -> bool:
        return True

    def render(
        self,
        scene: CodeScene,
        output_dir: Path,
        *,
        resume: bool,
        on_issue: IssueSink,
    ) -> tuple[list[Path], bool]:
        from PIL import Image, ImageDraw

        output_dir.mkdir(parents=True, exist_ok=True)
        frames: list[Path] = []

        text = str(scene.params.get("text", ""))
        for frame in range(scene.duration_frames):
            target = output_dir / frame_filename(frame)
            if resume and target.exists():
                frames.append(target)
                continue

            image = Image.new("RGBA", (scene.width, scene.height), self._rgba(scene.background))
            draw = ImageDraw.Draw(image)
            draw.rectangle(
                [0, 0, scene.width - 1, scene.height - 1],
                outline=(120, 130, 160, 255),
                width=max(1, scene.width // 400),
            )
            label = f"frame {frame:06d} / {scene.duration_frames}"
            draw.text((24, 24), label, fill=(235, 235, 245, 255))
            if text:
                draw.text((24, 60), text[:120], fill=(200, 210, 240, 255))
            image.save(target)
            frames.append(target)

        on_issue(
            "warning",
            "Chromium was unavailable - frames were rendered by the deterministic stub backend.",
            None,
            None,
            "backend",
            None,
        )
        return frames, True

    @staticmethod
    def _rgba(value: str) -> tuple[int, int, int, int]:
        text = (value or "#00000000").strip().lstrip("#")
        if len(text) == 6:
            text += "FF"
        if len(text) != 8:
            return (0, 0, 0, 255)
        try:
            return (
                int(text[0:2], 16),
                int(text[2:4], 16),
                int(text[4:6], 16),
                int(text[6:8], 16),
            )
        except ValueError:
            return (0, 0, 0, 255)


# ---------------------------------------------------------------------------
# Backend selection
# ---------------------------------------------------------------------------

def select_backend(
    preference: str = "auto",
    *,
    headless: bool = True,
    browser_args: list[str] | None = None,
    timeout_ms: int = 30000,
) -> Backend:
    """Pick a backend according to ``preference``.

    ``auto`` prefers Playwright and silently degrades to the stub backend.
    """

    preference = (preference or "auto").lower()
    if preference == "stub":
        return StubBackend()
    if preference == "playwright":
        backend = PlaywrightBackend(
            headless=headless, browser_args=browser_args, timeout_ms=timeout_ms
        )
        if not backend.available():
            raise EngineUnavailable(
                "The Playwright backend was requested but Chromium is unavailable. "
                "Run `omniframe doctor --fix` or `playwright install chromium`."
            )
        return backend
    if preference != "auto":
        raise ValueError(f"Unknown backend '{preference}' (expected auto, playwright or stub).")

    backend = PlaywrightBackend(
        headless=headless, browser_args=browser_args, timeout_ms=timeout_ms
    )
    if backend.available():
        return backend
    LOG.info("falling back to the stub backend")
    return StubBackend()
