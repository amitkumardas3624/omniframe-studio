"""Tests for the universal timeline schema, validation and translators."""

from __future__ import annotations

import pytest

from omniframe.core.errors import SchemaError, ValidationError
from omniframe.core.timeline_schema.io import load_project, save_project
from omniframe.core.timeline_schema.models import (
    Clip,
    ClipKind,
    Easing,
    EasingKind,
    Keyframe,
    OmniProject,
    ProjectMeta,
    Track,
    TrackKind,
)
from omniframe.core.timeline_schema.schema import project_json_schema
from omniframe.core.timeline_schema.translate import (
    available_translators,
    frames_to_timecode,
    get_translator,
    parse_time_to_frames,
)
from omniframe.core.timeline_schema.validate import summarize, validate_document, validate_project


def make_project() -> OmniProject:
    project = OmniProject(meta=ProjectMeta(name="demo", fps=30, width=1920, height=1080))
    project.tracks.append(
        Track(
            id="v1",
            name="Video 1",
            kind=TrackKind.VIDEO,
            index=0,
            clips=[
                Clip(
                    id="c1",
                    name="Intro",
                    kind=ClipKind.VIDEO,
                    start_frame=0,
                    duration_frames=60,
                    source="assets/intro.mp4",
                ),
                Clip(
                    id="c2",
                    name="Outro",
                    kind=ClipKind.VIDEO,
                    start_frame=60,
                    duration_frames=30,
                    source="assets/outro.mp4",
                ),
            ],
        )
    )
    return project


class TestModels:
    def test_total_frames_follows_content(self):
        project = make_project()
        assert project.total_frames() == 90

    def test_timecode(self):
        project = make_project()
        assert project.timecode(0) == "00:00:00:00"
        assert project.timecode(30) == "00:00:01:00"

    def test_clip_frames(self):
        clip = make_project().clip("c1")
        assert clip is not None
        assert clip.end_frame == 60
        assert clip.contains(59)
        assert not clip.contains(60)

    def test_easing_curves(self):
        assert Easing(kind=EasingKind.LINEAR).apply(0.5) == pytest.approx(0.5)
        assert Easing(kind=EasingKind.EASE_IN).apply(0.5) == pytest.approx(0.25)
        assert Easing(kind=EasingKind.HOLD).apply(0.9) == pytest.approx(0.0)
        assert Easing(kind=EasingKind.STEP, steps=4).apply(0.6) == pytest.approx(0.5)

    def test_transform_to_css(self):
        project = make_project()
        clip = project.clip("c1")
        assert clip is not None
        assert "translate" in clip.transform.to_css()


class TestValidation:
    def test_clean_project_has_no_errors(self):
        issues = validate_project(make_project(), check_assets=False)
        assert [i for i in issues if i.is_error] == []

    def test_overlapping_clips_are_reported(self):
        project = make_project()
        project.tracks[0].clips[1].start_frame = 30
        issues = validate_project(project, check_assets=False)
        codes = {i.code for i in issues}
        assert "E_CLIP_OVERLAP" in codes

    def test_keyframe_outside_clip_is_reported(self):
        project = make_project()
        clip = project.tracks[0].clips[0]
        clip.keyframes = [Keyframe(frame=999, values={"x": 1})]
        issues = validate_project(project, check_assets=False)
        assert "E_KEYFRAME_OUT_OF_RANGE" in {i.code for i in issues}

    def test_code_scene_without_payload_is_reported(self):
        project = make_project()
        project.tracks[0].clips[0].kind = ClipKind.CODE_SCENE
        project.tracks[0].clips[0].source = None
        issues = validate_project(project, check_assets=False)
        assert "E_CODE_SCENE_MISSING" in {i.code for i in issues}

    def test_document_validation_reports_schema_errors(self):
        issues = validate_document({"meta": {"fps": -1}})
        assert issues
        assert any(i.code == "E_SCHEMA_FIELD" for i in issues)

    def test_summary_shape(self):
        report = summarize(validate_project(make_project(), check_assets=False))
        assert "counts" in report and "issues" in report
        assert report["ok"] is True


class TestIo:
    def test_round_trip_json(self, tmp_path):
        project = make_project()
        path = save_project(project, tmp_path / "project.json")
        loaded = load_project(path)
        assert loaded.meta.name == "demo"
        assert len(loaded.tracks[0].clips) == 2

    def test_missing_file_raises(self, tmp_path):
        with pytest.raises(SchemaError):
            load_project(tmp_path / "nope.json")

    def test_invalid_json_raises(self, tmp_path):
        bad = tmp_path / "bad.json"
        bad.write_text("{not json", encoding="utf-8")
        with pytest.raises(SchemaError):
            load_project(bad)


class TestSchema:
    def test_json_schema_is_valid_json(self):
        schema = project_json_schema()
        assert schema["title"] == "OmniProject"
        assert "properties" in schema
        assert schema["$schema"].startswith("https://json-schema.org/")


class TestTranslators:
    def test_registry_contains_expected_translators(self):
        names = {entry["name"] for entry in available_translators()}
        assert {"fcpxml", "edl", "capcut_draft", "ae_manifest"} <= names

    def test_unknown_translator_raises(self):
        with pytest.raises(KeyError):
            get_translator("does-not-exist")

    def test_fcpxml_round_trip(self):
        project = make_project()
        xml = get_translator("fcpxml").from_universal(project)
        assert "fcpxml" in xml
        parsed = get_translator("fcpxml").to_universal(xml)
        assert parsed.meta.fps == pytest.approx(30.0)
        assert parsed.tracks
        assert len(parsed.tracks[0].clips) == 2

    def test_edl_export_contains_timecodes(self):
        edl = get_translator("edl").from_universal(make_project())
        assert "TITLE:" in edl
        assert "00:00:00:00" in edl

    def test_capcut_draft_round_trip(self):
        project = make_project()
        draft = get_translator("capcut_draft").from_universal(project)
        assert "materials" in draft and "tracks" in draft
        parsed = get_translator("capcut_draft").to_universal(draft)
        assert parsed.tracks

    def test_ae_manifest_export(self):
        manifest = get_translator("ae_manifest").from_universal(make_project())
        assert manifest["composition"]["fps"] == 30
        assert manifest["layers"]

    def test_time_parsing(self):
        assert parse_time_to_frames("00:00:01:00", 30) == 30
        assert parse_time_to_frames("1s", 30) == 30
        assert parse_time_to_frames("100f", 30) == 100
        assert frames_to_timecode(90, 30) == "00:00:03:00"
