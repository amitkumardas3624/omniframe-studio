import sys
from pathlib import Path

from PIL import Image

PROMO_DIR = Path("examples/omniframe-promo").resolve()
sys.path.insert(0, str(PROMO_DIR))
from render_promo import render_fallback_frame, render_project  # noqa: E402


def test_fallback_frame_has_delivery_dimensions():
    image = render_fallback_frame("hook", 45, 1920, 1080)
    assert image.size == (1920, 1080)
    assert image.mode == "RGBA"


def test_fallback_scene_is_deterministic():
    first = render_fallback_frame("structure", 300, 1920, 1080)
    second = render_fallback_frame("structure", 300, 1920, 1080)
    assert first.tobytes() == second.tobytes()


def test_render_report_contains_backend_and_frame_count(tmp_path: Path):
    report = render_project(
        Path("examples/omniframe-promo/project.json"),
        tmp_path,
        backend="fallback",
        frame_step=30,
        mux_audio=False,
    )
    assert report["backend"] == "fallback"
    assert report["frame_count"] == 30
    assert Path(report["video_path"]).exists()
    assert Image.open(tmp_path / "frames" / "frame_000000.png").size == (1920, 1080)
