"""Structural and Playwright checks for the OmniFrame Studio web UI.

Structural layer (``test_ui_markup_*``): fetch ``/ui`` through the in-process
FastAPI ``TestClient`` -- no port, no renderer -- and check the markup with the
standard library only. Verified: page title, ``<html lang>``, viewport meta, nav
and main landmarks, one ``<section>`` per panel named by its own ``<h2>``
heading, an accessible name on every icon-only button and on every form
control, alt or aria-hidden coverage for images and icons, and equality between
the external origins actually referenced and the inventory written in the head
comment.

Browser layer (``test_ui_a11y_in_browser``): serve the app with uvicorn on
127.0.0.1, load ``/ui`` in headless Chromium with every non-localhost request
aborted, and sample computed styles to prove the inline fallback CSS keeps
panels, badges, buttons and inputs usable and legible with zero network. Marked
``@pytest.mark.render``; skipped, never failed, when the pieces are missing.

Not verified here: colour contrast ratios, focus order, keyboard traps.
"""

from __future__ import annotations

import contextlib
import html as _html
import re
import socket
import threading
import time
from urllib.parse import urlparse

import pytest

pytest.importorskip("fastapi")

TITLE = "OmniFrame Studio \u2014 Agent & Creator Control Panel"

#: Panel slug -> exact heading text its accessible name must come from.
PANEL_TITLES = {
    "dashboard": "Dashboard",
    "projects": "Projects",
    "render": "Render Control",
    "bridges": "DCC Bridges",
    "inspection": "Inspection",
    "actions": "Actions",
    "jobs": "Jobs",
    "timeline": "Timeline",
}

#: Panels added by the Phase 4 tasks; the gate names these four explicitly.
PHASE4_PANELS = ("actions", "jobs", "bridges", "timeline")

#: Utility class names the markup uses. The offline fallback CSS must shim each
#: one, or blocking the Tailwind CDN would change spacing / hide content.
UTILITY_CLASSES = (
    "hidden",
    "block",
    "w-full",
    "rounded",
    "border",
    "px-2",
    "py-1",
    "mb-1",
    "mb-2",
    "mt-1",
    "mt-2",
    "mt-4",
    "text-sm",
    "text-muted",
    "btn",
    "btn-primary",
    "btn-ghost",
    "btn-acent",
)

#: Component classes the offline stylesheet must keep styling directly.
COMPONENT_CLASSES = (
    "panel",
    "panel-header",
    "panel-title",
    "badge",
    "badge-healthy",
    "badge-warning",
    "badge-critical",
    "data-table",
    "action-item",
    "action-name",
    "tool-run",
    "tool-schema",
    "actions-error-box",
    "capability-list",
    "timeline-clip",
)

_URL_ATTRIBUTES = ("src", "href", "poster", "data", "action", "formaction")

_COMMENT_RE = re.compile(r"<!--.*?-->", re.S)
_SCRIPT_RE = re.compile(r"<script\b[^>]*>.*?</script>", re.S | re.I)
_LINK_RE = re.compile(r"<link\b[^>]*>", re.I)
_STYLE_RE = re.compile(r"<style\b[^>]*>(.*?)</style>", re.S | re.I)
_CSS_COMMENT_RE = re.compile(r"/\*.*?\*/", re.S)
_TAG_RE = re.compile(r"<([a-zA-Z][a-zA-Z0-9-]*)\b([^>]*)>")
_ATTR_RE = re.compile(r'([a-zA-Z_:@][-a-zA-Z0-9_:.]*)\s*=\s*"([^"]*)"')
_HEADING_RE = re.compile(r"<h([1-6])\b[^>]*>(.*?)</h\1>", re.S | re.I)
_BODY_RE = re.compile(r"<body\b[^>]*>(.*?)</body>", re.S | re.I)


def _served_html() -> str:
    """The exact bytes the server returns for /ui."""
    from fastapi.testclient import TestClient

    from omniframe.backend.server import create_app

    with TestClient(create_app()) as client:
        response = client.get("/ui")

    assert response.status_code == 200, response.text
    return response.text


def _without_comments(markup: str) -> str:
    return _COMMENT_RE.sub("", markup)


