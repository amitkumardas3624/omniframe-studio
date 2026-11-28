"""The two decompiled templates: purity, parts and the gate they earn.

Both templates are decompiled from a reference reel. What is checked here:
that the scene ships its parts and stays pure (one seek, no timers, no
unseeded randomness), and that the reference frame lookup still finds a
reference by its frame number rather than by its position in a folder.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from omniframe.engines.compositor.compare import (  # noqa: E402
    _resolve_reference_png,
    verdict,
)

ROOT = Path(__file__).resolve().parents[1]
TEMPLATES = (
    ROOT / "examples" / "kinetic-intro",
    ROOT / "examples" / "kinetic-type-railway",
)


@pytest.mark.parametrize("template", TEMPLATES, ids=lambda p: p.name)
def test_template_ships_its_parts(template: Path) -> None:
    for name in ("scene.html", "scene.js", "content.json", "render_template.py", "README.md"):
        assert (template / name).exists(), name


@pytest.mark.parametrize("template", TEMPLATES, ids=lambda p: p.name)
def test_scene_has_exactly_one_frame_marker(template: Path) -> None:
    script = (template / "scene.js").read_text(encoding="utf-8")
    assert script.count("// === FRAME ===") == 1


@pytest.mark.parametrize("template", TEMPLATES, ids=lambda p: p.name)
def test_scene_is_pure_and_addressable(template: Path) -> None:
    script = (template / "scene.js").read_text(encoding="utf-8")
    assert "window.seek = function" in script
    assert "requestAnimationFrame" not in script
    assert "setTimeout" not in script
    assert "Math.random" not in script


@pytest.mark.parametrize("template", TEMPLATES, ids=lambda p: p.name)
def test_harness_matches_the_reference_frame_size(template: Path) -> None:
    harness = (template / "render_template.py").read_text(encoding="utf-8")
    assert "WIDTH = 1280" in harness
    assert "HEIGHT = 720" in harness


def test_reference_frames_are_matched_by_name_not_position(tmp_path: Path) -> None:
    """f060.png is reference frame 60, never "the first file in the folder"."""

    (tmp_path / "f060.png").write_bytes(b"x")
    (tmp_path / "f180.png").write_bytes(b"x")
    path, match = _resolve_reference_png(tmp_path, 60)
    assert path is not None and path.name == "f060.png"
    assert match == "frame_number"
    missing, kind = _resolve_reference_png(tmp_path, 0)
    assert missing is None, "frame 0 must not borrow another frame file"
    assert kind == "no_match"


def test_the_gate_passes_a_complete_checklist_and_rejects_a_bare_limit() -> None:
    rows = [
        {"id": "background_shifts", "status": "match", "note": ""},
        {"id": "grid_density", "status": "match", "note": ""},
        {"id": "particle_construction", "status": "match", "note": ""},
        {"id": "3d_focal_objects", "status": "match", "note": ""},
        {"id": "outro_hierarchy", "status": "limit", "note": "the logo is drawn, not licensed"},
    ]
    assert verdict(rows)["ok"] is True
    bare = [dict(row, note="") for row in rows]
    assert verdict(bare)["ok"] is False
    assert verdict(bare)["limits_without_note"] == ["outro_hierarchy"]
