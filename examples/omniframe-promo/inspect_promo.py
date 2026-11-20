"""Inspect rendered promo media and build a labeled contact sheet."""

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
    except TypeError:  # pragma: no cover - old Pillow fallback
        return ImageFont.load_default()


def _sample_paths(frame_dir: Path, count: int = 8) -> list[Path]:
    paths = sorted(frame_dir.glob("frame_*.png"))
    if not paths:
        raise FileNotFoundError(f"No PNG frames found in {frame_dir}")
    if len(paths) <= count:
        return paths
    indices = [round(index * (len(paths) - 1) / (count - 1)) for index in range(count)]
    return [paths[index] for index in indices]


def build_contact_sheet(
    frame_dir: str | Path,
    output_path: str | Path,
    *,
    columns: int = 4,
    count: int = 8,
) -> Path:
    """Build a 4×2 sheet of labeled 320×180 frame thumbnails."""

    if columns < 1:
        raise ValueError("columns must be >= 1")
    selected = _sample_paths(Path(frame_dir), count=count)
    thumb_width, thumb_height, label_height = 320, 180, 20
    rows = (len(selected) + columns - 1) // columns
    sheet = Image.new("RGB", (columns * thumb_width, rows * (thumb_height + label_height)), "#070B16")
    draw = ImageDraw.Draw(sheet)
    for index, path in enumerate(selected):
        with Image.open(path) as source:
            thumbnail = ImageOps.fit(source.convert("RGB"), (thumb_width, thumb_height))
        x = (index % columns) * thumb_width
        y = (index // columns) * (thumb_height + label_height)
        sheet.paste(thumbnail, (x, y))
        draw.rectangle((x, y + thumb_height, x + thumb_width, y + thumb_height + label_height), fill="#0D1528")
        draw.text((x + 8, y + thumb_height + 3), path.stem, font=_font(12), fill="#B8C8E5")
    target = Path(output_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(target)
    return target


def _probe(video_path: Path) -> dict[str, Any]:
    ffprobe = shutil.which("ffprobe")
    if not ffprobe:
        return {"ok": False, "warning": "ffprobe is unavailable on PATH."}
    command = [
        ffprobe,
        "-v",
        "error",
        "-show_streams",
        "-show_format",
        "-of",
        "json",
        str(video_path),
    ]
    try:
        completed = subprocess.run(command, check=True, capture_output=True, text=True)
        payload = json.loads(completed.stdout)
    except (OSError, subprocess.CalledProcessError, json.JSONDecodeError) as exc:
        return {"ok": False, "warning": f"ffprobe failed: {exc}"}

    streams = payload.get("streams", [])
    video = next((stream for stream in streams if stream.get("codec_type") == "video"), {})
    audio = next((stream for stream in streams if stream.get("codec_type") == "audio"), {})
    rate_text = video.get("r_frame_rate", "0/1")
    try:
        frame_rate = float(Fraction(rate_text))
    except (ValueError, ZeroDivisionError):
        frame_rate = None
    format_info = payload.get("format", {})
    return {
        "ok": True,
        "duration_seconds": float(format_info.get("duration", 0.0)),
        "format": format_info.get("format_name"),
        "video": {
            "codec": video.get("codec_name"),
            "width": video.get("width"),
            "height": video.get("height"),
            "frame_rate": frame_rate,
            "frames": video.get("nb_frames"),
        },
        "audio": {
            "codec": audio.get("codec_name"),
            "sample_rate": audio.get("sample_rate"),
            "channels": audio.get("channels"),
        },
    }


def inspect_delivery(video_path: str | Path, output_dir: str | Path) -> dict[str, Any]:
    """Probe the final MP4 and write contact-sheet/inspection artifacts."""

    video = Path(video_path)
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    report: dict[str, Any] = {"video_path": str(video), "exists": video.exists()}
    frames = video.parent / "frames"
    if frames.exists():
        try:
            report["contact_sheet"] = str(build_contact_sheet(frames, output / "contact-sheet.png"))
        except FileNotFoundError as exc:
            report["contact_sheet_warning"] = str(exc)
    report["probe"] = _probe(video)
    path = output / "inspection.json"
    path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    report["inspection_path"] = str(path)
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description="Inspect the OmniFrame promo delivery.")
    parser.add_argument("--video", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    report = inspect_delivery(args.video, args.output_dir)
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0 if report.get("probe", {}).get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
