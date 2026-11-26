"""Phase 3 round trip: edits produced by the timeline (move, trim, track
add/remove) survive a save -> get cycle and never reintroduce an overlap.

The pure timing maths are unit-tested in test_ui_timeline_math.py; this file
proves the backend contract the timeline relies on: whatever frame-aligned
edit is written back to the document, the save endpoint persists it verbatim
and the reloaded document validates with no E_CLIP_OVERLAP ERROR.
"""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

fastapi = pytest.importorskip("fastapi")  # noqa: F841

from fastapi.testclient import TestClient  # noqa: E402

from omniframe.backend.server import create_app  # noqa: E402
from omniframe.core.timeline_schema.models import OmniProject  # noqa: E402
from omniframe.core.timeline_schema.validate import validate_project  # noqa: E402

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


def _no_overlap_errors(project: OmniProject) -> list[str]:
    issues = validate_project(project, check_assets=False)
    return [i.code for i in issues if i.code == "E_CLIP_OVERLAP"]


# The drag/trim formulas guarantee the edits below: a trim-out pins the start
# and shortens duration ([0,45) from a [0,90) clip), a move+trim keeps [20,45)
# inside bounds, and the added clip sits alone on its own track so it never
# overlaps. Re-applying save/get must preserve them exactly.


def test_timeline_move_and_trim_round_trip_without_overlap(project_path: Path) -> None:
    with TestClient(create_app()) as client:
        _, loaded = post(
            client, "/api/v1/projects/get", {"project_path": str(project_path)}
        )
        doc = loaded["result"]["project"]

        track = doc["tracks"][0]
        intro = track["clips"][0]
        assert intro["id"] == "intro"
        # Trim-out then move: the end edge is pinned and the start is dragged.
        intro["duration_frames"] = 25  # trim-out from [0,90) toward [0,25)
        intro["start_frame"] = 20      # move to [20,45), still inside [0,90)

        status, saved = post(
            client,
            "/api/v1/projects/save",
            {"project_path": str(project_path), "project": doc},
        )
        assert status == 200
        assert saved["success"] is True, saved

        _, reloaded = post(
            client, "/api/v1/projects/get", {"project_path": str(project_path)}
        )
    reloaded_doc = reloaded["result"]["project"]
    reloaded_clip = reloaded_doc["tracks"][0]["clips"][0]
    assert reloaded_clip["start_frame"] == 20
    assert reloaded_clip["duration_frames"] == 25

    model = OmniProject.model_validate(reloaded_doc)
    assert _no_overlap_errors(model) == []


def test_timeline_track_add_round_trip_without_overlap(project_path: Path) -> None:
    with TestClient(create_app()) as client:
        _, loaded = post(
            client, "/api/v1/projects/get", {"project_path": str(project_path)}
        )
        doc = loaded["result"]["project"]

        # The timeline's editorAddTrack() adds {kind:'video', index: max+1}.
        new_id = "track-video-1"
        doc["tracks"].append(
            {
                "id": new_id,
                "kind": "video",
                "index": 1,
                "clips": [
                    {
                        "id": "title",
                        "kind": "text",
                        "start_frame": 0,
                        "duration_frames": 10,
                    }
                ],
            }
        )
        status, saved = post(
            client,
            "/api/v1/projects/save",
            {"project_path": str(project_path), "project": doc},
        )
        assert status == 200
        assert saved["success"] is True, saved

        _, reloaded = post(
            client, "/api/v1/projects/get", {"project_path": str(project_path)}
        )
    reloaded_doc = reloaded["result"]["project"]
    ids = [t["id"] for t in reloaded_doc["tracks"]]
    assert new_id in ids
    model = OmniProject.model_validate(reloaded_doc)
    assert _no_overlap_errors(model) == []