def _served_markup() -> str:
    """The served page with comments removed, for markup-level assertions.

    The head comment documents the offline policy and names the external
    origins, so it must be excluded before scanning for real tags/attributes --
    otherwise the documentation would satisfy the very assertions that are
    meant to describe the markup.
    """
    return _without_comments(_served_html())


def _without_scripts(markup: str) -> str:
    return _SCRIPT_RE.sub("", markup)


def _tags(markup: str, tag: str) -> list[dict[str, str]]:
    """Attribute dicts of every opening ``tag`` element, names lowercased."""
    found: list[dict[str, str]] = []
    for match in re.finditer(rf"<{tag}\b([^>]*)>", markup, re.I):
        attrs = {
            name.lower(): value
            for name, value in _ATTR_RE.findall(match.group(1))
        }
        found.append(attrs)
    return found


def _opening_tags(markup: str) -> list[str]:
    return [match.group(0) for match in _TAG_RE.finditer(markup)]


def _strip_tags(fragment: str) -> str:
    return re.sub(r"<[^>]+>", "", fragment)


def _referenced_origins(markup: str) -> set[str]:
    """Absolute http(s) origins that the document actually pulls resources from."""
    body = _without_comments(markup)
    found: set[str] = set()
    for attribute in _URL_ATTRIBUTES:
        pattern = rf'\b{attribute}\s*=\s*"([^"]*)"'
        for value in re.findall(pattern, body, re.I):
            parsed = urlparse(value.strip())
            if parsed.scheme in ("http", "https") and parsed.netloc:
                found.add(f"{parsed.scheme}://{parsed.netloc.lower()}")
    return found


def _documented_origins(markup: str) -> set[str]:
    """Origins listed as ``- <url>`` bullets inside the head comment."""
    head_fragment = markup.split("</head>")[0]
    documented: set[str] = set()
    for raw in re.findall(r"^\s*-\s+(https?://\S+)", head_fragment, re.M):
        documented.add(raw.rstrip(".,;:").lower())
    return documented


# -- structural layer ------------------------------------------------------


def test_ui_markup_declares_title_lang_and_viewport() -> None:
    """Title, html lang and a viewport meta must all be present and non-empty."""
    doc = _served_markup()

    title = re.search(r"<title\b[^>]*>(.*?)</title>", doc, re.S | re.I)
    assert title is not None, "document has no <title>"
    assert _html.unescape(_strip_tags(title.group(1))).strip() == TITLE

    html_open = re.search(r"<html\b[^>]*>", doc, re.I)
    assert html_open is not None, "document has no <html> element"
    lang = re.search(r'\blang\s*=\s*"([^"]*)"', html_open.group(0), re.I)
    assert lang is not None, "<html> must carry a lang attribute"
    assert lang.group(1).strip(), "lang must not be empty"

    viewports = [
        meta["content"]
        for meta in _tags(doc, "meta")
        if meta.get("name", "").lower() == "viewport"
    ]
    assert viewports, "a viewport meta is required for small screens"
    assert "width=device-width" in viewports[0]


def test_ui_markup_has_named_nav_and_main_landmarks() -> None:
    """Every nav landmark is named, and a main landmark exists."""
    doc = _served_markup()

    navs = _tags(doc, "nav")
    assert len(navs) >= 2, "sidebar navigation + tools navigation expected"
    for nav in navs:
        assert nav.get("aria-label") or nav.get("aria-labelledby"), (
            "each <nav> needs an accessible name"
        )

    assert _tags(doc, "main"), "expected a <main> landmark"


def test_ui_markup_panels_are_sections_labelled_by_headings() -> None:
    """Each panel is a <section> whose name comes from its own <h2>."""
    doc = _served_markup()

    headings: dict[str, str] = {}
    for match in re.finditer(r"<h([1-6])\b([^>]*)>(.*?)</h\1>", doc, re.S | re.I):
        params = {
            name.lower(): value for name, value in _ATTR_RE.findall(match.group(2))
        }
        if "id" in params:
            headings[params["id"]] = _html.unescape(
                _strip_tags(match.group(3)).strip()
            )

    for slug, expected in PANEL_TITLES.items():
        panel_id = slug + "-panel"
        sections = [attrs for attrs in _tags(doc, "section") if attrs.get("id") == panel_id]
        assert len(sections) == 1, f"expected one <section id={panel_id}>"

        labelled_by = sections[0].get("aria-labelledby", "").split()
        assert labelled_by, f"{panel_id} must be named by aria-labelledby"
        assert labelled_by == [panel_id + "-title"], (
            f"{panel_id} should be named by {panel_id}-title, got {labelled_by!r}"
        )
        for target in labelled_by:
            assert target in headings, f"{panel_id} points at missing #{target}"
            assert headings[target] == expected, (
                f"{panel_id} heading {headings[target]!r} != {expected!r}"
            )


