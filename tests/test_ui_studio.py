"""Phase 6 studio UI: Remotion-like player, properties and variables.

The panel is checked the way a person uses it: the markup has to carry the
player controls, the inspector has to be tabbed into props and variables,
and the browser has to actually step a frame, paint a pair of rows and
round-trip a project variable.
"""

from __future__ import annotations

import contextlib
import shutil
import socket
import threading
import time
from pathlib import Path

import pytest

pytest.importorskip("fastapi")

from omniframe.backend.server import create_app  # noqa: E402

REQUIRED = [
    "editorStepFrame",
    "editorJumpTo",
    "editorTogglePlay",
    "editorStopPlay",
    "editorSelectTab",
    "editorRenderPropRows",
    "editorRenderVariableRows",
    "editorApplyPropRows",
    "editorApplyVariables",
    "editorPlayerReadout",
    "editorTimecode",
    "editorHandleKey",
]

PLAYER_IDS = [
    "editor-jump-start",
    "editor-prev-frame",
    "editor-play-btn",
    "editor-next-frame",
    "editor-jump-end",
    "editor-frame",
    "editor-frame-total",
    "editor-timecode",
    "editor-zoom-mode",
    "editor-rate",
    "editor-loop",
    "editor-inout-readout",
]

PANE_IDS = [
    "editor-tab-props",
    "editor-tab-variables",
    "editor-tab-project",
    "editor-pane-props",
    "editor-pane-variables",
    "editor-pane-project",
    "editor-props-rows",
    "editor-variable-rows",
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


def _project(tmp_path: Path) -> Path:
    source = (
        Path(__file__).resolve().parents[1] / "examples" / "code-explainer" / "project.json"
    )
    target = tmp_path / "project.json"
    shutil.copyfile(source, target)
    return target


@pytest.fixture(scope="module")
def _studio():
    sync_api = pytest.importorskip("playwright.sync_api", reason="playwright not installed")
    try:
        playwright = sync_api.sync_playwright().start()
        browser = playwright.chromium.launch(headless=True)
    except Exception as exc:  # pragma: no cover - environment dependent
        pytest.fail(f"browser unavailable for studio-ui tests: {exc}")
    try:
        with _served_app() as base_url:
            page = browser.new_page()
            page.goto(base_url + "/ui")
            missing = [
                name for name in REQUIRED
                if not page.evaluate("typeof window." + name + " === 'function'")
            ]
            if missing:
                pytest.fail("studio functions not present: " + ", ".join(missing))
            yield page
    finally:
        browser.close()
        playwright.stop()


def test_markup_carries_the_player_controls(_studio) -> None:
    page = _studio
    for element_id in PLAYER_IDS:
        assert page.query_selector("#" + element_id) is not None, element_id


def test_inspector_is_tabbed_into_props_and_variables(_studio) -> None:
    page = _studio
    for element_id in PANE_IDS:
        assert page.query_selector("#" + element_id) is not None, element_id
    selected = page.eval_on_selector_all(
        ".studio-tab[aria-selected='true']", "els => els.map(e => e.id)"
    )
    assert selected == ["editor-tab-props"], selected


def test_tabs_switch_the_visible_pane(_studio) -> None:
    page = _studio
    page.click('[data-panel="editor"]')
    page.click("#editor-tab-variables")
    assert page.is_visible("#editor-pane-variables")
    assert not page.is_visible("#editor-pane-props")
    page.click("#editor-tab-props")
    assert page.is_visible("#editor-pane-props")
    assert not page.is_visible("#editor-pane-variables")


def test_stepping_a_frame_moves_the_preview(_studio, tmp_path: Path) -> None:
    page = _studio
    page.click('[data-panel="editor"]')
    page.fill("#editor-project-path", str(_project(tmp_path)))
    page.click("#editor-load-btn")
    page.wait_for_function(
        "() => document.getElementById('editor-frame-meta').textContent !== 'No project loaded'",
        timeout=30000,
    )
    page.click("#editor-next-frame")
    page.wait_for_function(
        "() => document.getElementById('editor-frame').value === '1'",
        timeout=30000,
    )
    assert page.text_content("#editor-timecode") == "00:00.03"


def test_props_rows_round_trip_through_the_dom(_studio, tmp_path: Path) -> None:
    page = _studio
    page.click('[data-panel="editor"]')
    page.fill("#editor-project-path", str(_project(tmp_path)))
    page.click("#editor-load-btn")
    page.wait_for_function(
        "() => document.getElementById('editor-frame-meta').textContent !== 'No project loaded'",
        timeout=30000,
    )
    result = page.evaluate("""() => {
        const track = editorProject.tracks.find(function (t) {
            return (t.clips || []).some(function (c) { return c.code; });
        });
        if (!track) return { ok: false, why: "no code clip in this project" };
        const clip = track.clips.find(function (c) { return c.code; });
        clip.code = clip.code || {};
        clip.code.params = { title: "Hello" };
        editorSelection = { trackId: track.id, clipId: clip.id };
        editorRenderPropRows();
        const host = document.getElementById("editor-props-rows");
        const rows = host.querySelectorAll(".studio-prop-row").length;
        const inputs = host.querySelector(".studio-prop-row").querySelectorAll("input");
        inputs[1].value = "changed";
        editorApplyPropRows();
        return { ok: true, rows: rows, params: clip.code.params };
    }""")
    assert result["ok"] is True, result
    assert result["rows"] == 1, result
    assert result["params"] == {"title": "changed"}, result


def test_variables_are_edited_and_persisted(_studio, tmp_path: Path) -> None:
    page = _studio
    project = _project(tmp_path)
    page.click('[data-panel="editor"]')
    page.fill("#editor-project-path", str(project))
    page.click("#editor-load-btn")
    page.wait_for_function(
        "() => document.getElementById('editor-frame-meta').textContent !== 'No project loaded'",
        timeout=30000,
    )
    page.click("#editor-tab-variables")
    page.click("#editor-variables-add")
    page.evaluate("""() => {
        const host = document.getElementById("editor-variable-rows");
        const inputs = host.querySelector(".studio-prop-row").querySelectorAll("input");
        inputs[0].value = "brand";
        inputs[1].value = "OmniFrame";
        editorApplyVariables();
    }""")
    variables = page.evaluate("() => editorProject.metadata.variables")
    assert variables == {"brand": "OmniFrame"}, variables

    page.evaluate("() => saveEditorProject()")
    page.wait_for_timeout(1200)
    saved = page.evaluate("""async (path) => {
        const response = await fetch("/api/v1/projects/get", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ project_path: path }),
        });
        const payload = await response.json();
        return payload.result.project.metadata.variables;
    }""", str(project))
    assert saved == {"brand": "OmniFrame"}, saved
