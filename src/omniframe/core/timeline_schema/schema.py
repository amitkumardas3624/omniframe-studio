"""JSON Schema export for the OmniFrame project format.

The schema is generated from the pydantic models so it can never drift from
the implementation.  ``omniframe schema --out schemas/project.schema.json``
writes the artefact consumed by editors, MCP clients and agents.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from .models import SCHEMA_VERSION, OmniProject

SCHEMA_ID = "https://omniframe.dev/schemas/project.schema.json"


def project_json_schema() -> dict[str, Any]:
    """Return the JSON Schema (draft 2020-12) for :class:`OmniProject`."""

    schema = OmniProject.model_json_schema(mode="serialization")
    schema["$schema"] = "https://json-schema.org/draft/2020-12/schema"
    schema["$id"] = SCHEMA_ID
    schema["title"] = "OmniProject"
    schema["description"] = (
        "Vendor-neutral OmniFrame Studio project document. Every engine and bridge "
        "reads and writes this format."
    )
    schema["x-schema-version"] = SCHEMA_VERSION
    schema["x-omniframe"] = {
        "kind": "project",
        "schema_version": SCHEMA_VERSION,
    }
    return schema


def export_schema(path: str | os.PathLike[str]) -> Path:
    """Write the project schema to ``path`` and return the written path."""

    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        json.dumps(project_json_schema(), indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return target
