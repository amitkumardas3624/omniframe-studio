import importlib.util
import wave
from pathlib import Path

PROMO_AUDIO = Path("examples/omniframe-promo/generate_audio.py").resolve()
spec = importlib.util.spec_from_file_location("omniframe_promo_generate_audio", PROMO_AUDIO)
assert spec is not None and spec.loader is not None
promo_audio = importlib.util.module_from_spec(spec)
spec.loader.exec_module(promo_audio)
generate_bed = promo_audio.generate_bed


def test_generated_bed_is_stereo_48khz_and_30_seconds(tmp_path):
    output = generate_bed(tmp_path / "bed.wav")
    with wave.open(str(output), "rb") as audio:
        assert audio.getnchannels() == 2
        assert audio.getframerate() == 48000
        assert audio.getnframes() == 48000 * 30


def test_generated_bed_is_not_silent(tmp_path):
    output = generate_bed(tmp_path / "bed.wav")
    with wave.open(str(output), "rb") as audio:
        payload = audio.readframes(audio.getnframes())
    assert any(byte != 0 for byte in payload)
