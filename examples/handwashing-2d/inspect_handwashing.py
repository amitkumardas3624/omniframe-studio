"""Build contact-sheet and ffprobe evidence for the handwashing demo."""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
from fractions import Fraction
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageFont, ImageOps


def _font(size: int):
    try:
        return ImageFont.load_default(size=size)
    except TypeError:  # pragma: no cover
        return ImageFont.load_default()


def build_contact_sheet(frame_dir: str | Path, output_path: str | Path, count: int = 8) -> Path:
    paths = sorted(Path(frame_dir).glob("frame_*.png"))
    if not paths:
        raise FileNotFoundError(f"No frames found in {frame_dir}")
    if len(paths) > count:
        paths = [paths[round(index * (len(paths) - 1) / (count - 1))] for index in range(count)]
    columns, thumb_w, thumb_h, label_h = 4, 480, 270, 30
    rows = (len(paths) + columns - 1) // columns
    sheet = Image.new("RGB", (columns * thumb_w, rows * (thumb_h + label_h)), "#FFF7E8")
    draw = ImageDraw.Draw(sheet)
    for index, path in enumerate(paths):
        with Image.open(path) as source:
            thumb = ImageOps.fit(source.convert("RGB"), (thumb_w, thumb_h))
        x = index % columns * thumb_w
        y = index // columns * (thumb_h + label_h)
        sheet.paste(thumb, (x, y))
        draw.rectangle((x, y + thumb_h, x + thumb_w, y + thumb_h + label_h), fill="#25324A")
        draw.text((x + 10, y + thumb_h + 7), path.stem, font=_font(16), fill="#FFFFFF")
    target = Path(output_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(target)
    return target


def inspect_handwashing(video_path: str | Path, output_dir: str | Path) -> dict[str, Any]:
    video = Path(video_path)
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    report: dict[str, Any] = {"video_path": str(video), "exists": video.exists()}
    report["contact_sheet"] = str(build_contact_sheet(video.parent / "frames", output / "contact-sheet.png"))
    ffprobe = shutil.which("ffprobe")
    if not ffprobe:
        report["probe"] = {"ok": False, "warning": "ffprobe is unavailable"}
    else:
        completed = subprocess.run(
            [ffprobe, "-v", "error", "-show_streams", "-show_format", "-of", "json", str(video)],
            check=True,
            capture_output=True,
            text=True,
        )
        payload = json.loads(completed.stdout)
        streams = payload.get("streams", [])
        video_stream = next(stream for stream in streams if stream.get("codec_type") == "video")
        audio_stream = next(stream for stream in streams if stream.get("codec_type") == "audio")
        report["probe"] = {
            "ok": True,
            "duration_seconds": float(payload["format"]["duration"]),
            "video": {
                "codec": video_stream.get("codec_name"),
                "width": video_stream.get("width"),
                "height": video_stream.get("height"),
                "frame_rate": float(Fraction(video_stream.get("r_frame_rate", "0/1"))),
                "frames": video_stream.get("nb_frames"),
            },
            "audio": {
                "codec": audio_stream.get("codec_name"),
                "sample_rate": audio_stream.get("sample_rate"),
                "channels": audio_stream.get("channels"),
            },
        }
    report_path = output / "inspection.json"
    report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    report["inspection_path"] = str(report_path)
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Inspect the handwashing animation delivery.")
    parser.add_argument("--video", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(inspect_handwashing(args.video, args.output), indent=2, ensure_ascii=False))
