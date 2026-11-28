"""Phase 2 editor shell: three-region layout, frame-derived time, stale requests.

Acceptance criteria for the editor shell in
docs/superpowers/specs/2026-11-25-studio-editor-live-preview-design.md:

- the shell has three named regions: preview-left, timeline-bottom,
  inspector-right, placed by one CSS grid;
- the shell is anchored to the real console geometry (the 260px sidebar column
  and the 64px header/footer rows) so it never overlaps the navigation;
- time is derived from an integer frame as t = frame / fps - the frame is the
  source of truth, never a float playhead;
- a slower, older preview response can never overwrite a newer one, because the
  in-flight request is aborted and a request sequence guard rejects leftovers.

tests/test_ui_editor.py keeps the original Phase 2 contract and is left
untouched; this file adds the layout and racing guarantees on top.
"""

from __future__ import annotations

import contextlib
import re
import socket
import threading
import time
from pathlib import Path

import pytest

pytest.importorskip("fastapi")

from fastapi.testclient import TestClient  # noqa: E402

from omniframe.backend.server import create_app  # noqa: E402

PROJECT = (
    Path(__file__).resolve().parents[1] / "examples" / "code-explainer" / "project.json"
)

REGIONS = ("preview-left", "timeline-bottom", "inspector-right")


def _served_html() -> str:
    with TestClient(create_app()) as client:
        response = client.get("/ui")
    assert response.status_code == 200, response.text
    return response.text


def _editor_section(html: str) -> str:
    at = html.index('id="editor-panel"')
    return html[at : html.index("</section>", at)]


# -- three named regions ---------------------------------------------------


def test_editor_shell_declares_each_region_exactly_once() -> None:
    section = _editor_section(_served_html())
    for region in REGIONS:
        assert section.count(f'data-region="{region}"') == 1, region


def test_editor_shell_is_one_grid_with_named_areas() -> None:
    html = _served_html()
    areas = re.search(r"grid-template-areas\s*:\s*([^;]+);", html, re.S)
    assert areas is not None, "the editor shell needs grid-template-areas"
    declared = areas.group(1)
    for region in REGIONS:
        assert region in declared, f"grid-template-areas omits {region}"
        assert f"grid-area: {region}" in html, f"no element claims grid-area {region}"


def test_editor_regions_are_the_expected_panels() -> None:
    section = _editor_section(_served_html())
    preview = re.search(r'data-region="preview-left"[^>]*>', section).group(0)
    timeline = re.search(r'data-region="timeline-bottom"[^>]*>', section).group(0)
    inspector = re.search(r'data-region="inspector-right"[^>]*>', section).group(0)
    assert "grid-area: preview-left" in preview
    assert "grid-area: timeline-bottom" in timeline
    assert "grid-area: inspector-right" in inspector
    # The preview region owns the rendered image; the inspector owns the
    # project path field; the timeline region owns the scrub control.
    assert section.index('id="editor-preview"') > section.index('data-region="preview-left"')
    for token in ('id="editor-project-path"', 'id="editor-save-btn"'):
        assert token in section
    assert section.index('id="editor-scrub"') > section.index('data-region="timeline-bottom"')
    assert section.index('id="editor-scrub"') < section.index('data-region="inspector-right"')


# -- anchored to the real console geometry --------------------------------


def test_editor_panel_is_anchored_to_the_console_grid() -> None:
    """The shell must sit in the main column, not on top of the sidebar.

    body declares "grid-template-columns: <sidebar> 1fr" and
    "grid-template-rows: <header> 1fr [<footer>]"; every docked panel is
    positioned: fixed through the shared .panel rule, so those exact numbers
    have to be repeated in its inset. A stale 240px/24px inset silently
    overlaps the navigation and the status bar.
    """
    html = _served_html()
    columns = re.search(r"grid-template-columns:\s*(\d+)px\s+1fr;", html)
    rows = re.search(r"grid-template-rows:\s*(\d+)px\s+1fr(?:\s+(\d+)px)?;", html)
    assert columns is not None and rows is not None
    sidebar, header = int(columns[1]), int(rows[1])
    footer = int(rows[2]) if rows[2] else 0

    rule = re.search(r"\.panel\s*\{[^}]*position:\s*fixed;[^}]*\}", html)
    assert rule is not None, "the shared .panel rule must dock the panels"
    inset = rule[0]
    assert f"left: {sidebar}px" in inset, inset
    assert f"top: {header}px" in inset, inset
    assert (f"bottom: {footer}px" if footer else "bottom: 0;") in inset, inset


# -- time is derived from an integer frame ---------------------------------


def test_editor_derives_time_from_the_integer_frame() -> None:
    html = _served_html()
    assert "function editorFps()" in html
    assert "function editorTimeFromFrame(frame)" in html
    assert "frame / editorFps()" in html, "t must be frame divided by fps"
    assert 'id="editor-time-meta"' in html


def test_editor_labels_every_scrub_control() -> None:
    html = _served_html()
    for control in ("editor-project-path", "editor-frame", "editor-scrub", "editor-zoom"):
        assert f'for="{control}"' in html, control


# -- a stale preview may never win ---------------------------------------


def test_editor_aborts_the_previous_preview_request_before_a_new_one() -> None:
    html = _served_html()
    assert "new AbortController()" in html
    assert "signal: controller.signal" in html
    assert "editorAbort.abort()" in html
    assert "error.name === 'AbortError'" in html
    assert html.index("editorAbort.abort()") < html.index("fetch('/api/v1/preview/frame'")


def test_editor_drops_a_response_overtaken_by_a_newer_request() -> None:
    html = _served_html()
    assert "if (requestId !== editorRequestId) return;" in html


# -- browser layer ---------------------------------------------------------


