"""Generate an original ten-second educational audio bed."""

from __future__ import annotations

import math
import wave
from pathlib import Path


def _sample(index: int, sample_rate: int, duration: float) -> tuple[float, float]:
    time = index / sample_rate
    pulse = 0.5 + 0.5 * math.sin(2 * math.pi * time / 2.5)
    chord = math.sin(2 * math.pi * 261.63 * time) * 0.10
    shimmer = math.sin(2 * math.pi * 523.25 * time) * (0.03 + pulse * 0.025)
    water = math.sin(2 * math.pi * (900 + 260 * pulse) * time) * 0.012
    envelope = min(1.0, time / 0.04, max(0.0, (duration - time) / 0.18))
    return (chord + shimmer + water) * envelope, (chord + shimmer * 1.05 - water) * envelope


def generate_bed(output_path: str | Path, duration_seconds: float = 10.0, sample_rate: int = 48000) -> Path:
    if duration_seconds <= 0 or sample_rate <= 0:
        raise ValueError("duration_seconds and sample_rate must be positive")
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    frames = int(round(duration_seconds * sample_rate))
    peak = max(max(abs(value) for value in _sample(i, sample_rate, duration_seconds)) for i in range(frames))
    gain = (10 ** (-1 / 20)) / peak if peak else 1.0
    with wave.open(str(output), "wb") as audio:
        audio.setnchannels(2)
        audio.setsampwidth(2)
        audio.setframerate(sample_rate)
        chunk = bytearray()
        for index in range(frames):
            left, right = _sample(index, sample_rate, duration_seconds)
            for value in (left, right):
                chunk.extend(max(-32767, min(32767, int(value * gain * 32767))).to_bytes(2, "little", signed=True))
            if len(chunk) >= 16384:
                audio.writeframes(chunk)
                chunk.clear()
        if chunk:
            audio.writeframes(chunk)
    return output
