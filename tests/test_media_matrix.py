"""Tests for the FFmpeg media matrix (``probe_media_matrix``).

The matrix is a best-effort diagnostic: it never crashes on a bad file, always
returns exactly one entry per input, and ``probe_media_matrix([])`` returns
``[]``. The ffprobe-backed assertions are marked ``@pytest.mark.render`` so a
bare CI runner without FFmpeg reports a documented skip instead of a failure.
"""

from __future__ import annotations

import pytest

from omniframe.engines.compositor.ffmpeg import ffmpeg_available
from omniframe.engines.compositor.presets import list_presets
from omniframe.engines.compositor.probe import probe_media_matrix

PRESET_NAMES = {preset["name"] for preset in list_presets()}


def test_empty_matrix_is_empty():
    assert probe_media_matrix([]) == []


def test_missing_file_is_single_error_entry(tmp_path):
    missing = tmp_path / "does-not-exist.mp4"
    entries = probe_media_matrix([missing])
    assert len(entries) == 1
    entry = entries[0]
    assert entry["path"] == str(missing)
    assert "error" in entry
    assert entry["compatible_with"] == {}


@pytest.mark.render
def test_synthetic_png_probes_with_ffprobe(tmp_path):
    if not ffmpeg_available():
        pytest.skip("ffprobe/ffmpeg is not available; matrix probe skipped")
    from PIL import Image

    image = tmp_path / "probe.png"
    Image.new("RGB", (64, 48), (200, 30, 40)).save(image)

    entries = probe_media_matrix([image])
    assert len(entries) == 1
    entry = entries[0]
    assert entry["path"] == str(image)
    assert "error" not in entry
    assert entry["video_codec"] == "png"
    assert entry["width"] == 64
    assert entry["height"] == 48
    assert entry["fps"] == pytest.approx(25.0)
    assert set(entry["compatible_with"]) == PRESET_NAMES
    # Every preset maps to a {"ok": bool, "reason": str} pair.
    for verdict in entry["compatible_with"].values():
        assert set(verdict) == {"ok", "reason"}
        assert isinstance(verdict["ok"], bool)
        assert isinstance(verdict["reason"], str)