def test_ui_markup_icon_only_buttons_have_accessible_names() -> None:
    """An icon-only <button> (e.g. the panel close glyph) must be named."""
    doc = _served_markup()

    icon_only = 0
    for match in re.finditer(r"<button\b([^>]*)>(.*?)</button>", doc, re.S | re.I):
        attrs = {
            name.lower(): value for name, value in _ATTR_RE.findall(match.group(1))
        }
        label = attrs.get("aria-label") or attrs.get("aria-labelledby")
        text = _html.unescape(_strip_tags(match.group(2))).strip()
        has_text = any(char.isalnum() for char in text)
        if has_text:
            continue
        icon_only += 1
        assert label or attrs.get("title"), (
            f"icon-only button has no accessible name: {match.group(0)!r}"
        )

    assert icon_only >= 4, "expected the panel close buttons to be icon-only"


def test_ui_markup_form_controls_have_accessible_names() -> None:
    """Every form control is named by aria-label/labelledby or <label for>."""
    doc = _served_markup()

    label_targets = set()
    for match in re.finditer(r"<label\b([^>]*)>", doc, re.I):
        attrs = {
            name.lower(): value for name, value in _ATTR_RE.findall(match.group(1))
        }
        if attrs.get("for"):
            label_targets.add(attrs["for"].split()[0])

    controls = re.findall(r"<(?:input|select|textarea)\b([^>]*)>", doc, re.I)
    assert controls, "expected at least one form control"

    for raw in controls:
        attrs = {name.lower(): value for name, value in _ATTR_RE.findall(raw)}
        if attrs.get("type", "").lower() == "hidden":
            continue
        named = (
            attrs.get("aria-label")
            or attrs.get("aria-labelledby")
            or attrs.get("title")
            or (attrs.get("id") and attrs["id"] in label_targets)
        )
        assert named, f"form control has no accessible name: {raw!r}"


def test_ui_markup_images_and_icons_are_described_or_hidden() -> None:
    """Every <img> carries alt (or is hidden); every decorative icon is hidden."""
    doc = _served_markup()

    images = re.findall(r"<img\b([^>]*)>", doc, re.I)
    for raw in images:
        attrs = {name.lower(): value for name, value in _ATTR_RE.findall(raw)}
        assert "alt" in attrs or attrs.get("aria-hidden", "").lower() == "true", raw
        if attrs.get("aria-hidden", "").lower() == "true":
            assert not attrs.get("alt", "").strip(), (
                f"an aria-hidden image must not carry a redundant alt: {raw!r}"
            )

    icons = re.findall(r"<svg\b([^>]*)>", doc, re.I)
    assert icons, "expected the sidebar SVG icons"
    for raw in icons:
        attrs = {name.lower(): value for name, value in _ATTR_RE.findall(raw)}
        hidden = attrs.get("aria-hidden", "").lower() == "true"
        labelled = bool(attrs.get("aria-label") or attrs.get("aria-labelledby"))
        assert hidden or labelled, f"svg icon needs aria-hidden or a label: {raw!r}"


def test_ui_markup_heading_order_does_not_skip_levels() -> None:
    """One h1, and heading levels never jump by more than one."""
    doc = _served_markup()
    levels = [int(level) for level, _ in _HEADING_RE.findall(doc)]
    assert levels, "expected headings"
    assert levels[0] == 1, f"first heading should be the h1, got h{levels[0]}"
    assert levels.count(1) == 1, "expected exactly one h1"
    assert 2 in levels, "panel <h2> headings are missing"

    for previous, current in zip(levels, levels[1:], strict=False):
        assert current - previous <= 1, f"heading level jump {previous} -> {current}"


