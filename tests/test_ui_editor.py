"""Phase 2 editor shell: structural contract and browser scrub behaviour."""

from __future__ import annotations

import contextlib
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


def test_ui_contains_editor_shell_contract() -> None:
    with TestClient(create_app()) as client:
        response = client.get("/ui")

    assert response.status_code == 200
    html = response.text
    for token in (
        'data-panel="editor"',
        'id="editor-panel"',
        'id="editor-project-path"',
        'id="editor-load-btn"',
        'id="editor-preview"',
        'id="editor-frame"',
        'id="editor-scrub"',
        'id="editor-save-btn"',
        'function loadEditorProject',
        'function seekEditorFrame',
        "/api/v1/preview/frame",
        "/api/v1/projects/get",
        "/api/v1/projects/save",
    ):
        assert token in html, token


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


@pytest.mark.render
def test_editor_scrub_changes_preview_frame() -> None:
    sync_api = pytest.importorskip("playwright.sync_api", reason="playwright not installed")
    try:
        playwright = sync_api.sync_playwright().start()
    except Exception as exc:  # pragma: no cover
        pytest.skip(f"playwright could not start: {exc}")
    try:
        try:
            browser = playwright.chromium.launch(headless=True)
        except Exception as exc:  # pragma: no cover
            pytest.skip(f"Chromium not available: {exc}")
        try:
            with _served_app() as base:
                page = browser.new_page()
                page.goto(f"{base}/ui")
                page.click('[data-panel="editor"]')
                assert page.locator("#editor-panel").is_visible()

                page.fill("#editor-project-path", str(PROJECT))
                page.click("#editor-load-btn")
                page.wait_for_function(
                    "() => { const i = document.getElementById('editor-preview'); "
                    "return i && i.src.startsWith('data:image/png'); }",
                    timeout=20000,
                )
                first = page.get_attribute("#editor-preview", "src")

                page.fill("#editor-frame", "20")
                page.click("#editor-scrub-btn")
                page.wait_for_function(
                    "(prev) => document.getElementById('editor-preview').src !== prev",
                    arg=first,
                    timeout=20000,
                )
                assert page.locator("#editor-frame-meta").inner_text() == "20"
        finally:
            browser.close()
    finally:
        playwright.stop()
