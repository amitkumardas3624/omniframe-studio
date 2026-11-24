"""Guards for the motion-reel template's reference-grade visual mechanics."""

from __future__ import annotations

from pathlib import Path

import pytest

from omniframe.engines.code_video import CodeScene
from omniframe.engines.code_video.composition import (
    composition_source,
    parse_composition,
    resolve_composition,
)
from omniframe.engines.code_video.seek_adapter import seek_adapter_source

BASE = Path(__file__).parents[1] / "examples" / "motion-reel-template"
MARKER = "// === FRAME ==="


def _scene() -> CodeScene:
    html = (BASE / "scene.html").read_text(encoding="utf-8")
    script = (BASE / "scene.js").read_text(encoding="utf-8")
    bootstrap, javascript = script.split(MARKER, 1)
    return CodeScene(
        html=html,
        bootstrap=bootstrap,
        javascript=javascript,
        background="#0B0A0F",
        width=1920,
        height=1080,
        fps=60.0,
        duration_frames=1,
    )


def test_systems_is_a_dense_grid():
    html = (BASE / "scene.html").read_text(encoding="utf-8")
    assert html.count('class="ring"') >= 10
    assert html.count('class="cross"') >= 16


def test_flow_has_many_strands():
    html = (BASE / "scene.html").read_text(encoding="utf-8")
    assert html.count("<path id=") >= 18


def test_sphere_dots_are_styled():
    html = (BASE / "scene.html").read_text(encoding="utf-8").replace(" ", "")
    assert "#spherei{" in html


def test_particles_sample_the_title_glyphs():
    script = (BASE / "scene.js").read_text(encoding="utf-8")
    assert "fillText" in script
    assert "getImageData" in script


def test_outro_has_full_hierarchy():
    html = (BASE / "scene.html").read_text(encoding="utf-8")
    assert 'data-var="outroMeta"' in html
    assert 'data-var="outroCaption"' in html
    assert 'id="brandDot"' in html


@pytest.mark.render
def test_dimension_sphere_dots_are_visible():
    sync_api = pytest.importorskip(
        "playwright.sync_api", reason="playwright not installed"
    )
    try:
        playwright = sync_api.sync_playwright().start()
    except Exception as exc:  # pragma: no cover - environment dependent
        pytest.skip(f"playwright could not start: {exc}")
    try:
        try:
            browser = playwright.chromium.launch(headless=True)
        except Exception as exc:  # pragma: no cover - environment dependent
            pytest.skip(f"Chromium not available: {exc}")
        try:
            scene = _scene()
            page = browser.new_page(viewport={"width": 1920, "height": 1080})
            page.set_content(scene.html)
            page.add_style_tag(
                content="html,body{margin:0;width:100%;height:100%;overflow:hidden}"
            )
            page.evaluate(
                "() => { window.__OMNIFRAME_FRAME__ = 495; "
                "window.__OMNIFRAME_TOTAL_FRAMES__ = 900; "
                "window.__OMNIFRAME_FPS__ = 60; }"
            )
            resolved = resolve_composition(parse_composition(scene.html), scene.params)
            page.evaluate(composition_source(resolved))
            page.evaluate(seek_adapter_source())
            page.evaluate(scene.bootstrap)
            page.evaluate(scene.javascript)
            info = page.evaluate(
                """() => {
                    const d = document.querySelectorAll('#sphere i');
                    const r = d[0].getBoundingClientRect();
                    return { count: d.length, width: r.width,
                             bg: getComputedStyle(d[0]).backgroundColor };
                }"""
            )
            assert info["count"] >= 40
            assert info["width"] >= 4, info
            assert info["bg"] != "rgba(0, 0, 0, 0)", info
        finally:
            browser.close()
    finally:
        playwright.stop()
