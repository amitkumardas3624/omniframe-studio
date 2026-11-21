"""Host-independent bridge-status + timeline-inspection contracts (Task 3 UI).

Verifies two things the phase-4 "Bridges" and "Timeline" panels depend on:

* ``GET /api/v1/bridges`` surfaces the Phase 3 ``BridgeReport`` fields the
  Bridges panel renders (installed / scripting_api / version plus a
  capabilities list carrying the capability tier badge source).
* ``POST /api/v1/projects/timeline`` returns exactly the result of
  ``omniframe.core.timeline_schema.io.load_project`` for the requested file,
  so the Timeline panel's sorted tracks/clips match the authoritative loader.

No proprietary DCC host is required. When FastAPI is missing the module is
skipped (not failed) via ``pytest.importorskip``.
"""

import json

import pytest

fastapi = pytest.importorskip("fastapi")  # noqa: F841  (skips module if missing)

from fastapi.testclient import TestClient  # noqa: E402

from omniframe.backend.server import create_app  # noqa: E402
from omniframe.core.timeline_schema.io import load_project  # noqa: E402
from omniframe.core.timeline_schema.models import (  # noqa: E402
    Clip,
    ClipKind,
    OmniProject,
    ProjectMeta,
    Track,
    TrackKind,
)

#: All capability tiers defined by the Phase 3 bridge model.
_TIERS = {"documented_api", "reverse_engineered", "ui_automation"}


def test_bridges_endpoint_surfaces_report_fields_and_tiers() -> None:
    """Every bridge carries installed/scripting_api/version + tiered caps."""
    with TestClient(create_app()) as client:
        response = client.get("/api/v1/bridges")

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["success"] is True
    bridges = payload["result"]
    assert isinstance(bridges, list)
    assert bridges, "expected at least one configured bridge"

    for bridge in bridges:
        for key in ("id", "host", "installed", "scripting_api", "version"):
            assert key in bridge, f"bridge missing field {key!r}: {bridge!r}"
        assert isinstance(bridge["installed"], bool)
        caps = bridge["capabilities"]
        assert isinstance(caps, list)
        for cap in caps:
            assert "name" in cap, f"capability missing name: {cap!r}"
            assert "tier" in cap, f"capability missing tier: {cap!r}"
            assert cap["tier"] in _TIERS, f"unexpected tier {cap['tier']!r}"


def _write_sample_project(path) -> OmniProject:
    """Write a small, self-contained OmniProject to disk and return it.

    Built from the pydantic models so it is guaranteed valid for
    ``load_project`` regardless of what example templates may or may not exist
    in the install layout.
    """
    project = OmniProject(
        meta=ProjectMeta(name="ui-timeline-sample", fps=24, duration_frames=60),
        tracks=[
            Track(
                id="v1",
                name="Video A",
                kind=TrackKind.VIDEO,
                index=1,
                clips=[
                    Clip(
                        id="clip-a",
                        name="alpha clip",
                        kind=ClipKind.VIDEO,
                        start_frame=10,
                        duration_frames=20,
                        source="assets/a.mp4",
                    )
                ],
            ),
            Track(
                id="v0",
                name="Main Video",
                kind=TrackKind.VIDEO,
                index=0,
                clips=[
                    Clip(
                        id="clip-b",
                        name="beta clip",
                        kind=ClipKind.VIDEO,
                        start_frame=0,
                        duration_frames=48,
                        source="assets/b.mp4",
                    )
                ],
            ),
        ],
    )
    path.write_text(json.dumps(project.model_dump(mode="json")), encoding="utf-8")
    return project


def test_timeline_endpoint_matches_load_project(tmp_path) -> None:
    """The timeline panel endpoint mirrors the authoritative load_project."""
    project_path = tmp_path / "sample.json"
    _write_sample_project(project_path)

    with TestClient(create_app()) as client:
        response = client.post(
            "/api/v1/projects/timeline",
            json={"project_path": str(project_path)},
        )

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["success"] is True
    assert payload["result"]["project_path"] == str(project_path)

    got = payload["result"]["project"]
    expected = load_project(str(project_path)).model_dump(mode="json")
    assert got == expected


def test_timeline_endpoint_reports_missing_project(tmp_path) -> None:
    """A nonexistent project path is surfaced as an error, not a crash."""
    missing = tmp_path / "does-not-exist.json"
    with TestClient(create_app()) as client:
        response = client.post(
            "/api/v1/projects/timeline",
            json={"project_path": str(missing)},
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["success"] is False
    assert payload["error"]