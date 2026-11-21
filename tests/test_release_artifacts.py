"""Tests for reproducible release-artifact checksums.

Reproducibility is the whole point of :func:`checksum_archive`, so these tests
build the same tree twice with different metadata (mtimes) and assert the
digests are unchanged, then assert the sidecar agrees with the report.
"""

from __future__ import annotations

import hashlib
import io
import tarfile
import zipfile
from pathlib import Path

import pytest

from omniframe.core.errors import ValidationError
from omniframe.release.sign import (
    CHUNK_SIZE,
    DEFAULT_SIDECAR,
    checksum_archive,
)

FILES = {
    "project.json": b'{"name": "omniframe", "version": "0.1.0"}\n',
    "scenes/intro/scene.json": b'{"id": "intro"}\n',
    "media/logo.bin": bytes(range(256)) * 4,
}

EARLY = (2020, 1, 1, 0, 0, 0)
LATE = (2024, 6, 1, 12, 30, 0)


def _build_zip(path: Path, files: dict[str, bytes], stamp: tuple[int, ...]) -> Path:
    """Write ``files`` into a zip at ``path`` with every entry at ``stamp``."""
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name, payload in files.items():
            info = zipfile.ZipInfo(name, date_time=stamp)
            info.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(info, payload)
    return path


def _build_tar_gz(path: Path, files: dict[str, bytes]) -> Path:
    """Write ``files`` into a gzipped tar at ``path`` (tar-style ``./`` names)."""
    with tarfile.open(path, "w:gz") as archive:
        for name, payload in files.items():
            info = tarfile.TarInfo(f"./{name}")
            info.size = len(payload)
            archive.addfile(info, io.BytesIO(payload))
    return path


# -- report shape -------------------------------------------------------------


def test_report_sorts_entries_and_counts_them(tmp_path) -> None:
    archive = _build_zip(tmp_path / "release.zip", FILES, EARLY)
    report = checksum_archive(archive)

    names = list(report["entries"])
    assert names == sorted(FILES), "entries must be emitted in sorted order"
    assert report["entry_count"] == len(FILES)
    assert report["algorithm"] == "sha256"
    assert report["archive"] == str(archive)


def test_digests_hash_entry_content(tmp_path) -> None:
    archive = _build_zip(tmp_path / "release.zip", FILES, EARLY)
    report = checksum_archive(archive)

    for name, payload in FILES.items():
        assert report["entries"][name] == hashlib.sha256(payload).hexdigest()


def test_digests_ignore_archive_metadata(tmp_path) -> None:
    """Same content, different mtimes -> identical digests (reproducible)."""
    first = checksum_archive(_build_zip(tmp_path / "a.zip", FILES, EARLY))
    second = checksum_archive(_build_zip(tmp_path / "b.zip", FILES, LATE))

    assert first["entries"] == second["entries"]
    assert first["entry_count"] == second["entry_count"]


def test_two_runs_over_the_same_archive_are_identical(tmp_path) -> None:
    archive = _build_zip(tmp_path / "release.zip", FILES, EARLY)
    assert checksum_archive(archive)["entries"] == checksum_archive(archive)["entries"]


# -- sidecar ------------------------------------------------------------------


def test_sidecar_is_written_beside_the_archive(tmp_path) -> None:
    archive = _build_zip(tmp_path / "release.zip", FILES, EARLY)
    report = checksum_archive(archive)

    sidecar = tmp_path / DEFAULT_SIDECAR
    assert report["sidecar"] == str(sidecar)
    assert sidecar.is_file()


