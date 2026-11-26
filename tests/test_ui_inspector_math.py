"""Phase 4 inspector maths: selection, timing fields, params JSON, assets rows.

The pure functions live in the served inline script and are unit-tested by
calling them inside the browser (no DOM wiring involved), exactly like the
Phase 3 timing-math suite. A missing required function fails via pytest.fail;
only genuine Playwright/Chromium unavailability skips.
"""

from __future__ import annotations

import contextlib
import socket
import threading
import time

import pytest

pytest.importorskip("fastapi")

from omniframe.backend.server import create_app  # noqa: E402

REQUIRED = [
    "editorSelectedClip",
    "editorTimingFields",
    "editorParseParamsJson",
    "editorApplyParams",
    "editorCompositionKeys",
    "editorAssetsRows",
    "editorValidateIssues",
]


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


def _call(page, expr):
    return page.evaluate(expr)


@pytest.fixture(scope="module")
def _inspector():
    sync_api = pytest.importorskip("playwright.sync_api", reason="playwright not installed")
    try:
        playwright = sync_api.sync_playwright().start()
        browser = playwright.chromium.launch(headless=True)
    except Exception as exc:  # pragma: no cover - environment dependent
        pytest.fail(f"browser unavailable for inspector-math tests: {exc}")
    try:
        with _served_app() as base_url:
            page = browser.new_page()
            page.goto(base_url + "/ui")
            missing = [
                name for name in REQUIRED
                if not page.evaluate("typeof window." + name + " === 'function'")
            ]
            if missing:
                pytest.fail("inspector functions not present on the served page: " + ", ".join(missing))
            yield page
    finally:
        browser.close()
        playwright.stop()


def test_selection_resolves_none_without_project(_inspector) -> None:
    page = _inspector
    assert _call(page, "editorSelectedClip()") is None


def test_selection_resolves_clip_from_project(_inspector) -> None:
    page = _inspector
    _call(page, "editorProject = {tracks: [{id: 't1', clips: [{id: 'c1', start_frame: 4, duration_frames: 9, code: {params: {}}}]}]}; editorSelection = {trackId: 't1', clipId: 'c1'};")
    clip = _call(page, "editorSelectedClip()")
    assert clip is not None
    assert clip["id"] == "c1"


def test_timing_fields(_inspector) -> None:
    assert _call(_inspector, "editorTimingFields({start_frame: 4, duration_frames: 9})") == {
        "start_frame": 4, "duration_frames": 9,
    }


def test_parse_params_valid_object(_inspector) -> None:
    result = _call(_inspector, "editorParseParamsJson('{\"title\": \"Go\"}')")
    assert result["ok"] is True
    assert result["params"]["title"] == "Go"


def test_parse_params_rejects_bad_json(_inspector) -> None:
    result = _call(_inspector, "editorParseParamsJson('not json')")
    assert result["ok"] is False
    assert "error" in result and result["error"]


def test_parse_params_rejects_non_object(_inspector) -> None:
    result = _call(_inspector, "editorParseParamsJson('[1, 2]')")
    assert result["ok"] is False


def test_apply_params_writes_and_rejected_invalid(_inspector) -> None:
    page = _inspector
    clip = _call(page, "var c = {code: {params: {}}}; window.__c = c; editorApplyParams(c, '{\"x\": 1}'); c.code.params")
    assert clip["x"] == 1
    _call(page, "window.__c.code.params = {};")
    err = _call(page, "editorApplyParams(window.__c, 'nope')")
    assert err["ok"] is False


def test_composition_keys_from_html(_inspector) -> None:
    html = '<div data-composition-variables="{\"title\": \"T\", \"speed\": 2}"></div>'
    keys = _call(_inspector, "editorCompositionKeys(" + __import__("json").dumps(html) + ")")
    assert keys == ["title", "speed"]


def test_assets_rows(_inspector) -> None:
    rows = _call(
        _inspector,
        "editorAssetsRows({assets: [{id: 'a1', kind: 'font', path: 'f.ttf'}, {id: 'a2', kind: 'video', path: 'v.mp4'}]})",
    )
    assert rows == [
        {"id": "a1", "kind": "font", "path": "f.ttf"},
        {"id": "a2", "kind": "video", "path": "v.mp4"},
    ]


def test_validate_issues_filters_errors(_inspector) -> None:
    issues = [
        {"severity": "error", "code": "E_CLIP_OVERLAP", "message": "boom"},
        {"severity": "warning", "code": "W_ODD_DIMENSIONS", "message": "odd"},
    ]
    lines = _call(_inspector, "editorValidateIssues(" + __import__("json").dumps(issues) + ")")
    assert lines == ["E_CLIP_OVERLAP: boom"]
