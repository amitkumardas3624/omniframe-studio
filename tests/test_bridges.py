"""Tests for the host-application bridges."""

from __future__ import annotations

import json

import pytest

from omniframe.bridges import (
    BRIDGES,
    AfterEffectsBridge,
    BridgeTier,
    CapCutBridge,
    DaVinciResolveBridge,
    KritaBridge,
    PremiereProBridge,
    bridge_report,
    get_bridge,
    list_bridges,
)
from omniframe.core.timeline_schema.models import (
    Clip,
    ClipKind,
    OmniProject,
    ProjectMeta,
    RenderTarget,
    Track,
    TrackKind,
)


def make_project() -> OmniProject:
    project = OmniProject(meta=ProjectMeta(name="demo", fps=30, width=1920, height=1080))
    project.render_targets.append(
        RenderTarget(id="r1", container="mp4", video_codec="h264", path="out/demo.mp4")
    )
    project.tracks.append(
        Track(
            id="v1",
            name="Video 1",
            kind=TrackKind.VIDEO,
            clips=[
                Clip(
                    id="c1",
                    name="Intro",
                    kind=ClipKind.VIDEO,
                    start_frame=0,
                    duration_frames=60,
                    source="assets/intro.mp4",
                )
            ],
        )
    )
    project.tracks.append(
        Track(
            id="a1",
            name="Audio 1",
            kind=TrackKind.AUDIO,
            clips=[
                Clip(
                    id="c2",
                    name="Voice",
                    kind=ClipKind.AUDIO,
                    start_frame=0,
                    duration_frames=60,
                    source="assets/voice.wav",
                )
            ],
        )
    )
    return project


class TestRegistry:
    def test_all_bridges_registered(self):
        assert set(BRIDGES) == {
            "premiere_pro",
            "after_effects",
            "davinci_resolve",
            "capcut",
            "krita",
        }

    def test_get_bridge(self):
        assert isinstance(get_bridge("premiere_pro"), PremiereProBridge)
        assert isinstance(get_bridge("after_effects"), AfterEffectsBridge)
        assert isinstance(get_bridge("davinci_resolve"), DaVinciResolveBridge)
        assert isinstance(get_bridge("capcut"), CapCutBridge)
        assert isinstance(get_bridge("krita"), KritaBridge)

    def test_unknown_bridge_raises(self):
        with pytest.raises(KeyError):
            get_bridge("nope")

    def test_list_bridges(self):
        entries = list_bridges()
        assert len(entries) == 5
        assert {entry["id"] for entry in entries} == set(BRIDGES)
        assert all("installed" in entry for entry in entries)


class TestDetection:
    @pytest.mark.parametrize("bridge_id", sorted(BRIDGES))
    def test_detect_never_raises(self, bridge_id):
        report = get_bridge(bridge_id).detect()
        assert report.bridge == bridge_id
        assert isinstance(report.installed, bool)
        assert report.capabilities

    @pytest.mark.parametrize("bridge_id", sorted(BRIDGES))
    def test_health_check(self, bridge_id):
        report = get_bridge(bridge_id).health_check()
        assert report["bridge"] == bridge_id
        assert "installed" in report

    @pytest.mark.parametrize("bridge_id", sorted(BRIDGES))
    def test_capabilities_have_a_valid_tier(self, bridge_id):
        for capability in get_bridge(bridge_id).capabilities():
            assert capability.tier in set(BridgeTier)

    def test_bridge_report_is_json_serialisable(self):
        json.dumps(bridge_report())


class TestGeneration:
    @pytest.mark.parametrize("bridge_id", sorted(BRIDGES))
    def test_generate_script_writes_a_file(self, tmp_path, bridge_id):
        bridge = get_bridge(bridge_id)
        result = bridge.generate_script(make_project(), tmp_path / bridge_id)
        assert result.path
        from pathlib import Path

        assert Path(result.path).exists()
        assert Path(result.path).stat().st_size > 0
        json.dumps(result.to_dict())

    def test_premiere_writes_extendscript_and_fcpxml(self, tmp_path):
        result = PremiereProBridge().generate_script(make_project(), tmp_path)
        from pathlib import Path

        script = Path(result.path).read_text(encoding="utf-8")
        assert "app.project" in script
        assert "importFiles" in script
        fcpxml = Path(result.metadata["fcpxml_path"])
        assert fcpxml.exists()
        assert "fcpxml" in fcpxml.read_text(encoding="utf-8")

    def test_after_effects_script_creates_a_comp(self, tmp_path):
        result = AfterEffectsBridge().generate_script(make_project(), tmp_path)
        from pathlib import Path

        script = Path(result.path).read_text(encoding="utf-8")
        assert "addComp" in script
        assert Path(result.metadata["manifest_path"]).exists()

    def test_resolve_script_uses_the_documented_api(self, tmp_path):
        result = DaVinciResolveBridge().generate_script(make_project(), tmp_path)
        from pathlib import Path

        script = Path(result.path).read_text(encoding="utf-8")
        assert "DaVinciResolveScript" in script
        assert Path(result.metadata["xml_path"]).exists()

    def test_capcut_draft_is_valid_json(self, tmp_path):
        result = CapCutBridge().generate_script(make_project(), tmp_path)
        from pathlib import Path

        draft = json.loads(Path(result.path).read_text(encoding="utf-8"))
        assert "materials" in draft
        assert "tracks" in draft

    def test_generated_scripts_warn_when_the_host_is_missing(self, tmp_path):
        # None of the host applications are installed on a CI machine, so the
        # bridges must still warn rather than fail.
        result = CapCutBridge().generate_script(make_project(), tmp_path)
        if not result.warnings:
            pytest.skip("CapCut is installed on this machine")
        assert any("CapCut" in warning for warning in result.warnings)


class TestInspection:
    def test_missing_target_is_reported(self, tmp_path):
        report = CapCutBridge().inspect(tmp_path / "nope")
        assert report["exists"] is False
        assert "error" in report

    def test_capcut_draft_directory_is_summarised(self, tmp_path):
        draft = tmp_path / "draft"
        draft.mkdir()
        (draft / "draft_content.json").write_text(
            json.dumps(
                {
                    "tracks": [
                        {"type": "video", "segments": [{"id": "s1"}]},
                        {"type": "audio", "segments": []},
                    ],
                    "materials": {"videos": [{"id": "m1", "path": "a.mp4"}]},
                }
            ),
            encoding="utf-8",
        )
        report = CapCutBridge().inspect(draft)
        assert report["track_count"] == 2
        assert report["material_counts"]["videos"] == 1
        assert "draft_content.json" in report["draft_files"]

    def test_premiere_probe_reports_magic_bytes(self, tmp_path):
        target = tmp_path / "project.prproj"
        target.write_bytes(b"\x00\x01Adobe Premiere Pro\x00\x02" + b"x" * 64)
        report = PremiereProBridge().inspect(target)
        assert report["exists"] is True
        assert report["magic_hex"]
        assert "Adobe Premiere Pro" in report["readable_strings"] or report["markers_found"]

    def test_krita_document_folder_lists_frames(self, tmp_path):
        folder = tmp_path / "doc"
        (folder / "frames").mkdir(parents=True)
        (folder / "frames" / "frame_000000.png").write_bytes(b"png")
        report = KritaBridge().inspect(folder)
        assert report["frame_count"] == 1
