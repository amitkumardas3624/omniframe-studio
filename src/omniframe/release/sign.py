"""Reproducible checksums for released OmniFrame artifacts.

A release is only trustworthy if a downloader can prove their bytes are ours.
This module produces that proof from content alone:

* entries are hashed in **sorted order**, so a report never inherits the order a
  filesystem or archive writer happened to use;
* only file content is hashed -- never mtimes, sizes or permissions -- so
  rebuilding the same tree yields the same digests;
* the sidecar is written as explicit UTF-8 with ``\\n`` newlines, so a Windows
  release box and a Linux CI runner produce byte-identical sidecars.

The sidecar format is ordinary ``sha256sum`` output (``<hex>  <entry>``), so a
downloader can verify it with tools already on their machine::

    sha256sum -c artifacts.sha256

Windows users can compare against ``Get-FileHash`` output by hand; the file is
plain text and deliberately carries no proprietary framing.
"""

from __future__ import annotations

import hashlib
import tarfile
import zipfile
from collections.abc import Iterator
from pathlib import Path
from typing import Any

from ..core.errors import ValidationError

__all__ = ["ARCHIVE_SUFFIXES", "CHUNK_SIZE", "DEFAULT_SIDECAR", "checksum_archive"]

#: Sidecar filename written next to an archive by default.
DEFAULT_SIDECAR = "artifacts.sha256"

#: Archive suffixes this module can walk (detection also falls back to magic).
ARCHIVE_SUFFIXES = (".zip", ".tar", ".tar.gz", ".tgz", ".tar.bz2", ".txz", ".tar.xz")

#: Read size when hashing entries; keeps memory flat for large media members.
CHUNK_SIZE = 1 << 20


def _normalize(name: str) -> str:
    """Return an archive entry name in one comparable form.

    Zip stores plain relative names while tar conventionally prefixes ``./``;
    stripping it makes an identical tree hash identically regardless of which
    container it was packed into.
    """
    normalized = name.replace("\\", "/")
    while normalized.startswith("./"):
        normalized = normalized[2:]
    return normalized


def _zip_entries(path: Path) -> Iterator[tuple[str, Any]]:
    """Yield ``(name, stream)`` for every regular file in a zip archive."""
    with zipfile.ZipFile(path) as archive:
        for info in archive.infolist():
            if info.is_dir():
                continue
            with archive.open(info) as handle:
                yield _normalize(info.filename), handle


def _tar_entries(path: Path) -> Iterator[tuple[str, Any]]:
    """Yield ``(name, stream)`` for every regular file in a tar archive."""
    with tarfile.open(path, "r:*") as archive:
        for member in archive.getmembers():
            if not member.isfile():
                continue
            handle = archive.extractfile(member)
            if handle is None:
                continue
            with handle:
                yield _normalize(member.name), handle


def _detect(path: Path) -> str:
    """Return ``"zip"`` or ``"tar"`` for ``path``, raising for anything else."""
    if zipfile.is_zipfile(path):
        return "zip"
    if tarfile.is_tarfile(path):
        return "tar"
    raise ValidationError(
        f"{path} is neither a zip nor a tar archive",
        archive=str(path),
    )


def _entries(path: Path) -> Iterator[tuple[str, Any]]:
    kind = _detect(path)
    if kind == "zip":
        return _zip_entries(path)
    return _tar_entries(path)


def _digest_stream(stream: Any, algorithm: str) -> str:
    """Hash a binary stream in :data:`CHUNK_SIZE` blocks."""
    digest = hashlib.new(algorithm)
    while True:
        chunk = stream.read(CHUNK_SIZE)
        if not chunk:
            break
        digest.update(chunk)
    return digest.hexdigest()


def _sidecar_text(entries: dict[str, str]) -> str:
    """Render ``sha256sum``-compatible lines, sorted, LF-terminated."""
    return "".join(f"{value}  {name}\n" for name, value in sorted(entries.items()))


def checksum_archive(
    archive_path: str | Path,
    *,
    algorithm: str = "sha256",
    sidecar: str | Path | None = None,
    write_sidecar: bool = True,
) -> dict[str, Any]:
    """Checksum every file entry in ``archive_path`` and emit a sidecar.

    ``archive_path`` may be a zip or a tar (compressed or not). The returned
    mapping lists each entry's digest in sorted order plus the algorithm and
    entry count, so two runs over the same bytes compare equal as plain dicts.

    With ``write_sidecar`` (the default) a ``sha256sum``-compatible sidecar is
    written to ``sidecar``, or to ``artifacts.sha256`` beside the archive. Set
    ``write_sidecar=False`` to only compute the report -- useful in tests and in
    read-only release mirrors.

    Raises :class:`~omniframe.core.errors.ValidationError` for a missing path,
    an unsupported algorithm, or a file that is neither zip nor tar.
    """
    path = Path(archive_path).expanduser()
    if not path.is_file():
        raise ValidationError(
            f"archive not found: {path}", archive=str(path)
        )
    if algorithm not in hashlib.algorithms_guaranteed:
        raise ValidationError(
            f"unsupported digest algorithm {algorithm!r}",
            algorithm=algorithm,
            supported=sorted(hashlib.algorithms_guaranteed),
        )

    entries: dict[str, str] = {}
    for name, stream in _entries(path):
        entries[name] = _digest_stream(stream, algorithm)
    ordered = {name: entries[name] for name in sorted(entries)}

    sidecar_path: Path | None = None
    if write_sidecar:
        sidecar_path = Path(sidecar).expanduser() if sidecar is not None else (
            path.parent / DEFAULT_SIDECAR
        )
        sidecar_path.parent.mkdir(parents=True, exist_ok=True)
        # newline="\n" keeps Windows and POSIX sidecars byte-identical.
        sidecar_path.write_text(
            _sidecar_text(ordered), encoding="utf-8", newline="\n"
        )

    return {
        "archive": str(path),
        "algorithm": algorithm,
        "entry_count": len(ordered),
        "entries": ordered,
        "sidecar": str(sidecar_path) if sidecar_path is not None else None,
    }


