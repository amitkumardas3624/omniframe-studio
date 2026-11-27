"""Phase 5 compare gate: same frame numbers from reference and current output.

The gate exists to stop a template shipping on "JSON, lint and render passed"
evidence. It pairs the current output with a reference (a video, or a directory of
reference PNGs) at identical frame numbers, measures the pixel gap, and refuses a
pass verdict until every mechanic from root SKILL.md section 7A is attested -
either matched, or declared an explicit engine limit.
"""

from __future__ import annotations

import base64
import shutil
from pathlib import Path

import pytest

fastapi = pytest.importorskip("fastapi")  # noqa: F841

from fastapi.testclient import TestClient  # noqa: E402

from omniframe.backend.server import create_app  # noqa: E402
from omniframe.core.errors import ValidationError  # noqa: E402
from omniframe.engines.compositor import ffmpeg_available  # noqa: E402
from omniframe.engines.compositor.compare import (  # noqa: E402
    CHECKLIST,
    mean_abs_diff,
    parse_frames,
    reference_frame_index,
    render_report_markdown,
    verdict,
)

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


def _png_bytes(client, project_path: Path, frame: int) -> bytes:
    status, payload = _post(
        client,
        "/api/v1/preview/frame",
        {"project_path": str(project_path), "frame": frame, "backend": "stub"},
    )
    assert status == 200 and payload["success"] is True, payload
    return base64.b64decode(payload["result"]["image_base64"])


# -- checklist -------------------------------------------------------------


def test_checklist_covers_the_seven_a_mechanics() -> None:
    ids = [item.id for item in CHECKLIST]
    assert len(ids) == 5
    assert len(set(ids)) == 5
    joined = " ".join(item.label.lower() for item in CHECKLIST)
    for word in ("background", "density", "particle", "3d", "outro"):
        assert word in joined, word


def test_every_checklist_item_starts_unchecked() -> None:
    assert all(item.status == "unchecked" for item in CHECKLIST)


# -- frame list ------------------------------------------------------------


def test_parse_frames_dedupes_and_sorts() -> None:
    assert parse_frames("24, 0, 12", 90) == [0, 12, 24]
    assert parse_frames("0", 90) == [0]


@pytest.mark.parametrize("text", ["", "   ", "abc", "0,90", "1,,2"])
def test_parse_frames_rejects_non_numeric(text: str) -> None:
    with pytest.raises(ValidationError):
        parse_frames(text, 90)


def test_parse_frames_rejects_out_of_range() -> None:
    with pytest.raises(ValidationError):
        parse_frames("0, 90", 90)
    with pytest.raises(ValidationError):
        parse_frames("-1", 90)


# -- fps mapping -----------------------------------------------------------


def test_reference_index_maps_by_time_not_by_count() -> None:
    assert reference_frame_index(10, project_fps=30.0, reference_fps=30.0) == 10
    assert reference_frame_index(10, project_fps=30.0, reference_fps=60.0) == 20
    assert reference_frame_index(10, project_fps=60.0, reference_fps=30.0) == 5


# -- verdict ---------------------------------------------------------------


def _rows(**statuses: str) -> list[dict]:
    return [{"id": item.id, "status": statuses.get(item.id, "unchecked")} for item in CHECKLIST]


def test_verdict_needs_every_item_attested() -> None:
    report = verdict(_rows())
    assert report["ok"] is False
    assert len(report["pending"]) == 5
    assert report["gaps"] == []


def test_verdict_passes_on_match_and_limit() -> None:
    rows = _rows(**{item.id: "match" for item in CHECKLIST})
    assert verdict(rows)["ok"] is True

    # A limit is only a pass when it names what remains (7A item 3).
    rows = _rows(**{item.id: "limit" for item in CHECKLIST})
    for row in rows:
        row["note"] = "engine cannot do this yet"
    assert verdict(rows)["ok"] is True


def test_verdict_fails_on_any_gap() -> None:
    rows = _rows(**{item.id: "match" for item in CHECKLIST})
    rows[0]["status"] = "gap"
    report = verdict(rows)
    assert report["ok"] is False
    assert report["gaps"] == [rows[0]["id"]]


def test_verdict_rejects_a_concrete_gap_hidden_without_note() -> None:
    rows = _rows(**{item.id: "limit" for item in CHECKLIST})
    report = verdict(rows)
    assert report["ok"] is False
    assert report["limits_without_note"]


# -- pixel diff ------------------------------------------------------------


def test_mean_abs_diff_is_zero_for_the_same_bytes(tmp_path: Path) -> None:
    pytest.importorskip("PIL", reason="Pillow not installed")
    from PIL import Image

    path = tmp_path / "a.png"
    Image.new("RGBA", (8, 8), (10, 20, 30, 255)).save(path)
    assert mean_abs_diff(path, path) == 0.0