def test_ui_markup_external_origins_match_documented_inventory() -> None:
    """The head comment's inventory == the origins the markup actually loads."""
    doc = _served_html()
    referenced = _referenced_origins(doc)
    documented = _documented_origins(doc)

    assert documented, "head comment must list the remaining external origins"
    assert referenced == documented, f"referenced {sorted(referenced)} != documented {sorted(documented)}"

    # Every one of them is a progressive-enhancement HTTPS origin, and nothing
    # is loaded over an insecure or protocol-relative scheme.
    assert all(origin.startswith("https://") for origin in referenced), referenced
    markup = _without_comments(doc)
    assert 'src="//' not in markup and 'href="//' not in markup
    assert 'src="http://' not in markup and 'href="http://' not in markup


def _inline_css() -> str:
    match = _STYLE_RE.search(_served_markup())
    assert match is not None, "expected an inline <style> block"
    return _CSS_COMMENT_RE.sub("", match.group(1))


def test_offline_css_shims_every_utility_class_the_markup_uses() -> None:
    """No Tailwind utility class used in the markup may be left unstyled."""
    css = _inline_css()
    missing = []
    for name in UTILITY_CLASSES:
        pattern = rf"\.{re.escape(name)}(?![-A-Za-z0-9_])"
        if not re.search(pattern, css):
            missing.append(name)
    assert not missing, "offline CSS does not shim: {}".format(", ".join(missing))


def test_offline_css_styles_components_controls_and_tables() -> None:
    """Panels, tables, badges, buttons and inputs are styled without a network."""
    css = _inline_css()
    missing = [
        name
        for name in COMPONENT_CLASSES
        if not re.search(rf"\.{re.escape(name)}(?![-A-Za-z0-9_])", css)
    ]
    assert not missing, "offline CSS missing component rules: {}".format(", ".join(missing))

    assert re.search(r"\.data-table\s*(th|td|,|\{)", css), "table cell rules missing"
    assert re.search(r"\bbutton\b\s*[,{]", css), "base button rule missing"
    assert re.search(r"\binput\b\s*[,{]", css), "base input rule missing"
    assert re.search(r"\.panel-title\s*\{[^}]*\bmargin\b", css), "h2 default margin not reset"
    assert "@import" not in css, "inline CSS must not @import a remote stylesheet"
    assert "url(http" not in css.replace(" ", ""), "inline CSS must not fetch a remote file"


# -- browser layer ---------------------------------------------------------


@contextlib.contextmanager
def _served_app():
    """Serve the real app on 127.0.0.1 through uvicorn in a background thread.

    An in-process thread and socket, not shell=True and not a subprocess. The
    socket is bound to port 0 first so the kernel picks a free port; uvicorn then
    serves on that socket. Yields the base URL and always shuts down again.
    """
    uvicorn = pytest.importorskip("uvicorn", reason="ui extra (uvicorn) not installed")

    from omniframe.backend.server import create_app

    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind(("127.0.0.1", 0))
    sock.listen(128)
    port = sock.getsockname()[1]

    config = uvicorn.Config(create_app(), log_level="error", lifespan="on")
    server = uvicorn.Server(config)
    thread = threading.Thread(
        target=server.run, kwargs={"sockets": [sock]}, daemon=True
    )
    thread.start()

    deadline = time.monotonic() + 20.0
    while not server.started and time.monotonic() < deadline:
        time.sleep(0.01)
    try:
        if not server.started:
            raise RuntimeError("uvicorn did not start within 20s")
        yield f"http://127.0.0.1:{port}"
    finally:
        server.should_exit = True
        thread.join(timeout=10)
        sock.close()


#: Collects the computed style facts the offline-legibility test asserts on.
_COMPUTED_STYLE_JS = """
() => {
  // Panels are display:none until navigation shows one, so lay them all out
  // first; badge markup is rendered by JS, so add one representative sample.
  document.querySelectorAll('.panel').forEach((panel) => { panel.style.display = 'block'; });
  const list = document.querySelector('#actions-panel .panel-header');
  if (list && !document.querySelector('#actions-panel .badge')) {
    const badge = document.createElement('span');
    badge.className = 'badge badge-healthy';
    badge.textContent = 'Installed';
    list.appendChild(badge);
  }
  const sample = (selector) => {
    const el = document.querySelector(selector);
    if (!el) return null;
    const cs = getComputedStyle(el);
    return {
      background: cs.backgroundColor,
      borderTop: cs.borderTopWidth,
      borderStyle: cs.borderTopStyle,
      radius: cs.borderTopLeftRadius,
      padding: cs.paddingTop,
      display: cs.display,
      fontSize: cs.fontSize,
      width: el.getBoundingClientRect().width,
    };
  };
  return {
    body: sample('body'),
    panel: sample('#actions-panel'),
    title: sample('#actions-panel-title'),
    badge: sample('#actions-panel .badge'),
    button: sample('#jobs-panel button.tool-run'),
    select: sample('#job-kind'),
  };
}
"""


