"""Phase 5 compare-gate maths: frame parsing, verdict rules, pair markup.

The pure functions live in the served inline script and are unit-tested by
calling them inside the browser (no DOM wiring involved), exactly like the
Phase 3 timing-math and Phase 4 inspector suites. A missing required function
or missing panel element fails via pytest.fail; only genuine
Playwright/Chromium unavailability skips.

The verdict parity checks at the end compare the browser answer with the
Python one from omniframe.engines.compositor.compare, so the panel cannot
drift from the gate the backend actually applies.
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
    "editorParseFrameList",
    "editorCompareVerdict",
    "editorCompareDiffText",
    "editorComparePairModel",
    "updateCompareVerdict",
    "runCompare",
    "writeCompareReport",
]

#: Panel hooks the markup must carry for the panel to be usable at all.
PANEL_IDS = (
    "compare-panel",
    "compare-content",
    "compare-project-path",
    "compare-frames",
    "compare-reference-video",
    "compare-reference-dir",
    "compare-backend",
    "compare-run",
    "compare-write",
    "compare-status",
    "compare-error",
    "compare-verdict",
    "compare-checklist",
    "compare-pairs",
    "compare-report-status",
)


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


@pytest.fixture(scope="module")
def _compare():
    sync_api = pytest.importorskip("playwright.sync_api", reason="playwright not installed")
    try:
        playwright = sync_api.sync_playwright().start()
        browser = playwright.chromium.launch(headless=True)
    except Exception as exc:  # pragma: no cover - environment dependent
        pytest.fail(f"browser unavailable for compare-math tests: {exc}")
    try:
        with _served_app() as base_url:
            page = browser.new_page()
            page.goto(base_url + "/ui")
            missing = [
                name for name in REQUIRED
                if not page.evaluate("typeof window." + name + " === 'function'")
            ]
            if missing:
                pytest.fail("compare functions not present: " + ", ".join(missing))
            absent = [
                pid for pid in PANEL_IDS
                if page.query_selector("#" + pid) is None
            ]
            if absent:
                pytest.fail("compare panel hooks missing: " + ", ".join(absent))
            yield page
    finally:
        browser.close()
        playwright.stop()


def _ev(page, expr):
    return page.evaluate(expr)


def _rows(status, note=""):
    return [{"id": m, "status": status, "note": note} for m in MECHANICS]


def _verdict(page, rows):
    return page.evaluate("(rows) => editorCompareVerdict(rows)", rows)


MECHANICS = [
    "background_shifts",
    "grid_density",
    "particle_construction",
    "3d_focal_objects",
    "outro_hierarchy",
]


def test_frame_list_parses_sorts_and_dedupes(_compare):
    result = _ev(_compare, "editorParseFrameList('9, 3,3', 20)")
    assert result["ok"] is True
    assert result["frames"] == [3, 9]


def test_frame_list_accepts_space_separated(_compare):
    result = _ev(_compare, "editorParseFrameList('4 8 15', 20)")
    assert result["ok"] is True
    assert result["frames"] == [4, 8, 15]


def test_frame_list_rejects_empty_double_comma_and_words(_compare):
    for expression in (
        "editorParseFrameList('', 20)",
        "editorParseFrameList('   ', 20)",
        "editorParseFrameList('1,,2', 20)",
        "editorParseFrameList('1,two', 20)",
        "editorParseFrameList('1.5', 20)",
        "editorParseFrameList('-1', 20)",
    ):
        result = _ev(_compare, expression)
        assert result["ok"] is False, expression
        assert result["error"], expression


def test_frame_list_rejects_out_of_range(_compare):
    result = _ev(_compare, "editorParseFrameList('0,90', 90)")
    assert result["ok"] is False
    assert "90" in result["error"]


def test_verdict_pending_when_nothing_attested(_compare):
    result = _verdict(_compare, [])
    assert result["ok"] is False
    assert result["pending"] == MECHANICS


def test_verdict_passes_when_every_mechanic_matches(_compare):
    result = _verdict(_compare, _rows("match"))
    assert result["ok"] is True
    assert result["pending"] == []
    assert result["gaps"] == []
    assert result["limits_without_note"] == []


def test_verdict_treats_unchecked_as_pending(_compare):
    rows = _rows("match")
    rows[0]["status"] = "unchecked"
    result = _verdict(_compare, rows)
    assert result["ok"] is False
    assert result["pending"] == [MECHANICS[0]]


def test_verdict_lists_gaps(_compare):
    rows = _rows("match")
    rows[1]["status"] = "gap"
    result = _verdict(_compare, rows)
    assert result["ok"] is False
    assert result["gaps"] == [MECHANICS[1]]


def test_verdict_fails_limit_without_note(_compare):
    rows = _rows("match")
    rows[2]["status"] = "limit"
    rows[2]["note"] = "   "
    result = _verdict(_compare, rows)
    assert result["ok"] is False
    assert result["limits_without_note"] == [MECHANICS[2]]


def test_verdict_accepts_noted_limit(_compare):
    rows = _rows("match")
    rows[2]["status"] = "limit"
    rows[2]["note"] = "no bundled font files"
    assert _verdict(_compare, rows)["ok"] is True


def test_verdict_ignores_unknown_rows(_compare):
    rows = _rows("match") + [{"id": "not_a_mechanic", "status": "match", "note": ""}]
    assert _verdict(_compare, rows)["ok"] is True


def test_diff_text_formats(_compare):
    assert _ev(_compare, "editorCompareDiffText(null)") == "n/a"
    assert _ev(_compare, "editorCompareDiffText(undefined)") == "n/a"
    assert _ev(_compare, "editorCompareDiffText(0)") == "0.00"
    assert _ev(_compare, "editorCompareDiffText(12.345678)") == "12.35"


def test_pair_model_shows_both_frames_and_diff(_compare):
    model = _ev(
        _compare,
        "editorComparePairModel({frame: 12, diff: 3.5, current: 'AAAA', reference: 'BBBB'})",
    )
    assert model["frame"] == 12
    assert model["diff"] == "3.50"
    assert model["referenceSrc"] == "data:image/png;base64,BBBB"
    assert model["currentSrc"] == "data:image/png;base64,AAAA"


def test_pair_model_marks_missing_reference(_compare):
    model = _ev(_compare, "editorComparePairModel({frame: 7, current: 'AAAA'})")
    assert model["referenceSrc"] == ""
    assert model["diff"] == "n/a"


def test_checklist_renders_native_controls(_compare):
    rows = [{"id": m, "label": m, "status": "unchecked", "note": ""} for m in MECHANICS]
    counts = _compare.evaluate(
        "(rows) => {"
        " renderCompareChecklist(rows);"
        " var host = document.getElementById('compare-checklist');"
        " return {"
        "   selects: host.querySelectorAll('select[data-mechanic]').length,"
        "   notes: host.querySelectorAll('input[data-note]').length,"
        " };"
        " }",
        rows,
    )
    assert counts["selects"] == len(MECHANICS)
    assert counts["notes"] == len(MECHANICS)


def test_checklist_round_trips_through_the_dom(_compare):
    rows = [{"id": m, "label": m, "status": "match", "note": ""} for m in MECHANICS]
    rows[4]["status"] = "limit"
    rows[4]["note"] = "no bundled font files"
    asserted = _compare.evaluate(
        "(rows) => {"
        " renderCompareChecklist(rows);"
        " return compareAttestedRows();"
        " }",
        rows,
    )
    assert [row["id"] for row in asserted] == MECHANICS
    assert asserted[4]["status"] == "limit"
    assert asserted[4]["note"] == "no bundled font files"


def test_panel_markup_is_wired(_compare):
    labelled = _ev(_compare, "document.getElementById('compare-panel').getAttribute('aria-labelledby')")
    assert labelled == "compare-panel-title"
    assert _ev(_compare, "!!document.querySelector('a.nav-link[data-panel=compare]')")
    assert _ev(_compare, "document.getElementById('compare-run').getAttribute('type')") == "button"
    assert _ev(_compare, "document.getElementById('compare-write').getAttribute('type')") == "button"
    options = _ev(
        _compare,
        "Array.from(document.getElementById('compare-backend').options)"
        ".map(function (o) { return o.value; }).join(',')",
    )
    assert options == "stub,playwright,auto"


def test_checklist_html_carries_every_mechanic(_compare):
    rows = [{"id": m, "label": m, "status": "unchecked", "note": ""} for m in MECHANICS]
    html = _compare.evaluate("(rows) => { renderCompareChecklist(rows); return document.getElementById('compare-checklist').innerHTML; }", rows)
    for mechanic in MECHANICS:
        assert mechanic in html


def test_mechanics_match_backend_checklist(_compare):
    from omniframe.engines.compositor.compare import CHECKLIST

    assert _ev(_compare, "window.COMPARE_MECHANICS") == [item.id for item in CHECKLIST]


def test_frame_parsing_agrees_with_backend(_compare):
    from omniframe.core.errors import ValidationError
    from omniframe.engines.compositor.compare import parse_frames

    for text in ("0, 120", "5 6 7", "1,,2", "", "abc", "900"):
        try:
            expected = parse_frames(text, 900)
            parsed_ok = True
        except ValidationError:
            parsed_ok = False
            expected = None
        result = _compare.evaluate("(t) => editorParseFrameList(t, 900)", text)
        assert result["ok"] is parsed_ok, text
        if parsed_ok:
            assert result["frames"] == expected, text


def test_verdict_agrees_with_backend(_compare):
    from omniframe.engines.compositor.compare import CHECKLIST
    from omniframe.engines.compositor.compare import verdict as backend_verdict

    rows = [item.to_dict() for item in CHECKLIST]
    assert _verdict(_compare, rows) == backend_verdict(rows)
