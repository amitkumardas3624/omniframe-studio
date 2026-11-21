"""Tests for the evidence-based compatibility report.

Most tests inject a ``probe`` so they stay host-independent and cannot outlive
their usefulness on a machine without ffmpeg. The one test that encodes for real
skips when ffmpeg is absent, and is marked ``slow``.
"""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from omniframe.core.errors import ValidationError
from omniframe.release import compat
from omniframe.release.compat import (
    PROBED_CODECS,
    VERIFICATION_LEVELS,
    compatibility_report,
)

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(autouse=True)
def _no_encoder_subprocess(monkeypatch) -> None:
    """Pre-empt the ``ffmpeg -encoders`` call unless a test asks for it."""
    monkeypatch.setitem(compat._ENCODER_CACHE, "names", set())


@pytest.fixture(autouse=True)
def _clear_probe_cache(monkeypatch) -> None:
    monkeypatch.setattr(compat, "_PROBE_CACHE", {})


def _recorder(answer: bool | dict[str, bool]):
    """A probe that records which codecs it was asked about."""
    calls: list[str] = []

    def probe(preset):
        calls.append(preset["video_codec"])
        if isinstance(answer, dict):
            return bool(answer.get(preset["video_codec"], False)), "mapped"
        return bool(answer), "mapped"

    return probe, calls


# -- report shape -------------------------------------------------------------


def test_report_covers_every_shipped_preset() -> None:
    probe, _ = _recorder(False)
    report = compatibility_report({"machine": "unit"}, probe=probe)

    assert set(report["presets"]) == {"gif", "h264", "h265", "png_sequence", "prores", "qtrle_alpha", "webm"}
    assert report["levels"] == list(VERIFICATION_LEVELS)
    assert sorted(report["probed_codecs"]) == sorted(PROBED_CODECS)


def test_every_entry_carries_the_preset_facts() -> None:
    probe, _ = _recorder(True)
    report = compatibility_report({}, probe=probe)

    h264 = report["presets"]["h264"]
    assert h264["container"] == "mp4"
    assert h264["video_codec"] == "libx264"
    assert h264["audio_codec"] == "aac"
    assert h264["supports_transparency"] is False
    assert h264["status"] == "render_tested"
    assert h264["reason"]

    qtrle = report["presets"]["qtrle_alpha"]
    assert qtrle["container"] == "mov"
    assert qtrle["video_codec"] == "qtrle"
    assert qtrle["supports_transparency"] is True


def test_only_probed_codecs_are_encoded() -> None:
    probe, calls = _recorder(True)
    compatibility_report({}, probe=probe)

    assert sorted(calls) == sorted(PROBED_CODECS)
    assert "prores_ks" not in calls
    assert "qtrle" not in calls


def test_successful_probe_promotes_only_probed_presets() -> None:
    probe, _ = _recorder(True)
    report = compatibility_report({}, probe=probe)

    for name in ("h264", "webm", "gif"):
        assert report["presets"][name]["status"] == "render_tested", name
    for name in ("h265", "prores", "qtrle_alpha", "png_sequence"):
        assert report["presets"][name]["status"] == "unverified", name
    assert report["summary"]["render_tested"] == 3


def test_failed_probe_promotes_nothing() -> None:
    probe, _ = _recorder(False)
    report = compatibility_report({}, probe=probe)

    assert report["summary"]["render_tested"] == 0
    assert report["summary"]["unverified"] == len(report["presets"])
    assert all(entry["status"] == "unverified" for entry in report["presets"].values())


def test_partial_probe_is_recorded_per_preset() -> None:
    probe, _ = _recorder({"libx264": True, "libvpx-vp9": False, "gif": True})
    report = compatibility_report({}, probe=probe)

    assert report["presets"]["h264"]["status"] == "render_tested"
    assert report["presets"]["webm"]["status"] == "unverified"
    assert report["presets"]["gif"]["status"] == "render_tested"
    assert report["summary"] == {"unverified": 5, "import_tested": 0, "render_tested": 2}


def test_statuses_stay_inside_the_vocabulary() -> None:
    probe, _ = _recorder(True)
    report = compatibility_report({"os": "test"}, probe=probe, evidence={"prores": "import_tested"})

    for name, entry in report["presets"].items():
        assert entry["status"] in VERIFICATION_LEVELS, name


def test_encoder_listing_never_promotes_a_status(monkeypatch) -> None:
    """A codec in ``ffmpeg -encoders`` is capability, not evidence."""
    # Pretend ffmpeg is installed so the result does not depend on the host:
    # without it the capability is honestly "unknown" everywhere.
    monkeypatch.setattr(compat, "_ffmpeg_binary", lambda: "ffmpeg")
    monkeypatch.setitem(
        compat._ENCODER_CACHE,
        "names",
        {"libx264", "libvpx-vp9", "gif", "prores_ks", "qtrle"},
    )
    probe, _ = _recorder(False)
    report = compatibility_report({}, probe=probe)

    assert report["presets"]["prores"]["capability"] == "encoder_present"
    assert report["presets"]["prores"]["status"] == "unverified"
    assert report["presets"]["qtrle_alpha"]["capability"] == "encoder_present"
    assert report["presets"]["qtrle_alpha"]["status"] == "unverified"


