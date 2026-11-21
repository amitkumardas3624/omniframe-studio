"""Golden-frame verification for compositor output.

This module verifies a directory of produced ``frame_*.png`` files against a
stored reference directory. In the default ``hash="sha256"`` mode it compares
exact SHA-256 digests; when ``tolerance > 0`` it engages a perceptual pass that
compares the maximum mean absolute difference across RGBA channels (via Pillow)
against ``tolerance``.

Pillow stays an optional dependency: the hash-only path works without it, and
Pillow is imported lazily inside the perceptual branch (mirroring the convention
used in :mod:`omniframe.engines.compositor.ffmpeg`).
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

__all__ = ["GoldenReport", "verify_frames", "sha256_of"]


def sha256_of(path: str | Path) -> str:
    """Return the lowercase hex SHA-256 digest of the file at ``path``."""

    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for block in iter(lambda: handle.read(65536), b""):
            digest.update(block)
    return digest.hexdigest()


def _file_hash(path: str | Path, *, hash_name: str) -> str:
    digest = hashlib.new(hash_name)
    with Path(path).open("rb") as handle:
        for block in iter(lambda: handle.read(65536), b""):
            digest.update(block)
    return digest.hexdigest()


def _mean_abs_diff_rgba(produced: str | Path, expected: str | Path) -> float:
    """Maximum mean-absolute pixel difference between two RGBA frames.

    A value of ``float("inf")`` signals the frames have different dimensions.
    """
    from PIL import Image  # optional dependency, pulled in only when needed

    with Image.open(Path(produced)).convert("RGBA") as actual, Image.open(Path(expected)).convert(
        "RGBA"
    ) as expected_image:
        if actual.size != expected_image.size:
            return float("inf")
        width, height = actual.size
        actual_px = actual.load()
        expected_px = expected_image.load()
        total = 0
        count = width * height * 4
        for y in range(height):
            for x in range(width):
                ap = actual_px[x, y]
                ep = expected_px[x, y]
                total += (
                    abs(ap[0] - ep[0])
                    + abs(ap[1] - ep[1])
                    + abs(ap[2] - ep[2])
                    + abs(ap[3] - ep[3])
                )
    return total / count


@dataclass
class GoldenReport:
    """The structured outcome of a golden-frame verification run."""

    total: int
    matched: int
    mismatched: list[dict] = field(default_factory=list)
    missing: list[str] = field(default_factory=list)
    ok: bool = True

    def to_dict(self) -> dict[str, Any]:
        """Serialize every field for JSON-compatible rendering."""

        return {
            "total": self.total,
            "matched": self.matched,
            "mismatched": self.mismatched,
            "missing": self.missing,
            "ok": self.ok,
        }


def verify_frames(
    reference_dir: str | Path,
    produced_dir: str | Path,
    *,
    hash: str = "sha256",
    tolerance: float = 0.0,
) -> GoldenReport:
    """Verify ``produced_dir`` frames against a ``reference_dir`` of golden frames.

    Reference filenames are the lexicographically sorted ``frame_*.png`` files in
    ``reference_dir``. For each reference, the corresponding produced file is
    checked: a missing produced file is recorded in ``missing``; content that
    differs from the reference is recorded in ``mismatched``. When
    ``tolerance > 0`` a perceptual pass replaces the exact digest comparison,
    matching when the mean absolute RGBA difference is ``<= tolerance``.

    Args:
        reference_dir: Directory holding the golden ``frame_*.png`` files.
        produced_dir: Directory holding the newly-produced frames.
        hash: Hash algorithm name used for the exact-mode digests (default
            ``"sha256"``). Only used when ``tolerance == 0``.
        tolerance: When ``> 0``, engage the Pillow perceptual comparison with
            this maximum mean absolute RGBA difference; otherwise require exact
            content equality by digest.

    Returns:
        A :class:`GoldenReport` whose ``ok`` is ``True`` only when every
        reference has a matching produced frame and nothing is missing.
    """

    reference = Path(reference_dir)
    produced = Path(produced_dir)

    total = 0
    matched = 0
    mismatched: list[dict] = []
    missing: list[str] = []

    ref_frames = sorted(reference.glob("frame_*.png")) if reference.is_dir() else []

    for ref_path in ref_frames:
        frame_name = ref_path.name
        total += 1
        produced_path = produced / frame_name
        if not produced_path.is_file():
            missing.append(frame_name)
            continue

        if tolerance > 0:
            difference = _mean_abs_diff_rgba(produced_path, ref_path)
            if difference <= tolerance:
                matched += 1
                continue
            mismatched.append(
                {
                    "frame": frame_name,
                    "expected_hash": _file_hash(ref_path, hash_name=hash),
                    "actual_hash": _file_hash(produced_path, hash_name=hash),
                    "difference": round(difference, 6),
                }
            )
        else:
            expected_hash = _file_hash(ref_path, hash_name=hash)
            actual_hash = _file_hash(produced_path, hash_name=hash)
            if expected_hash == actual_hash:
                matched += 1
            else:
                mismatched.append(
                    {
                        "frame": frame_name,
                        "expected_hash": expected_hash,
                        "actual_hash": actual_hash,
                    }
                )

    ok = len(mismatched) == 0 and len(missing) == 0
    return GoldenReport(
        total=total,
        matched=matched,
        mismatched=mismatched,
        missing=missing,
        ok=ok,
    )