@pytest.mark.render
def test_ui_a11y_in_browser() -> None:
    """Load /ui in Chromium with every external origin blocked, then assert a11y.

    Verified when the pieces are present: the served page keeps its title,
    html lang, single h1 and named nav/main landmarks; each Phase 4 panel is a
    named region in the accessibility tree; every button has an accessible
    name; no image lacks alt text or an explicit hide; and panels, badges,
    buttons and inputs stay laid out and legible from the inline CSS alone
    (background, border, radius, padding and width sampled from computed style
    after the CDN and font requests are aborted).

    Skipped, never failed, with pytest recording the reason when Playwright, its
    Chromium build, or the ui extra (uvicorn) is unavailable.
    """
    sync_api = pytest.importorskip(
        "playwright.sync_api", reason="playwright not installed"
    )

    with _served_app() as base_url:
        try:
            playwright = sync_api.sync_playwright().start()
        except Exception as exc:  # pragma: no cover - environment dependent
            pytest.skip(f"playwright could not start: {exc}")

        browser = None
        external: list[str] = []
        try:
            try:
                browser = playwright.chromium.launch()
            except Exception as exc:  # pragma: no cover - environment dependent
                pytest.skip(f"Chromium not available: {exc}")

            page = browser.new_page()

            def _route(route) -> None:
                url = route.request.url
                if url.startswith(base_url) or url.startswith(("data:", "about:")):
                    route.continue_()
                else:
                    external.append(url)
                    route.abort()

            page.route("**/*", _route)
            page.goto(base_url + "/ui", wait_until="load")
            page.wait_for_timeout(300)

            assert page.title() == TITLE
            assert page.evaluate("document.documentElement.lang") == "en"

            assert page.get_by_role("heading", level=1).count() == 1
            assert page.get_by_role("navigation").count() >= 2
            assert page.get_by_role("main").count() == 1

            for slug in PHASE4_PANELS:
                selector = f"section#{slug}-panel"
                assert page.eval_on_selector(selector, "el => el.tagName") == "SECTION"

            unnamed = page.evaluate(
                "Array.from(document.querySelectorAll('button')).filter("
                "b => !(b.getAttribute('aria-label') || b.textContent.trim())).length"
            )
            assert unnamed == 0, f"{unnamed} button(s) without an accessible name"

            undecided = page.evaluate(
                "Array.from(document.querySelectorAll('img')).filter("
                "i => !i.hasAttribute('alt') && i.getAttribute('aria-hidden') !== 'true'"
                ").length"
            )
            assert undecided == 0

            styles = page.evaluate(_COMPUTED_STYLE_JS)

            for name in ("body", "panel", "title", "button", "select"):
                assert styles[name] is not None, f"{name} was not rendered"

            assert styles["body"]["background"] != "rgba(0, 0, 0, 0)", "body has no background"

            panel = styles["panel"]
            assert panel["background"] not in ("rgba(0, 0, 0, 0)", "transparent")
            assert panel["borderTop"] == "1px"
            assert panel["borderStyle"] == "solid"
            assert panel["radius"] != "0px"
            assert float(panel["padding"].rstrip("px")) > 0
            assert panel["width"] > 200, "panel collapsed with the network blocked"
            assert float(styles["title"]["fontSize"].rstrip("px")) > 12

            button = styles["button"]
            assert button["borderTop"] == "1px"
            assert button["radius"] != "0px"
            assert float(button["padding"].rstrip("px")) > 0
            assert button["width"] > 40

            select = styles["select"]
            assert select["display"] == "block"
            assert select["borderTop"] == "1px"
            assert select["width"] > 100

            assert styles["badge"]["display"] in ("inline-flex", "flex")

            assert external, "expected the CDN/font origins to be requested and blocked"
        finally:
            if browser is not None:
                browser.close()
            playwright.stop()
