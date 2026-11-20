"""Generate the original rights-safe OmniFrame promo music bed."""

from __future__ import annotations

import math
import wave
from pathlib import Path


NOTES = (220.0, 277.18, 329.63, 440.0)


def _sample(index: int, sample_rate: int, duration: float) -> tuple[float, float]:
    time = index / sample_rate
    beat = int(time / 0.5)
    note = NOTES[beat % len(NOTES)]
    envelope = min(1.0, time / 0.03, max(0.0, (duration - time) / 0.25))
    pulse = 0.5 + 0.5 * math.sin(2.0 * math.pi * time / 4.0)
    pad = math.sin(2.0 * math.pi * 55.0 * time) * 0.10
    arp = math.sin(2.0 * math.pi * note * time) * (0.18 + pulse * 0.05)
    harmonic = math.sin(2.0 * math.pi * note * 2.0 * time) * 0.035
    tick = math.sin(2.0 * math.pi * 8.0 * time) * 0.018
    left = (pad + arp + harmonic + tick) * envelope
    right = (pad + arp * 0.92 + harmonic * 1.08 - tick) * envelope
    return left, right


def generate_bed(
    output_path: str | Path,
    duration_seconds: float = 30.0,
    sample_rate: int = 48000,
) -> Path:
    """Write a deterministic stereo 16-bit original music bed."""

    if duration_seconds <= 0:
        raise ValueError("duration_seconds must be positive")
    if sample_rate <= 0:
        raise ValueError("sample_rate must be positive")

    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    frame_count = int(round(duration_seconds * sample_rate))
    peak = 0.0
    for index in range(frame_count):
        left, right = _sample(index, sample_rate, duration_seconds)
        peak = max(peak, abs(left), abs(right))
    gain = (10 ** (-1.0 / 20.0)) / peak if peak else 1.0

    with wave.open(str(output), "wb") as audio:
        audio.setnchannels(2)
        audio.setsampwidth(2)
        audio.setframerate(sample_rate)
        chunk = bytearray()
        for index in range(frame_count):
            left, right = _sample(index, sample_rate, duration_seconds)
            left_i = max(-32767, min(32767, int(left * gain * 32767)))
            right_i = max(-32767, min(32767, int(right * gain * 32767)))
            chunk.extend(left_i.to_bytes(2, "little", signed=True))
            chunk.extend(right_i.to_bytes(2, "little", signed=True))
            if len(chunk) >= 16384:
                audio.writeframes(chunk)
                chunk.clear()
        if chunk:
            audio.writeframes(chunk)
    return output


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Generate the original OmniFrame promo bed.")
    parser.add_argument("output", type=Path)
    parser.add_argument("--duration", type=float, default=30.0)
    args = parser.parse_args()
    print(generate_bed(args.output, duration_seconds=args.duration))
