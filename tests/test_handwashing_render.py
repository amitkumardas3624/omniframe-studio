import importlib.util
import sys
import wave
from pathlib import Path

HANDWASHING_AUDIO = Path("examples/handwashing-2d/generate_audio.py").resolve()
audio_spec = importlib.util.spec_from_file_location(
    "omniframe_handwashing_generate_audio", HANDWASHING_AUDIO
)
assert audio_spec is not None and audio_spec.loader is not None
handwashing_audio = importlib.util.module_from_spec(audio_spec)
audio_spec.loader.exec_module(handwashing_audio)
generate_bed = handwashing_audio.generate_bed

HANDWASHING_RENDER = Path("examples/handwashing-2d/render_handwashing.py").resolve()
render_spec = importlib.util.spec_from_file_location(
    "omniframe_handwashing_render", HANDWASHING_RENDER
)
assert render_spec is not None and render_spec.loader is not None
handwashing_render = importlib.util.module_from_spec(render_spec)
render_spec.loader.exec_module(handwashing_render)
draw_frame = handwashing_render.draw_frame
render_handwashing = handwashing_render.render_handwashing


def test_human_like_frame_is_deterministic_and_full_hd():
    first = draw_frame("problem", 30, 1920, 1080)
    second = draw_frame("problem", 30, 1920, 1080)
    assert first.size == (1920, 1080)
    assert first.mode == "RGBA"
    assert first.tobytes() == second.tobytes()


def test_audio_is_stereo_48khz_and_ten_seconds(tmp_path):
    output = generate_bed(tmp_path / "bed.wav")
    with wave.open(str(output), "rb") as audio:
        assert audio.getnchannels() == 2
        assert audio.getframerate() == 48000
        assert audio.getnframes() == 48000 * 10


def test_smoke_render_returns_ten_sample_frames(tmp_path, monkeypatch):
    monkeypatch.setitem(sys.modules, "generate_audio", handwashing_audio)
    report = render_handwashing(
        Path("examples/handwashing-2d/project.json"),
        tmp_path,
        frame_step=30,
    )
    assert report["frame_count"] == 10
    assert report["width"] == 1920
    assert Path(report["video_path"]).exists()
    assert Path(report["audio_path"]).exists()