def test_mean_abs_diff_reports_a_red_blue_gap(tmp_path: Path) -> None:
    pytest.importorskip("PIL", reason="Pillow not installed")
    from PIL import Image

    red = tmp_path / "red.png"
    blue = tmp_path / "blue.png"
    Image.new("RGBA", (4, 4), (255, 0, 0, 255)).save(red)
    Image.new("RGBA", (4, 4), (0, 0, 255, 255)).save(blue)
    # 255 + 255 over the RGBA channels, mean 127.5
    assert round(mean_abs_diff(red, blue), 3) == 127.5


# -- report ----------------------------------------------------------------


def test_report_states_frames_statuses_and_limits() -> None:
    rows = _rows(**{item.id: "match" for item in CHECKLIST})
    rows[4]["status"] = "limit"
    rows[4]["note"] = "no outro hierarchy beyond two cards"
    payload = {
        "project_path": "examples/motion-reel-template/project.json",
        "reference_kind": "video",
        "reference_path": "refs/motion-reel.mp4",
        "frames": [
            {"frame": 0, "diff": 12.5, "reference_frame": 0},
            {"frame": 120, "diff": 8.25, "reference_frame": 240},
        ],
        "checklist": rows,
        "verdict": verdict(rows),
    }
    text = render_report_markdown(payload)
    for needle in ("frame 0", "frame 120", "12.5", "8.25", "limit", "not expressible"):
        assert needle in text.lower(), needle


# -- endpoint --------------------------------------------------------------


def test_compare_without_reference_still_returns_current_frames(project_path: Path) -> None:
    with TestClient(create_app()) as client:
        status, payload = _post(
            client,
            "/api/v1/compare/frames",
            {"project_path": str(project_path), "frames": [0, 12], "backend": "stub"},
        )

    assert status == 200
    assert payload["success"] is True, payload
    result = payload["result"]
    assert result["reference_supplied"] is False
    assert [row["frame"] for row in result["frames"]] == [0, 12]
    assert all(row["current"] for row in result["frames"])
    assert all(row["reference"] is None for row in result["frames"])
    assert result["verdict"]["ok"] is False


def test_compare_against_identical_reference_frames_is_zero_diff(
    project_path: Path, tmp_path: Path
) -> None:
    reference_dir = tmp_path / "reference"
    reference_dir.mkdir()
    with TestClient(create_app()) as client:
        for frame in (0, 12):
            png = _png_bytes(client, project_path, frame)
            (reference_dir / f"frame_{frame:05d}.png").write_bytes(png)
        status, payload = _post(
            client,
            "/api/v1/compare/frames",
            {
                "project_path": str(project_path),
                "frames": [0, 12],
                "reference_frames_dir": str(reference_dir),
                "backend": "stub",
            },
        )

    assert status == 200
    result = payload["result"]
    assert result["reference_supplied"] is True
    assert result["reference_kind"] == "frames"
    for row in result["frames"]:
        assert row["reference"], row
        assert row["diff"] == 0.0


def test_compare_rejects_out_of_range_frame(project_path: Path) -> None:
    with TestClient(create_app()) as client:
        status, payload = _post(
            client,
            "/api/v1/compare/frames",
            {"project_path": str(project_path), "frames": [90], "backend": "stub"},
        )

    assert status == 200
    assert payload["success"] is False
    assert payload["error_code"] == "E_VALIDATION"


def test_report_endpoint_writes_the_gate(project_path: Path, tmp_path: Path) -> None:
    out = tmp_path / "gate.md"
    rows = _rows(**{item.id: "match" for item in CHECKLIST})
    body = {
        "project_path": str(project_path),
        "output_path": str(out),
        "compare": {
            "reference_kind": None,
            "reference_path": None,
            "frames": [{"frame": 0, "diff": None, "reference_frame": None}],
            "checklist": rows,
            "verdict": verdict(rows),
        },
    }
    with TestClient(create_app()) as client:
        status, payload = _post(client, "/api/v1/compare/report", body)
    assert status == 200
    assert payload["success"] is True, payload
    assert Path(payload["result"]["report_path"]).exists()
    assert "compare gate" in out.read_text(encoding="utf-8").lower()


@pytest.mark.skipif(not ffmpeg_available(), reason="ffmpeg is not available")
def test_compare_against_a_reference_video_maps_by_instant(
    project_path: Path, tmp_path: Path
) -> None:
    """A 60 fps reference is sampled at twice the project frame, by time."""

    import subprocess

    video = tmp_path / "reference.mp4"
    subprocess.run(
        [
            "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
            "-f", "lavfi", "-i", "color=c=red:s=64x64:d=1:r=60",
            "-frames:v", "60",
            "-pix_fmt", "yuv420p",
            str(video),
        ],
        check=True,
    )
    with TestClient(create_app()) as client:
        status, payload = _post(
            client,
            "/api/v1/compare/frames",
            {
                "project_path": str(project_path),
                "frames": [10],
                "reference_video": str(video),
                "width": 64,
                "height": 64,
                "backend": "stub",
            },
        )

    assert status == 200
    assert payload["success"] is True, payload
    row = payload["result"]["frames"][0]
    assert row["reference"], row
    assert row["reference_frame"] == 20
    assert row["diff"] is not None
    assert row["diff"] > 0