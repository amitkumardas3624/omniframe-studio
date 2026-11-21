from pathlib import Path

from omniframe.core.timeline_schema.io import load_project

PROJECT = Path("examples/omniframe-promo/project.json")


def test_promo_project_has_expected_canvas_and_duration():
    project = load_project(PROJECT)
    assert project.meta.width == 1920
    assert project.meta.height == 1080
    assert project.meta.fps == 30
    assert project.meta.duration_frames == 900


def test_promo_project_has_original_storyboard_clip_boundaries():
    project = load_project(PROJECT)
    code_clips = [
        clip for track in project.tracks for clip in track.clips if track.kind.value == "code_scene"
    ]
    assert [(clip.id, clip.start_frame, clip.duration_frames) for clip in code_clips] == [
        ("hook", 0, 90),
        ("prompt", 90, 150),
        ("structure", 240, 180),
        ("render", 420, 210),
        ("inspect", 630, 150),
        ("cta", 780, 120),
    ]
    accent_clips = [
        clip for track in project.tracks for clip in track.clips if clip.id == "signal-accent"
    ]
    assert len(accent_clips) == 1
    assert accent_clips[0].start_frame == 420
    assert accent_clips[0].duration_frames == 210
    assert accent_clips[0].cartoon is not None


def test_asset_manifest_states_no_reference_downloads():
    manifest = Path("examples/omniframe-promo/ASSET_LICENSES.md").read_text(encoding="utf-8")
    assert "YouTube reference" in manifest
    assert "Not used" in manifest
    assert "procedural" in manifest.lower()
