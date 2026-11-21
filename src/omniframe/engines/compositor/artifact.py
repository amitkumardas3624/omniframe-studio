"""Per-delivery artifact manifests for compositor output.

Every successful compositor delivery emits a small JSON manifest next to the
produced file so the result is auditable and reproducible: it records the
output path, its SHA-256 digest and size, what produced it (tool, preset,
Python version, platform), the inputs consumed, arbitrary ``meta`` and a
timestamp.

    >>> from omniframe.engines.compositor.artifact import write_artifact_manifest
    >>> write_artifact_manifest("out/demo.mp4", tool="scale_video", preset="h264")
    {...}

The ``.manifest.json`` file is written as ``<output>.manifest.json`` (the
suffix of ``output`` is preserved and ``.manifest.json`` appended).
"""

from __future__ import annotations

import hashlib
import json
import platform
import sys
from collections.abc import Sequence
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

__all__ = ["SCHEMA_VERSION", "write_artifact_manifest"]

SCHEMA_VERSION = "1.0"
MANIFEST_KIND = "omniframe_composite_artifact"
VERIFICATION_LEVEL = "render_tested"


def _absolute(path: str | Path) -> str:
    """Return ``path`` as a normalized absolute string."""
    return str(Path(path).resolve())


def write_artifact_manifest(
    output: str | Path,
    *,
    tool: str,
    preset: str | None = None,
    meta: dict[str, Any] | None = None,
    extra_inputs: Sequence[str | Path] = (),
) -> dict[str, Any]:
    """Write a delivery artifact manifest next to ``output`` and return it.

    Args:
        output: The produced delivery file. It must already exist on disk;
            otherwise a :class:`FileNotFoundError` is raised and no manifest
            is written.
        tool: The name of the compositor method (or tool) that produced the
            artifact.
        preset: The selected export preset name, or ``None`` when the delivery
            uses no preset.
        meta: Optional free-form dictionary embedded verbatim in the manifest
            (default ``{}``).
        extra_inputs: The input files/directories consumed to produce
            ``output``. Every path is normalized to an absolute string.

    Returns:
        The manifest dictionary that was serialized to disk.

    The ``inputs`` field is the list of normalized absolute ``extra_inputs``
    with the output path itself appended unless it is already present (so an
    in-place delivery is not listed twice). Refuses to proceed (raising
    :class:`FileNotFoundError`) when ``output`` does not exist as a file.
    """
    target = Path(output)
    if not target.is_file():
        raise FileNotFoundError(
            f"Cannot write artifact manifest: output file does not exist: {target}"
        )

    digest = hashlib.sha256()
    size_bytes = 0
    with target.open("rb") as handle:
        for block in iter(lambda: handle.read(65536), b""):
            digest.update(block)
            size_bytes += len(block)

    output_abs = _absolute(target)
    inputs = [_absolute(path) for path in extra_inputs]
    if output_abs not in inputs:
        inputs.append(output_abs)

    manifest: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "kind": MANIFEST_KIND,
        "output": output_abs,
        "sha256": digest.hexdigest(),
        "size_bytes": size_bytes,
        "produced_by": {
            "tool": tool,
            "preset": preset,
            "python": platform.python_version(),
            "platform": sys.platform,
        },
        "inputs": inputs,
        "meta": dict(meta or {}),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "verification_level": VERIFICATION_LEVEL,
    }

    manifest_path = target.with_suffix(target.suffix + ".manifest.json")
    manifest_path.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return manifest