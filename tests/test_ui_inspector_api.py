"""Phase 4 inspector contracts: in-memory preview of params edits + surfaced schema errors.

The Phase 2 preview endpoint loaded the project from disk, so an in-memory
params edit could never reach the rendered PNG. Phase 4 lets the preview
request carry an optional in-memory document and adds an inspector validate
endpoint that reports structured schema issues (e.g. E_CLIP_OVERLAP) for an
arbitrary in-memory document.
"""

from __future__ import annotations

import base64
import shutil
from pathlib import Path

import pytest

fastapi = pytest.importorskip("fastapi")  # noqa: F841

from fastapi.testclient import TestClient  # noqa: E402

from omniframe.backend.server import create_app  # noqa: E402

SOURCE = (
    Path(__file__).resolve().parents[1] / "examples" / "code-explainer" / "project.json"
)


@pytest.fixture()
def project_path(tmp_path: Path) -> Path:
    target = tmp_path / "project.json"
    shutil.copyfile(SOURCE, target)
    return target


def _post(client, url: str, body: dict) -> tuple[int, dict]:
    response = client.post(url, json=body)
    return response.status_code, response.json()


def _load_document(client, project_path: Path) -> dict:
    status, payload = _post(
        client, "/api/v1/projects/get", {"project_path": str(project_path)}
    )
    assert status == 200 and payload["success"] is True, payload
    return payload["result"]["project"]


def _png(payload: dict) -> bytes:
    assert payload["success"] is True, payload
    return base64.b64decode(payload["result"]["image_base64"])


def test_preview_uses_in_memory_params_when_project_supplied(project_path: Path) -> None:
    """An in-memory params edit must change the rendered frame vs disk state."""
    with TestClient(create_app()) as client:
        document = _load_document(client, project_path)
        document["tracks"][0]["clips"][0]["code"]["params"] = {"text": "PHASE4-VISIBLE"}

        disk = _png(client.post(
            "/api/v1/preview/frame",
            json={"project_path": str(project_path), "frame": 0, "backend": "stub"},
        ).json())
        edited = _png(client.post(
            "/api/v1/preview/frame",
            json={
                "project_path": str(project_path),
                "frame": 0,
                "backend": "stub",
                "project": document,
            },
        ).json())

    assert edited != disk, "params edit had no effect on the preview frame"


def test_preview_rejects_invalid_in_memory_document(project_path: Path) -> None:
    """A malformed in-memory doc must surface a schema error, never render."""
    bad = {"schema_version": "1.0", "tracks": "not-a-list"}
    with TestClient(create_app()) as client:
        status, payload = _post(
            client,
            "/api/v1/preview/frame",
            {"project_path": str(project_path), "frame": 3, "project": bad},
        )

    assert status == 200
    assert payload["success"] is False
    assert payload["error_code"] == "E_VALIDATION"


def test_inspector_validate_reports_overlap(project_path: Path) -> None:
    """An overlapping in-memory doc surfaces E_CLIP_OVERLAP as an ERROR issue."""
    with TestClient(create_app()) as client:
        document = _load_document(client, project_path)
        track = document["tracks"][0]
        track["clips"].append(
            {
                "id": "clash",
                "kind": "video",
                "start_frame": 10,
                "duration_frames": 10,
                "source": "missing-but-schema-valid.mp4",
            }
        )
        status, payload = _post(client, "/api/v1/inspector/validate", {"project": document})

    assert status == 200
    assert payload["success"] is True, payload
    assert payload["result"]["ok"] is False
    assert "E_CLIP_OVERLAP" in payload["result"]["codes"]
    errors = [i for i in payload["result"]["issues"] if i["severity"] == "error"]
    assert any(i["code"] == "E_CLIP_OVERLAP" for i in errors)


def test_inspector_validate_passes_clean_document(project_path: Path) -> None:
    with TestClient(create_app()) as client:
        document = _load_document(client, project_path)
        status, payload = _post(client, "/api/v1/inspector/validate", {"project": document})

    assert status == 200
    assert payload["success"] is True
    assert payload["result"]["ok"] is True
