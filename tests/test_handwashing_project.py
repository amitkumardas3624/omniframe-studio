from pathlib import Path

from omniframe.core.timeline_schema.io import load_project

PROJECT = Path("examples/handwashing-2d/project.json")


def test_handwashing_project_contract():
    project = load_project(PROJECT)
    assert project.meta.width == 1920
    assert project.meta.height == 1080
    assert project.meta.fps == 30
    assert project.meta.duration_frames == 300
    clips = project.tracks[0].clips
    assert [(clip.id, clip.start_frame, clip.duration_frames) for clip in clips] == [
        ("problem", 0, 60),
        ("steps", 60, 90),
        ("handwash", 150, 90),
        ("reminder", 240, 60),
    ]


def test_handwashing_captions_and_rights_manifest():
    captions = Path("examples/handwashing-2d/captions.srt").read_text(encoding="utf-8")
    manifest = Path("examples/handwashing-2d/ASSET_LICENSES.md").read_text(encoding="utf-8")
    assert "১ পানি" in captions
    assert "৩ ২০ সেকেন্ড" in captions
    assert "Not used" in manifest
    assert "Original procedural audio" in manifest
