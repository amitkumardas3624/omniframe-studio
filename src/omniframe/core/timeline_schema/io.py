"""Reading and writing OmniFrame project documents.

JSON and YAML are both supported; the format is chosen by file extension, with
YAML as the fallback for unknown extensions.  Saving always produces stable,
diff-friendly output (2-space indent, keys in declaration order).
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from ..errors import SchemaError
from .models import OmniProject


def load_document(path: str | os.PathLike[str]) -> dict[str, Any]:
    """Load a raw project document from JSON or YAML."""

    target = Path(path)
    if not target.exists():
        raise SchemaError(f"Project file not found: {target}")

    raw = target.read_text(encoding="utf-8")
    suffix = target.suffix.lower()

    if suffix in {".yaml", ".yml"}:
        try:
            import yaml
        except ImportError as exc:  # pragma: no cover - PyYAML is a hard dependency
            raise SchemaError("PyYAML is required to read YAML projects.") from exc
        try:
            data = yaml.safe_load(raw)
        except Exception as exc:
            raise SchemaError(f"Invalid YAML in {target}: {exc}") from exc
    else:
        try:
            data = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise SchemaError(f"Invalid JSON in {target}: {exc}") from exc

    if not isinstance(data, dict):
        raise SchemaError(f"Project document must be a mapping, got {type(data).__name__}.")
    return data


def load_project(path: str | os.PathLike[str]) -> OmniProject:
    """Load and validate the shape of a project document."""

    document = load_document(path)
    try:
        return OmniProject.model_validate(document)
    except Exception as exc:
        raise SchemaError(f"Invalid project document {path}: {exc}") from exc


def save_project(project: OmniProject, path: str | os.PathLike[str]) -> Path:
    """Write a project to disk as JSON or YAML."""

    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    document = project.model_dump(mode="json", exclude_none=False)

    if target.suffix.lower() in {".yaml", ".yml"}:
        try:
            import yaml
        except ImportError as exc:  # pragma: no cover
            raise SchemaError("PyYAML is required to write YAML projects.") from exc
        target.write_text(
            yaml.safe_dump(document, sort_keys=False, allow_unicode=True), encoding="utf-8"
        )
    else:
        target.write_text(
            json.dumps(document, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )
    return target


def dump_project(project: OmniProject) -> str:
    """Serialise a project to a JSON string (no file IO)."""

    return json.dumps(project.model_dump(mode="json"), indent=2, ensure_ascii=False)
