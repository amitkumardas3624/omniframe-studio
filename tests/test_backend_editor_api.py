"""Phase 1 editor contracts: project get/save and frame-accurate preview."""

from __future__ import annotations

import base64
import json
import shutil
from pathlib import Path

import pytest

fastapi = pytest.importorskip("fastapi")  # noqa: F841

from fastapi.testclient import TestClient  # noqa: E402

from omniframe.backend.server import create_app  # noqa: E402
from omniframe.engines.code_video import CodeVideoRenderer  # noqa: E402

SOURCE = (
    Path(__file__).resolve().parents[1] / "examples" / "code-explainer" / "project.json"
)


@pytest.fixture()
def project_path(tmp_path: Path) -> Path:
    target = tmp_path / "project.json"
    shutil.copyfile(SOURCE, target)
    return target


def post(client, url: str, body: dict) -> tuple[int, dict]:
    response = client.post(url, json=body)
    return response.status_code, response.json()


def test_projects_get_returns_the_document(project_path: Path) -> None:
    with TestClient(create_app()) as client:
        status, payload = post(
            client, "/api/v1/projects/get", {"project_path": str(project_path)}
        )

    assert status == 200
    assert payload["success"] is True
    project = payload["result"]["project"]
    assert project["meta"]["fps"] == 30
    assert project["tracks"]


def test_projects_save_round_trips_an_edit(project_path: Path) -> None:
    with TestClient(create_app()) as client:
        _, loaded = post(
            client, "/api/v1/projects/get", {"project_path": str(project_path)}
        )
        document = loaded["result"]["project"]
        document["meta"]["fps"] = 24
        status, saved = post(
            client,
            "/api/v1/projects/save",
            {"project_path": str(project_path), "project": document},
        )
        assert status == 200
        assert saved["success"] is True

        _, reloaded = post(
            client, "/api/v1/projects/get", {"project_path": str(project_path)}
        )

    assert reloaded["result"]["project"]["meta"]["fps"] == 24
    assert json.loads(project_path.read_text(encoding="utf-8"))["meta"]["fps"] == 24


def test_projects_save_rejects_invalid_document(project_path: Path) -> None:
    before = project_path.read_bytes()
    with TestClient(create_app()) as client:
        status, payload = post(
            client,
            "/api/v1/projects/save",
            {
                "project_path": str(project_path),
                "project": {"schema_version": "1.0", "tracks": "not-a-list"},
            },
        )

    assert status == 200
    assert payload["success"] is False
    assert payload["error_code"] == "E_VALIDATION"
    assert project_path.read_bytes() == before


def test_preview_frame_is_pure_and_reports_exact_time(project_path: Path) -> None:
    body = {
        "project_path": str(project_path),
        "frame": 12,
        "backend": "stub",
    }
    with TestClient(create_app()) as client:
        status, first = post(client, "/api/v1/preview/frame", body)
        assert status == 200
        assert first["success"] is True, first
        _, second = post(client, "/api/v1/preview/frame", body)

    result = first["result"]
    assert result["frame"] == 12
    assert result["fps"] == 30.0
    assert result["t"] == 0.4
    assert result["verification_level"] == "import_tested"
    # The stub backend emits a warning by design; there must be no errors.
    assert not [issue for issue in result["issues"] if issue.startswith("ERROR:")]
    png = base64.b64decode(result["image_base64"])
    assert png.startswith(b"\x89PNG\r\n\x1a\n")
    assert second["result"]["image_base64"] == result["image_base64"]


@pytest.mark.parametrize(
    ("frame", "expected_status"),
    [(-1, 422), (90, 200)],
)
def test_preview_frame_rejects_out_of_range(
    project_path: Path, frame: int, expected_status: int
) -> None:
    with TestClient(create_app()) as client:
        status, payload = post(
            client,
            "/api/v1/preview/frame",
            {"project_path": str(project_path), "frame": frame, "backend": "stub"},
        )

    assert status == expected_status
    if expected_status == 200:
        assert payload["success"] is False
        assert payload["error_code"] == "E_VALIDATION"


@pytest.mark.render
def test_preview_frame_with_real_backend_is_render_tested(project_path: Path) -> None:
    if not CodeVideoRenderer(backend="playwright").available():
        pytest.skip("Chromium is not available")
    with TestClient(create_app()) as client:
        status, payload = post(
            client,
            "/api/v1/preview/frame",
            {"project_path": str(project_path), "frame": 12, "backend": "playwright"},
        )

    assert status == 200
    assert payload["success"] is True, payload
    assert payload["result"]["verification_level"] == "render_tested"
    assert payload["result"]["frame"] == 12


def test_preview_frame_accepts_explicit_dimensions(project_path: Path) -> None:
    with TestClient(create_app()) as client:
        status, payload = post(
            client,
            "/api/v1/preview/frame",
            {
                "project_path": str(project_path),
                "frame": 3,
                "width": 320,
                "height": 180,
                "backend": "stub",
            },
        )

    assert status == 200
    assert payload["success"] is True, payload
    assert payload["result"]["width"] == 320
    assert payload["result"]["height"] == 180