@contextlib.contextmanager
def _served_app():
    uvicorn = pytest.importorskip("uvicorn", reason="ui extra not installed")
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind(("127.0.0.1", 0))
    sock.listen(128)
    port = sock.getsockname()[1]
    config = uvicorn.Config(create_app(), log_level="error", lifespan="on")
    server = uvicorn.Server(config)
    thread = threading.Thread(target=server.run, kwargs={"sockets": [sock]}, daemon=True)
    thread.start()
    deadline = time.monotonic() + 20.0
    while not server.started and time.monotonic() < deadline:
        time.sleep(0.01)
    try:
        if not server.started:
            raise RuntimeError("uvicorn did not start")
        yield f"http://127.0.0.1:{port}"
    finally:
        server.should_exit = True
        thread.join(timeout=10)
        sock.close()


def _open_editor(playwright_instance):
    browser = playwright_instance.chromium.launch(headless=True)
    page = browser.new_page(viewport={"width": 1600, "height": 900})
    return browser, page


def _load_project(page, base_url):
    page.goto(base_url + "/ui")
    page.click('[data-panel="editor"]')
    assert page.locator("#editor-panel").is_visible()
    page.fill("#editor-project-path", str(PROJECT))
    page.click("#editor-load-btn")
    page.wait_for_function(
        "() => { const i = document.getElementById('editor-preview');"
        " return i && i.src.startsWith('data:image/png'); }",
        timeout=25000,
    )


RATIOS_JS = (
    "() => {"
    " const r = (sel) => { const b = document.querySelector(sel).getBoundingClientRect();"
    " return {x: b.x, y: b.y, w: b.width, h: b.height}; };"
    " return { preview: r('[data-region=preview-left]'),"
    " timeline: r('[data-region=timeline-bottom]'),"
    " inspector: r('[data-region=inspector-right]') };"
    "}"
)


@pytest.mark.render
def test_editor_regions_are_laid_out_like_a_video_editor() -> None:
    sync_api = pytest.importorskip("playwright.sync_api", reason="playwright not installed")
    try:
        playwright = sync_api.sync_playwright().start()
    except Exception as exc:  # pragma: no cover
        pytest.skip(f"playwright could not start: {exc}")
    browser = None
    try:
        try:
            browser, page = _open_editor(playwright)
        except Exception as exc:  # pragma: no cover
            pytest.skip(f"Chromium not available: {exc}")
        with _served_app() as base_url:
            _load_project(page, base_url)
            boxes = page.evaluate(RATIOS_JS)

        preview = boxes["preview"]
        timeline = boxes["timeline"]
        inspector = boxes["inspector"]

        for name in ("preview", "timeline", "inspector"):
            assert boxes[name]["w"] > 100, (name, boxes[name])
            assert boxes[name]["h"] > 60, (name, boxes[name])

        # preview on the left, inspector docked to its right
        assert preview["x"] < inspector["x"]
        assert preview["x"] + preview["w"] <= inspector["x"] + 1

        # timeline underneath both of them, spanning the full shell width
        lowest = max(preview["y"] + preview["h"], inspector["y"] + inspector["h"])
        assert timeline["y"] >= lowest - 1, (timeline, preview, inspector)
        assert timeline["w"] >= preview["w"] + inspector["w"] - 1
    finally:
        if browser is not None:
            browser.close()
        playwright.stop()


@pytest.mark.render
def test_editor_shows_time_as_frame_over_fps() -> None:
    sync_api = pytest.importorskip("playwright.sync_api", reason="playwright not installed")
    try:
        playwright = sync_api.sync_playwright().start()
    except Exception as exc:  # pragma: no cover
        pytest.skip(f"playwright could not start: {exc}")
    browser = None
    try:
        try:
            browser, page = _open_editor(playwright)
        except Exception as exc:  # pragma: no cover
            pytest.skip(f"Chromium not available: {exc}")
        with _served_app() as base_url:
            _load_project(page, base_url)

            page.fill("#editor-frame", "20")
            page.click("#editor-scrub-btn")
            page.wait_for_function(
                "() => document.getElementById('editor-frame-meta').textContent === '20'",
                timeout=25000,
            )
            # examples/code-explainer/project.json is 30 fps: 20/30 = 0.667
            assert page.locator("#editor-time-meta").inner_text() == "t = 0.667 s"
    finally:
        if browser is not None:
            browser.close()
        playwright.stop()


@pytest.mark.render
def test_editor_rapid_scrub_keeps_the_last_frame() -> None:
    sync_api = pytest.importorskip("playwright.sync_api", reason="playwright not installed")
    try:
        playwright = sync_api.sync_playwright().start()
    except Exception as exc:  # pragma: no cover
        pytest.skip(f"playwright could not start: {exc}")
    browser = None
    try:
        try:
            browser, page = _open_editor(playwright)
        except Exception as exc:  # pragma: no cover
            pytest.skip(f"Chromium not available: {exc}")
        with _served_app() as base_url:
            _load_project(page, base_url)

            # Fire and forget: no await, no debounce. Only the last frame may win.
            page.evaluate(
                "() => { [5, 15, 25, 45, 30, 80, 20].forEach((f) => { seekEditorFrame(f); }); }"
            )
            page.wait_for_function(
                "() => document.getElementById('editor-frame-meta').textContent === '20'",
                timeout=25000,
            )
            settled = page.get_attribute("#editor-preview", "src")
            page.wait_for_timeout(1500)
            assert page.locator("#editor-frame-meta").inner_text() == "20"
            assert page.get_attribute("#editor-preview", "src") == settled, (
                "an older preview landed after the newest one"
            )
    finally:
        if browser is not None:
            browser.close()
        playwright.stop()


