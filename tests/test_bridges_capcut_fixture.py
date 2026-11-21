"""Task 4: CapCut version-pinned fixture test.

The CapCut bridge (``omniframe.bridges.CapCutBridge``) emits a ``draft_content.json``
whose top-level ``"version"`` is a hard-coded literal (``13.0.0``, see
``omniframe.core.timeline_schema.translate.CapCutDraftTranslator.from_universal``).
Because that version marker is deterministic and identifiable in code, this test
PINS it: the output for a canonical project must deep-equal the golden fixture at
``tests/fixtures/bridges/capcut-13.0.0/draft_content.json``.

This is a generation-only structural pin.  It never opens the CapCut host, never
launches an application, and uses no network or ffmpeg.  It consumes only the
already-shipped public bridge surface (``get_bridge``, ``GeneratedScript``) and the
timeline models needed to build a valid input project, and it does not touch files
owned by other workers (``tests/fixtures/bridges/*.txt`` from Task 1 are untouched;
the golden here lives in a version-specific subdirectory).
"""

from __future__ import annotations

import json
from pathlib import Path

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

PINNED_VERSION = "13.0.0"

FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures" / "bridges"
GOLDEN_DIR = FIXTURES_DIR / f"capcut-{PINNED_VERSION}"
GOLDEN_DRAFT = GOLDEN_DIR / "draft_content.json"


def _make_pin_project() -> OmniProject:
    """The canonical project the golden was generated from.

    IMPORTANT: keep this project identical to the one documented in
    ``capcut-13.0.0/README.md`` (30 fps, 1920x1080, one audio + one video track,
    no ``Asset`` records).  Changing it here requires regenerating the golden and
    re-verifying the version pin.
    """
    project = OmniProject(
        meta=ProjectMeta(name="capcut-pin", fps=30, width=1920, height=1080)
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


def _load_golden() -> dict:
    """Load and parse the pinned golden draft."""
    assert GOLDEN_DIR.is_dir(), f"golden fixture directory missing: {GOLDEN_DIR}"
    assert GOLDEN_DRAFT.is_file(), f"golden draft missing: {GOLDEN_DRAFT}"
    return json.loads(GOLDEN_DRAFT.read_text(encoding="utf-8"))


def test_capcut_golden_and_version_meta_exist() -> None:
    """The pinned golden and its version documentation are present."""
    assert GOLDEN_DIR.is_dir(), f"expected version fixture dir: {GOLDEN_DIR}"
    assert GOLDEN_DRAFT.is_file(), f"expected golden draft: {GOLDEN_DRAFT}"
    assert (GOLDEN_DIR / "README.md").is_file(), "version pin documentation missing"
    golden = _load_golden()
    assert golden["version"] == PINNED_VERSION, "golden version marker mismatch"


def test_capcut_generate_matches_pinned_golden(tmp_path: Path) -> None:
    """Stable format: generated draft must deep-equal the pinned golden.

    Because ``from_universal`` hard-codes the format version, the output is
    deterministic and can be pinned.  If this ever fails, the CapCut draft format
    changed on us and the pin must be re-verified — do not silently regenerate.
    """
    bridge = get_bridge("capcut")
    project = _make_pin_project()

    result = bridge.generate_script(project, tmp_path / "out")

    # -- the generated artifact exists, non-empty, correct suffix -----------
    generated = Path(result.path)
    assert generated.exists(), f"generated draft missing: {generated}"
    assert generated.stat().st_size > 0, "generated draft is empty"
    assert generated.suffix == bridge.script_extension == ".json"

    # -- generated contract fields ------------------------------------------
    assert result.language == "json"
    assert result.bridge == "capcut"
    assert result.summary, "summary must be non-empty"

    # -- structural / version assertions (generation-only, no host) ---------
    data = json.loads(generated.read_text(encoding="utf-8"))
    assert data["version"] == PINNED_VERSION, (
        f"emitted version {data.get('version')!r} != pinned {PINNED_VERSION!r}"
    )
    assert {"materials", "tracks", "version", "canvas_config", "fps"} <= set(data), (
        f"missing expected top-level draft keys; got {sorted(data)}"
    )

    # -- the full golden pin: deep equality with the fixture ----------------
    assert data == _load_golden(), (
        "CapCut draft output diverged from the pinned golden fixture "
        f"({GOLDEN_DRAFT}). Re-verify the format version before changing anything."
    )

    # -- warnings must be honest (host absent), never claim a host run ------
    assert result.warnings, "expected at least a host-not-detected warning"
    for warning in result.warnings:
        assert any(frag in warning for frag in ("not detected", "undocumented and version specific")), (
            f"unexpected/untrusted warning: {warning!r}"
        )


def test_capcut_host_is_not_opened(tmp_path: Path) -> None:
    """Honesty guard: this fixture's detection state must not claim a host."""
    assert get_bridge("capcut").detect().installed is False
    # Generation succeeds even though the host is absent — proving that doing so
    # is a generation-only step, not a host-launch.
    result = get_bridge("capcut").generate_script(_make_pin_project(), tmp_path / "out2")
    assert Path(result.path).exists()