def test_missing_encoder_is_reported_as_such(monkeypatch) -> None:
    monkeypatch.setattr(compat, "_ffmpeg_binary", lambda: "ffmpeg")
    monkeypatch.setitem(compat._ENCODER_CACHE, "names", {"libx264"})
    probe, _ = _recorder(False)
    report = compatibility_report({}, presets=["h264", "h265"], probe=probe)

    assert report["presets"]["h264"]["capability"] == "encoder_present"
    assert report["presets"]["h265"]["capability"] == "encoder_missing"


def test_env_is_recorded_verbatim_without_aliasing() -> None:
    env = {"machine": "desktop", "python": "3.12.10"}
    probe, _ = _recorder(False)
    report = compatibility_report(env, presets=["h264"], probe=probe)

    assert report["env"] == env
    env["python"] = "tampered"
    assert report["env"]["python"] == "3.12.10"


def test_preset_filter_narrows_the_work() -> None:
    probe, calls = _recorder(True)
    report = compatibility_report({}, presets=["h264"], probe=probe)

    assert list(report["presets"]) == ["h264"]
    assert calls == ["libx264"]
    assert report["summary"]["render_tested"] == 1


def test_unknown_preset_filter_is_rejected() -> None:
    probe, _ = _recorder(True)
    with pytest.raises(ValidationError) as excinfo:
        compatibility_report({}, presets=["h264", "nonesuch"], probe=probe)

    assert excinfo.value.code == "E_VALIDATION"
    assert "nonesuch" in excinfo.value.details["presets"]


def test_evidence_promotes_status_a_probe_cannot_reach() -> None:
    probe, _ = _recorder(True)
    report = compatibility_report(
        {}, probe=probe, evidence={"prores": "render_tested"}
    )

    assert report["presets"]["prores"]["status"] == "render_tested"
    assert "evidence" in report["presets"]["prores"]["reason"]


def test_evidence_with_unknown_level_is_rejected() -> None:
    probe, _ = _recorder(True)
    with pytest.raises(ValidationError):
        compatibility_report({}, probe=probe, evidence={"prores": "trusted"})


def test_evidence_with_unknown_preset_is_rejected() -> None:
    probe, _ = _recorder(True)
    with pytest.raises(ValidationError):
        compatibility_report({}, probe=probe, evidence={"nonesuch": "render_tested"})


# -- the real probe -----------------------------------------------------------


def test_real_probe_reports_absent_ffmpeg_honestly(monkeypatch) -> None:
    """With no ffmpeg on PATH, the report must claim nothing."""
    monkeypatch.setattr(compat, "_ffmpeg_binary", lambda: None)

    report = compatibility_report({"machine": "no-ffmpeg"})

    assert report["ffmpeg"]["available"] is False
    assert report["ffmpeg"]["version"] is None
    assert report["summary"]["render_tested"] == 0


@pytest.mark.slow
@pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="ffmpeg not installed")
def test_real_probe_encodes_and_reads_back() -> None:
    """The one test that proves the probe is wired to a real encoder."""
    report = compatibility_report({"machine": "local"}, presets=["h264"])

    assert report["ffmpeg"]["available"] is True
    assert report["ffmpeg"]["version"].startswith("ffmpeg version")
    entry = report["presets"]["h264"]
    assert entry["status"] == "render_tested", entry["reason"]
    assert "bytes" in entry["reason"] and "codec_name" in entry["reason"]


# -- documentation must not drift from the code ------------------------------


def test_compatibility_matrix_documents_every_preset() -> None:
    text = (ROOT / "docs" / "compatibility-matrix.md").read_text(encoding="utf-8")
    for name in ("h264", "h265", "prores", "webm", "gif", "png_sequence", "qtrle_alpha"):
        assert name in text, name


def test_release_checklist_carries_the_identity_prerequisite() -> None:
    text = (ROOT / "docs" / "release-checklist.md").read_text(encoding="utf-8").lower()

    assert "repository identity" in text
    assert "blocker" in text
    assert "omniframe doctor" in text or "cli doctor" in text
    assert "sha256sum -c" in text


def test_phase5_report_flags_the_blocker() -> None:
    text = (ROOT / "docs" / "phase-reports" / "phase5-release.md").read_text(
        encoding="utf-8"
    ).lower()

    assert "release-blocking" in text
    assert "repository identity" in text