def test_sidecar_matches_the_report(tmp_path) -> None:
    archive = _build_zip(tmp_path / "release.zip", FILES, EARLY)
    report = checksum_archive(archive)

    payload = (tmp_path / DEFAULT_SIDECAR).read_bytes()
    assert b"\r" not in payload, "sidecars must be LF-only to compare across OSes"
    assert payload.endswith(b"\n")

    lines = payload.decode("utf-8").splitlines()
    assert len(lines) == report["entry_count"]
    parsed = {}
    for line in lines:
        digest, sep, name = line.partition("  ")
        assert sep == "  ", line
        parsed[name] = digest
    assert parsed == report["entries"]
    assert list(parsed) == sorted(parsed), "sidecar must be written in sorted order"


def test_sidecar_can_be_redirected_and_skipped(tmp_path) -> None:
    archive = _build_zip(tmp_path / "release.zip", FILES, EARLY)

    custom = tmp_path / "dist" / "checksums.txt"
    report = checksum_archive(archive, sidecar=custom)
    assert report["sidecar"] == str(custom)
    assert custom.is_file()

    before = custom.read_text(encoding="utf-8")
    dry = checksum_archive(archive, sidecar=custom, write_sidecar=False)
    assert dry["sidecar"] is None
    assert dry["entries"] == report["entries"]
    assert custom.read_text(encoding="utf-8") == before, "dry run must not write"


# -- containers and algorithms ------------------------------------------------


def test_tar_archive_is_walked(tmp_path) -> None:
    archive = _build_tar_gz(tmp_path / "release.tar.gz", FILES)
    report = checksum_archive(archive)

    assert report["entry_count"] == len(FILES)
    assert report["entries"] == {
        name: hashlib.sha256(payload).hexdigest() for name, payload in FILES.items()
    }


def test_zip_and_tar_of_the_same_tree_agree(tmp_path) -> None:
    """tar's conventional ``./`` prefix must not change the digests."""
    zipped = checksum_archive(_build_zip(tmp_path / "release.zip", FILES, EARLY))
    tarred = checksum_archive(_build_tar_gz(tmp_path / "release.tar.gz", FILES))

    assert tarred["entries"] == zipped["entries"]


def test_alternate_algorithm(tmp_path) -> None:
    archive = _build_zip(tmp_path / "release.zip", {"a.txt": b"a"}, EARLY)
    report = checksum_archive(archive, algorithm="md5")

    assert report["algorithm"] == "md5"
    assert report["entries"]["a.txt"] == hashlib.md5(b"a").hexdigest()
    assert len(report["entries"]["a.txt"]) == 32


def test_directories_are_not_entries(tmp_path) -> None:
    archive = tmp_path / "release.zip"
    with zipfile.ZipFile(archive, "w") as handle:
        handle.writestr("empty/", b"")
        handle.writestr("kept.txt", b"kept")

    report = checksum_archive(archive)
    assert list(report["entries"]) == ["kept.txt"]


def test_chunk_size_is_used_for_large_entries(tmp_path) -> None:
    payload = b"x" * (CHUNK_SIZE + 7)
    archive = _build_zip(tmp_path / "big.zip", {"big.bin": payload}, EARLY)

    report = checksum_archive(archive)
    assert report["entries"]["big.bin"] == hashlib.sha256(payload).hexdigest()


# -- refusals -----------------------------------------------------------------


def test_missing_archive_is_a_validation_error(tmp_path) -> None:
    with pytest.raises(ValidationError) as excinfo:
        checksum_archive(tmp_path / "nope.zip")
    assert excinfo.value.code == "E_VALIDATION"


def test_non_archive_is_a_validation_error(tmp_path) -> None:
    target = tmp_path / "notes.txt"
    target.write_text("hello", encoding="utf-8")
    with pytest.raises(ValidationError):
        checksum_archive(target)


def test_unsupported_algorithm_is_a_validation_error(tmp_path) -> None:
    archive = _build_zip(tmp_path / "release.zip", {"a.txt": b"a"}, EARLY)
    with pytest.raises(ValidationError) as excinfo:
        checksum_archive(archive, algorithm="nonesuch")
    assert excinfo.value.details["algorithm"] == "nonesuch"



