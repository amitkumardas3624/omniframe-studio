"""Tests for deterministic HTML composition metadata in the code-video engine."""

from __future__ import annotations

import pytest

from omniframe.core.errors import ValidationError
from omniframe.engines.code_video.composition import (
    composition_source,
    parse_composition,
    resolve_composition,
)

TEMPLATE = """<html data-composition-variables='{"title":"Hello","accent":"#7cf"}'>
<body>
  <span data-var="title"></span>
  <div data-track="intro" data-start="1.5" data-duration="2" data-track-index="0"></div>
  <div data-track="outro" data-start="4" data-track-index="1"></div>
  <div data-start="0.5" data-duration="1"></div>
</body></html>"""


class TestParseComposition:
    def test_reads_declared_variable_defaults(self):
        spec = parse_composition(TEMPLATE)
        assert spec.variables == {"title": "Hello", "accent": "#7cf"}

    def test_reads_track_metadata_in_document_order(self):
        spec = parse_composition(TEMPLATE)
        assert [(t.id, t.start, t.duration, t.track) for t in spec.tracks] == [
            ("intro", 1.5, 2.0, 0),
            ("outro", 4.0, None, 1),
            ("track-2", 0.5, 1.0, None),
        ]

    def test_accepts_html_without_metadata(self):
        spec = parse_composition("<div>plain</div>")
        assert spec.variables == {}
        assert spec.tracks == ()

    def test_rejects_malformed_variable_json(self):
        with pytest.raises(ValidationError):
            parse_composition("<div data-composition-variables='{oops}'></div>")

    def test_rejects_invalid_timing(self):
        with pytest.raises(ValidationError):
            parse_composition("<div data-start='-1'></div>")
        with pytest.raises(ValidationError):
            parse_composition("<div data-duration='0'></div>")


class TestResolveComposition:
    def test_params_override_declared_defaults(self):
        spec = parse_composition(TEMPLATE)
        resolved = resolve_composition(spec, {"title": "Bye", "extra": 7})
        assert resolved["variables"]["title"] == "Bye"
        assert resolved["variables"]["accent"] == "#7cf"
        assert resolved["variables"]["extra"] == 7
        assert resolved["declared"] == ["title", "accent"]

    def test_resolve_is_pure(self):
        spec = parse_composition(TEMPLATE)
        first = resolve_composition(spec, {"title": "Bye"})
        second = resolve_composition(spec, {"title": "Bye"})
        assert first == second
        assert spec.variables["title"] == "Hello"


class TestCompositionSource:
    def test_source_has_no_live_timers_or_randomness(self):
        source = composition_source({"variables": {}, "tracks": [], "declared": []})
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
        assert "__OMNIFRAME_COMPOSITION__" in source
        assert "__omniframe_track_local_time" in source


@pytest.mark.render
class TestCompositionInBrowser:
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

    def test_binds_variables_and_computes_track_time(self):
        sync_api = pytest.importorskip(
            "playwright.sync_api", reason="playwright not installed"
        )
        playwright, browser = self._browser(sync_api)
        try:
            page = browser.new_page()
            page.set_content("<html><body><span data-var='title'></span></body></html>")
            resolved = resolve_composition(parse_composition(TEMPLATE), {"title": "Hello"})
            page.evaluate(composition_source(resolved))
            assert page.locator("[data-var='title']").inner_text() == "Hello"
            sample = page.evaluate(
                """() => [
                    window.__omniframe_track_local_time('intro', 0),
                    window.__omniframe_track_local_time('intro', 1.8),
                    window.__omniframe_track_local_time('intro', 99),
                    window.__omniframe_track_local_time('missing', 3)
                ]"""
            )
            assert sample[0] == 0
            assert sample[1] == pytest.approx(0.3)
            assert sample[2] == pytest.approx(2.0)
            assert sample[3] == 3
        finally:
            browser.close()
            playwright.stop()
