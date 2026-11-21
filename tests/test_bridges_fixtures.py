"""Fixture-driven, host-independent tests for the CapCut, Premiere Pro and
After Effects bridges.

These tests generate each bridge's script into a ``tmp_path`` and assert it is
a non-empty file with the bridge's ``script_extension``, plus a deterministic
contract on ``language``, ``summary``, ``metadata`` serialisability and the
contents of ``warnings``.

Design notes
------------
* No real host is launched and no network/ffmpeg is required.  ``detect()``
  reports ``installed is False`` for every host on this machine (doctor
  confirms none of Premiere/AE/Resolve/CapCut/Krita is installed).
* Because the host is absent, ``generate_script`` may legitimately emit an
  explicit ``host not detected`` warning rather than staying silent.  The
  warnings assertion therefore checks the *deterministic contract*: every
  warning must carry one of the known, expected fragments below, and must
  never be an unexpected/unrelated error.  This stays deterministic whether
  or not the host happens to be installed.
* "Golden" marker strings live under ``tests/fixtures/bridges/`` and are read
  into each parametrised case, so the script bodies are compared against the
  curated fixture markers rather than hard-coded strings.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from omniframe.bridges import get_bridge
from omniframe.core.timeline_schema.models import (
    Clip,
    ClipKind,
    OmniProject,
    ProjectMeta,
    RenderTarget,
    Track,
    TrackKind,
)

FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures" / "bridges"

#: Every warning a bridge may emit must contain at least one of these
#: fragments.  Anything outside this set is treated as an unexpected error.
KNOWN_WARNING_FRAGMENTS: tuple[str, ...] = (
    "was not detected",
    "not detected",
    "undocumented and version specific",
    "referenced media file(s) are missing",
    "have no media source",
)


def _make_project() -> OmniProject:
    """A minimal, valid :class:`OmniProject` accepted by all three bridges."""
    project = OmniProject(
        meta=ProjectMeta(name="fixture-demo", fps=30, width=1920, height=1080)
    )
    project.render_targets.append(
        RenderTarget(id="r1", container="mp4", video_codec="h264", path="out/fixture.mp4")
    )
    project.tracks.append(
        Track(
            id="v1",
            name="Video 1",
            kind=TrackKind.VIDEO,
            clips=[
                Clip(
                    id="c1",
                    name="Intro",
                    kind=ClipKind.VIDEO,
                    start_frame=0,
                    duration_frames=60,
                    source="assets/intro.mp4",
                )
            ],
        )
    )
    project.tracks.append(
        Track(
            id="a1",
            name="Audio 1",
            kind=TrackKind.AUDIO,
            clips=[
                Clip(
                    id="c2",
                    name="Voice",
                    kind=ClipKind.AUDIO,
                    start_frame=0,
                    duration_frames=60,
                    source="assets/voice.wav",
                )
            ],
        )
    )
    return project


def _golden_markers(bridge_id: str) -> list[str]:
    """Non-empty marker lines from the bridge's golden fixture file."""
    path = FIXTURES_DIR / f"{bridge_id}.txt"
    assert path.exists(), f"golden fixture missing: {path}"
    return [line.strip() for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


#: (bridge_id, expected ``language``, expected file suffix)
BRIDGE_CASES: tuple[tuple[str, str, str], ...] = (
    ("capcut", "json", ".json"),
    ("premiere_pro", "javascript", ".jsx"),
    ("after_effects", "javascript", ".jsx"),
)


def test_fixture_markers_exist_for_each_bridge() -> None:
    """Every bridge under test must have a non-empty golden fixture."""
    for bridge_id, _language, _extension in BRIDGE_CASES:
        assert _golden_markers(bridge_id), f"empty golden fixture for {bridge_id}"


@pytest.mark.parametrize(
    ("bridge_id", "expected_language", "expected_suffix"),
    BRIDGE_CASES,
    ids=[case[0] for case in BRIDGE_CASES],
)
def test_generate_script_contract(
    tmp_path: Path,
    bridge_id: str,
    expected_language: str,
    expected_suffix: str,
) -> None:
    bridge = get_bridge(bridge_id)
    project = _make_project()

    result = bridge.generate_script(project, tmp_path / bridge_id)

    # -- the generated file exists and is non-empty ---------------------
    generated = Path(result.path)
    assert generated.exists(), f"{bridge_id}: result.path does not exist: {generated}"
    assert generated.stat().st_size > 0, f"{bridge_id}: generated file is empty"

    # -- the suffix matches the bridge's script_extension ---------------
    assert expected_suffix == bridge.script_extension
    assert generated.suffix == expected_suffix, (
        f"{bridge_id}: expected suffix {expected_suffix!r}, got {generated.suffix!r}"
    )

    # -- deterministic language / summary / metadata --------------------
    assert result.language == expected_language
    assert result.summary, f"{bridge_id}: summary must be non-empty"
    assert isinstance(result.metadata, dict)
    json.dumps(result.metadata)  # must be JSON-serialisable

    # -- golden markers appear in the generated body --------------------
    body = generated.read_text(encoding="utf-8")
    for marker in _golden_markers(bridge_id):
        assert marker in body, f"{bridge_id}: golden marker {marker!r} missing from output"

    # -- warnings respect the deterministic contract --------------------
    for warning in result.warnings:
        assert any(fragment in warning for fragment in KNOWN_WARNING_FRAGMENTS), (
            f"{bridge_id}: unexpected warning: {warning!r}"
        )


def test_all_hosts_absent_in_fixture_machine() -> None:
    """Honesty guard: on this machine no host may report as installed."""
    for bridge_id, _language, _extension in BRIDGE_CASES:
        assert get_bridge(bridge_id).detect().installed is False