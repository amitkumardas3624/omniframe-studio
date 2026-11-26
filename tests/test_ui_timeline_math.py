"""Phase 3 timing maths: px<->frame, edge snap, collision-free placement, trim.

The pure functions live in the served inline script and are unit-tested by
calling them inside the browser (no DOM wiring involved). The integer frame
is the source of truth everywhere; px are only a zoomed view.
"""

from __future__ import annotations

import contextlib
import socket
import threading
import time

import pytest

pytest.importorskip("fastapi")

from omniframe.backend.server import create_app  # noqa: E402


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
def _math():
    sync_api = pytest.importorskip("playwright.sync_api", reason="playwright not installed")
    try:
        playwright = sync_api.sync_playwright().start()
        browser = playwright.chromium.launch(headless=True)
    except Exception as exc:  # pragma: no cover - environment dependent
        pytest.fail(f"browser unavailable for timing-math tests: {exc}")
    try:
        with _served_app() as base_url:
            page = browser.new_page()
            page.goto(base_url + "/ui")
            ok = page.evaluate("typeof window.editorPxToFrame === 'function'")
            if not ok:
                pytest.fail("editor math functions not present on the served page")

            yield page
    finally:
        browser.close()
        playwright.stop()


def test_frame_px_roundtrip(_math) -> None:
    page = _math
    assert _call(page, "editorFrameToPx(10)") == 10 * 6 + 112
    assert _call(page, "editorPxToFrame(172)") == 10
    assert _call(page, "editorPxToFrame(editorFrameToPx(10))") == 10


def test_frame_px_clamps_to_range(_math) -> None:
    page = _math
    assert _call(page, "editorPxToFrame(0)") == 0
    assert _call(page, "editorPxToFrame(1)") == 0


def test_snap_nearest_target(_math) -> None:
    page = _math
    assert _call(page, "editorSnapEdges(6, [5])") == 5
    assert _call(page, "editorSnapEdges(9, [5])") == 9
    assert _call(page, "editorSnapEdges(10, [5, 12])") == 12
    assert _call(page, "editorSnapEdges(4, [])") == 4


def test_placement_keeps_duration_and_bounds(_math) -> None:
    page = _math
    assert _call(page, "JSON.stringify(editorPlacement(3, 10, [], 90))") == '{"start":3,"duration":10}'
    assert _call(page, "JSON.stringify(editorPlacement(88, 10, [], 90))") == '{"start":80,"duration":10}'
    assert _call(page, "JSON.stringify(editorPlacement(-5, 10, [], 90))") == '{"start":0,"duration":10}'


def test_placement_avoids_overlap(_math) -> None:
    page = _math
    assert _call(page, "JSON.stringify(editorPlacement(55, 10, [{start:50,end:60}], 90))") == '{"start":60,"duration":10}'
    assert _call(page, "JSON.stringify(editorPlacement(45, 10, [{start:50,end:60}], 90))") == '{"start":40,"duration":10}'


def test_placement_snaps_to_sibling_edge(_math) -> None:
    page = _math
    assert _call(page, "JSON.stringify(editorPlacement(38, 10, [{start:30,end:45}], 90))") == '{"start":45,"duration":10}'


def test_trim_keeps_opposite_edge_pinned(_math) -> None:
    page = _math
    assert _call(page, "JSON.stringify(editorTrim(2, 10, \'out\', 20, [], 90))") == '{"start":2,"duration":18}'
    assert _call(page, "JSON.stringify(editorTrim(2, 10, \'in\', 5, [], 90))") == '{"start":5,"duration":7}'


def test_trim_clamps_to_bounds(_math) -> None:
    page = _math
    assert _call(page, "JSON.stringify(editorTrim(80, 2, \'out\', 100, [], 90))") == '{"start":80,"duration":10}'

def test_trim_out_stops_at_a_right_sibling(_math) -> None:
    page = _math
    # [2,12) trim-out into a sibling [15,20): end clamps to 15, not past it.
    assert _call(page, "JSON.stringify(editorTrim(2, 10, \'out\', 30, [{start:15,end:20}], 90))") == '{"start":2,"duration":13}'


def test_trim_in_stops_at_a_left_sibling(_math) -> None:
    page = _math
    # [10,20) trim-in before a sibling [0,4): start clamps to 4, not into it.
    assert _call(page, "JSON.stringify(editorTrim(10, 10, \'in\', 1, [{start:0,end:4}], 90))") == '{"start":4,"duration":16}'


def test_placement_respects_several_siblings(_math) -> None:
    page = _math
    # Gap between [0,5) and [10,15), duration 2, requested 6 -> flush after 5.
    assert _call(page, "JSON.stringify(editorPlacement(6, 2, [{start:0,end:5},{start:10,end:15}], 90))") == '{"start":5,"duration":2}'

