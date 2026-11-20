import sys
import wave
from pathlib import Path

PROMO_DIR = Path("examples/omniframe-promo").resolve()
sys.path.insert(0, str(PROMO_DIR))
from generate_audio import generate_bed  # noqa: E402


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
