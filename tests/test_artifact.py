"""Tests for per-delivery artifact manifests.

Covers the standalone :func:`write_artifact_manifest` schema contract directly,
and the compositor-level emission wired into the delivery methods (verified on
``scale_video`` by monkeypatching ``run_ffmpeg`` so no real FFmpeg is needed).
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from omniframe.engines.compositor.artifact import write_artifact_manifest

TOP_LEVEL_KEYS = (
    "schema_version",
    "kind",
    "output",
    "sha256",
    "size_bytes",
    "produced_by",
    "inputs",
    "meta",
    "created_at",
    "verification_level",
)
PRODUCED_BY_KEYS = ("tool", "preset", "python", "platform")


def _delivery(tmp_path) -> Path:
    output = tmp_path / "delivery.mp4"
    output.write_bytes(b"hello-world-bytes" * 64)
    return output


def test_schema_keys_and_content(tmp_path):
    output = _delivery(tmp_path)

    manifest = write_artifact_manifest(
        output, tool="scale_video", preset="h264", meta={"note": "scaled"}
    )

    for key in TOP_LEVEL_KEYS:
        assert key in manifest
    assert manifest["schema_version"] == "1.0"
    assert manifest["kind"] == "omniframe_composite_artifact"
    assert manifest["output"] == str(output.resolve())
    assert manifest["sha256"] == hashlib.sha256(output.read_bytes()).hexdigest()
    assert manifest["size_bytes"] == output.stat().st_size
    assert manifest["verification_level"] == "render_tested"
    assert manifest["meta"] == {"note": "scaled"}
    assert manifest["created_at"].endswith("+00:00") or "T" in manifest["created_at"]

    for key in PRODUCED_BY_KEYS:
        assert key in manifest["produced_by"]
    assert manifest["produced_by"]["tool"] == "scale_video"
    assert manifest["produced_by"]["preset"] == "h264"


def test_manifest_json_parses(tmp_path):
    output = _delivery(tmp_path)

    write_artifact_manifest(output, tool="concat_videos", preset="h265")

    manifest_file = output.with_suffix(output.suffix + ".manifest.json")
    assert manifest_file.is_file()
    data = json.loads(manifest_file.read_text(encoding="utf-8"))
    assert data["output"] == str(output.resolve())
    assert data["produced_by"]["tool"] == "concat_videos"


def test_inputs_include_extra_inputs_and_output(tmp_path):
    output = _delivery(tmp_path)
    source = tmp_path / "source.mp4"
    source.write_bytes(b"source-bytes")

    manifest = write_artifact_manifest(
        output, tool="mux_audio", preset="h264", extra_inputs=(source,)
    )

    expected = [str(source.resolve()), str(output.resolve())]
    assert manifest["inputs"] == expected


def test_output_deduplicated_in_inputs(tmp_path):
    output = _delivery(tmp_path)

    manifest = write_artifact_manifest(
        output, tool="scale_video", extra_inputs=(output,)
    )

    # The output passed as its own input must be listed only once.
    assert manifest["inputs"] == [str(output.resolve())]


def test_inputs_default_to_output_only(tmp_path):
    output = _delivery(tmp_path)

    manifest = write_artifact_manifest(output, tool="scale_video")

    assert manifest["inputs"] == [str(output.resolve())]


def test_missing_output_refuses(tmp_path):
    output = tmp_path / "does-not-exist.mp4"

    with pytest.raises(FileNotFoundError):
        write_artifact_manifest(output, tool="scale_video")

    # No manifest file should be produced on failure.
    assert not (output.with_suffix(output.suffix + ".manifest.json")).exists()


def test_meta_default_is_empty(tmp_path):
    output = _delivery(tmp_path)

    manifest = write_artifact_manifest(output, tool="extract_audio", preset=None)

    assert manifest["produced_by"]["preset"] is None
    assert manifest["meta"] == {}


# -- compositor-level emission ---------------------------------------


def test_scale_video_emits_manifest(tmp_path, monkeypatch):
    from omniframe.engines.compositor.compositor import Compositor

    source = tmp_path / "source.mp4"
    source.write_bytes(b"fake-video-bytes")
    output = tmp_path / "scaled.mp4"

    def fake_run_ffmpeg(args, **kwargs):
        # The final argv entry is the output target; create it so the manifest
        # emission (which requires the file to exist) succeeds.
        Path(args[-1]).write_bytes(b"scaled-output")
        return ""

    monkeypatch.setattr(
        "omniframe.engines.compositor.compositor.run_ffmpeg", fake_run_ffmpeg
    )

    result = Compositor().scale_video(source, output, width=320, height=180)

    assert result == output
    manifest_file = output.with_suffix(output.suffix + ".manifest.json")
    assert manifest_file.is_file()
    data = json.loads(manifest_file.read_text(encoding="utf-8"))
    assert data["produced_by"]["tool"] == "scale_video"
    assert data["produced_by"]["preset"] == "h264"
    assert str(source.resolve()) in data["inputs"]
    assert data["sha256"] == hashlib.sha256(output.read_bytes()).hexdigest()