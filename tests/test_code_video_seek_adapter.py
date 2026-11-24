"""Tests for the optional deterministic seek adapter in the code-video engine."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from omniframe.core.errors import ValidationError
from omniframe.engines.code_video import CodeScene, CodeVideoRenderer
from omniframe.engines.code_video.composition import (
    composition_source,
    parse_composition,
    resolve_composition,
)
from omniframe.engines.code_video.seek_adapter import (
    SEEK_KINDS,
    SeekBinding,
    local_time,
    seek_adapter_source,
)


class TestSeekBinding:
    def test_rejects_unknown_kind(self):
        with pytest.raises(ValidationError):
            SeekBinding(name="tl", kind="flash")

    def test_rejects_negative_start(self):
        with pytest.raises(ValidationError):
            SeekBinding(name="tl", start=-0.1)

    def test_rejects_zero_duration(self):
        with pytest.raises(ValidationError):
            SeekBinding(name="tl", duration=0)

    def test_accepts_known_kinds(self):
        assert SEEK_KINDS == frozenset({"gsap", "lottie", "three", "custom"})
        for kind in sorted(SEEK_KINDS):
            assert SeekBinding(name="tl", kind=kind).kind == kind


class TestLocalTime:
    def test_is_clamped_to_the_binding_window(self):
        assert local_time(0.0, 1.0, 2.0) == 0.0
        assert local_time(1.5, 1.0, 2.0) == pytest.approx(0.5)
        assert local_time(9.0, 1.0, 2.0) == 2.0

    def test_is_pure_across_repeated_calls(self):
        times = (0.2, 1.2, 2.0, 0.2)
        first = [local_time(t, 0.5, 1.0) for t in times]
        assert first == [local_time(t, 0.5, 1.0) for t in times]

    def test_without_duration_only_clamps_the_lower_bound(self):
        assert local_time(0.1, 1.0, None) == 0.0
        assert local_time(7.5, 1.0, None) == pytest.approx(6.5)


class TestSeekAdapterSource:
    def test_source_has_no_live_timers_or_randomness(self):
        source = seek_adapter_source()
        for forbidden in (
            "requestAnimationFrame",
            "setTimeout",
            "setInterval",
            "Date.now",
            "performance.now",
            "Math.random",
            "element.animate",
        ):
            assert forbidden not in source
        assert "window.__omniframe_seek_adapter" in source
        assert "goToAndStop" in source


@pytest.mark.render
class TestSeekAdapterInBrowser:
    @staticmethod
    def _browser(sync_api):
        try:
            playwright = sync_api.sync_playwright().start()
        except Exception as exc:  # pragma: no cover - environment dependent
            pytest.skip(f"playwright could not start: {exc}")
        try:
            browser = playwright.chromium.launch(headless=True)
        except Exception as exc:  # pragma: no cover - environment dependent
            playwright.stop()
            pytest.skip(f"Chromium not available: {exc}")
        return playwright, browser

    def test_scrubs_gsap_style_timeline_from_t(self):
        sync_api = pytest.importorskip(
            "playwright.sync_api", reason="playwright not installed"
        )
        playwright, browser = self._browser(sync_api)
        try:
            page = browser.new_page()
            page.set_content("<html><body></body></html>")
            page.evaluate(seek_adapter_source())
            registered = page.evaluate(
                """() => {
                    window.__SEEN__ = [];
                    const fake = { time(v, suppress) {
                        window.__SEEN__.push([v, suppress, window.__OMNIFRAME_FRAME__]);
                    } };
                    return window.__omniframe_seek_adapter.register(
                        'tl', fake, { kind: 'gsap', start: 1, duration: 2 });
                }"""
            )
            assert registered is True
            for frame, t in ((15, 1.5), (25, 2.5)):
                page.evaluate(
                    """([frame, t]) => {
                        window.__OMNIFRAME_FRAME__ = frame;
                        window.__omniframe_seek_adapter.seek(t, frame);
                    }""",
                    [frame, t],
                )
            assert page.evaluate("() => window.__SEEN__") == [
                [0.5, False, 15],
                [1.5, False, 25],
            ]
        finally:
            browser.close()
            playwright.stop()

    def test_missing_library_is_skipped_gracefully(self):
        sync_api = pytest.importorskip(
            "playwright.sync_api", reason="playwright not installed"
        )
        playwright, browser = self._browser(sync_api)
        try:
            page = browser.new_page()
            page.set_content("<html><body></body></html>")
            page.evaluate(seek_adapter_source())
            registered = page.evaluate(
                """() => window.__omniframe_seek_adapter.register(
                    'absent', null, { kind: 'gsap' })"""
            )
            assert registered is False
            page.evaluate("() => window.__omniframe_seek_adapter.seek(1, 10)")
            assert page.evaluate("() => window.__omniframe_seek_adapter.names()") == []
        finally:
            browser.close()
            playwright.stop()

    def test_track_metadata_from_composition_drives_local_time(self):
        sync_api = pytest.importorskip(
            "playwright.sync_api", reason="playwright not installed"
        )
        playwright, browser = self._browser(sync_api)
        try:
            page = browser.new_page()
            page.set_content("<html><body><span id='v'></span></body></html>")
            resolved = resolve_composition(
                parse_composition(
                    "<div data-composition-variables='{}' "
                    "data-track='intro' data-start='1' data-duration='2'></div>"
                ),
                {},
            )
            page.evaluate(composition_source(resolved))
            page.evaluate(seek_adapter_source())
            page.evaluate(
                """() => window.__omniframe_seek_adapter.register(
                    'x', document.getElementById('v'),
                    { kind: 'custom', track: 'intro',
                      seek: (local) => { document.getElementById('v').textContent = String(local); } })"""
            )
            page.evaluate("() => window.__omniframe_seek_adapter.seek(1.75, 17)")
            assert float(page.locator("#v").inner_text()) == pytest.approx(0.75)
        finally:
            browser.close()
            playwright.stop()

    def test_example_renders_byte_identical_frames(self, tmp_path):
        """The shipped example proves scrubbing is a pure function of t."""

        renderer = CodeVideoRenderer(backend="playwright")
        if not renderer.available():
            pytest.skip("Chromium is not available")

        example = (
            Path(__file__).parents[1] / "examples" / "seek-adapter" / "project.json"
        )
        payload = json.loads(example.read_text(encoding="utf-8"))
        code = payload["tracks"][0]["clips"][0]["code"]
        meta = payload["meta"]
        scene = CodeScene(
            html=code["html"],
            css=code["css"],
            javascript=code["javascript"],
            bootstrap=code["bootstrap"],
            params=code["params"],
            seed=code["seed"],
            width=int(meta["width"]),
            height=int(meta["height"]),
            fps=float(meta["fps"]),
            duration_frames=4,
        )

        first = renderer.render(scene, tmp_path / "a")
        second = renderer.render(scene, tmp_path / "b")
        assert first.ok, [str(issue) for issue in first.issues]
        assert second.ok, [str(issue) for issue in second.issues]
        assert len(first.frames) == len(second.frames) == 4
        for left, right in zip(first.frames, second.frames, strict=True):
            assert left.read_bytes() == right.read_bytes()
