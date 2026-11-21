"""Tests for golden-frame verification against a stored reference.

These test the hash mode of :func:`verify_frames` with deterministic Pillow
images, plus a ``to_dict`` round-trip. The perceptual (tolerance) path is
exercised only implicitly where Pillow is present; the hash-only path remains
usable as the default.
"""

from __future__ import annotations

from PIL import Image

from omniframe.engines.compositor.golden import sha256_of, verify_frames


def _write_frames(directory, count: int = 3, *, color=(10, 20, 30, 255)) -> list[str]:
    """Write ``count`` deterministic ``frame_*.png`` files and return their names."""

    names: list[str] = []
    for index in range(count):
        name = f"frame_{index:04d}.png"
        image = Image.new("RGBA", (8, 8), color)
        (directory / name).parent.mkdir(parents=True, exist_ok=True)
        image.save(directory / name)
        names.append(name)
    return names


def test_identical_frames_pass(tmp_path):
    reference = tmp_path / "reference"
    produced = tmp_path / "produced"
    reference.mkdir()
    produced.mkdir()
    _write_frames(reference)
    _write_frames(produced)

    report = verify_frames(reference, produced)

    assert report.ok is True
    assert report.total == 3
    assert report.matched == 3
    assert report.mismatched == []
    assert report.missing == []


def test_mutated_frame_is_mismatched(tmp_path):
    reference = tmp_path / "reference"
    produced = tmp_path / "produced"
    reference.mkdir()
    produced.mkdir()
    _write_frames(reference)
    produced_frames = _write_frames(produced)

    # Mutate the second produced frame's contents only.
    mutated = produced / produced_frames[1]
    Image.new("RGBA", (8, 8), (90, 255, 0, 200)).save(mutated)

    report = verify_frames(reference, produced)

    assert report.total == 3
    assert report.matched == 2
    assert report.ok is False
    assert len(report.mismatched) == 1
    entry = report.mismatched[0]
    assert entry["frame"] == produced_frames[1]
    assert entry["expected_hash"] == sha256_of(reference / produced_frames[1])
    assert entry["actual_hash"] == sha256_of(mutated)
    assert entry["actual_hash"] != entry["expected_hash"]
    assert report.missing == []


def test_missing_produced_frame_reported(tmp_path):
    reference = tmp_path / "reference"
    produced = tmp_path / "produced"
    reference.mkdir()
    produced.mkdir()
    names = _write_frames(reference)
    _write_frames(produced)

    # Remove one produced file.
    (produced / names[0]).unlink()

    report = verify_frames(reference, produced)

    assert report.ok is False
    assert report.total == 3
    assert report.matched == 2
    assert names[0] in report.missing
    assert len(report.missing) == 1
    assert report.mismatched == []


def test_to_dict_round_trip(tmp_path):
    reference = tmp_path / "reference"
    produced = tmp_path / "produced"
    reference.mkdir()
    produced.mkdir()
    _write_frames(reference)
    _write_frames(produced)

    data = verify_frames(reference, produced).to_dict()

    for key in ("total", "matched", "mismatched", "missing", "ok"):
        assert key in data
    assert data["total"] == 3
    assert data["matched"] == 3
    assert data["mismatched"] == []
    assert data["missing"] == []
    assert data["ok"] is True


def test_empty_reference_dir_reports_ok(tmp_path):
    reference = tmp_path / "reference"
    produced = tmp_path / "produced"
    reference.mkdir()
    produced.mkdir()

    report = verify_frames(reference, produced)

    assert report.total == 0
    assert report.matched == 0
    assert report.ok is True


def test_missing_reference_dir_is_vacuous(tmp_path):
    produced = tmp_path / "produced"
    produced.mkdir()

    report = verify_frames(tmp_path / "nonexistent-reference", produced)

    assert report.total == 0
    assert report.ok is True


def test_sha256_of_matches_read_bytes(tmp_path):
    frame = tmp_path / "frame_0000.png"
    Image.new("RGB", (4, 4), (255, 0, 0)).save(frame)

    import hashlib

    assert sha256_of(frame) == hashlib.sha256(frame.read_bytes()).hexdigest()


def test_tolerance_path_matches_close_frames(tmp_path):
    reference = tmp_path / "reference"
    produced = tmp_path / "produced"
    reference.mkdir()
    produced.mkdir()
    _write_frames(reference, color=(50, 50, 50, 255))
    files = _write_frames(produced, color=(50, 50, 50, 255))
    # Slight perturbation stays within a permissive tolerance.
    Image.new("RGBA", (8, 8), (51, 50, 50, 255)).save(produced / files[0])

    report = verify_frames(reference, produced, tolerance=255.0)

    assert report.ok is True
    assert report.matched == report.total == 3


def test_tolerance_mismatch_reports_difference(tmp_path):
    reference = tmp_path / "reference"
    produced = tmp_path / "produced"
    reference.mkdir()
    produced.mkdir()
    _write_frames(reference, color=(0, 0, 0, 255))
    files = _write_frames(produced, color=(0, 0, 0, 255))
    # Drastic change fails a tight tolerance.
    Image.new("RGBA", (8, 8), (255, 255, 255, 255)).save(produced / files[0])

    report = verify_frames(reference, produced, tolerance=0.5)

    assert report.ok is False
    assert len(report.mismatched) == 1
    assert report.mismatched[0]["frame"] == files[0]
    assert "difference" in report.mismatched[0]