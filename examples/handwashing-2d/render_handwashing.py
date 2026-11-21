"""Render the original Bengali handwashing education animation."""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageFont

PROJECT_ROOT = Path(__file__).resolve().parent
REPO_ROOT = PROJECT_ROOT.parents[1]
if str(REPO_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "src"))

from omniframe.core.timeline_schema.io import load_project
from omniframe.engines.compositor.compositor import Compositor


BG = "#FFF7E8"
INK = "#25324A"
SKIN = "#C98262"
SKIN_LIGHT = "#F1B18B"
BLUE = "#4B77BE"
TEAL = "#55B7A8"
YELLOW = "#FFD166"
PINK = "#F28C8C"


def _font(size: int):
    for candidate in (Path("C:/Windows/Fonts/Nirmala.ttc"), Path("C:/Windows/Fonts/Nirmala.ttf"), Path("C:/Windows/Fonts/NirmalaUI.ttf")): 
        if candidate.exists():
            return ImageFont.truetype(str(candidate), size)
    try:
        return ImageFont.load_default(size=size)
    except TypeError:  # pragma: no cover
        return ImageFont.load_default()


def _text(draw: ImageDraw.ImageDraw, xy: tuple[int, int], value: str, size: int, fill: str = INK, anchor: str | None = None) -> None:
    draw.text(xy, value, font=_font(size), fill=fill, anchor=anchor)


def _ease(t: float) -> float:
    t = max(0.0, min(1.0, t))
    return 1 - (1 - t) ** 3


def _scene_progress(frame: int, start: int, end: int) -> float:
    return (frame - start) / max(1, end - start - 1)


def _background(image: Image.Image, color: str) -> ImageDraw.ImageDraw:
    draw = ImageDraw.Draw(image, "RGBA")
    draw.rectangle((0, 0, image.width, image.height), fill=color)
    draw.ellipse((1180, -260, 2140, 700), fill=(255, 255, 255, 90))
    draw.line((0, 880, image.width, 880), fill=(37, 50, 74, 70), width=4)
    return draw


def _person(draw: ImageDraw.ImageDraw, x: int, y: int, scale: float, shirt: str, hair: str, *, teacher: bool = False, wave: bool = False) -> None:
    s = scale
    # body, neck, head, hair, eyes, smile, and simple arms create a generic original character.
    draw.rounded_rectangle((x - int(100 * s), y + int(140 * s), x + int(100 * s), y + int(430 * s)), radius=int(58 * s), fill=shirt)
    draw.rectangle((x - int(24 * s), y + int(92 * s), x + int(24 * s), y + int(170 * s)), fill=SKIN)
    draw.ellipse((x - int(105 * s), y - int(120 * s), x + int(105 * s), y + int(120 * s)), fill=SKIN_LIGHT, outline=INK, width=max(2, int(5 * s)))
    draw.pieslice((x - int(110 * s), y - int(130 * s), x + int(110 * s), y + int(85 * s)), 180, 360, fill=hair)
    eye_y = y - int(15 * s)
    draw.ellipse((x - int(45 * s), eye_y, x - int(25 * s), eye_y + int(22 * s)), fill=INK)
    draw.ellipse((x + int(25 * s), eye_y, x + int(45 * s), eye_y + int(22 * s)), fill=INK)
    draw.arc((x - int(42 * s), y + int(20 * s), x + int(42 * s), y + int(76 * s)), 10, 170, fill=INK, width=max(2, int(5 * s)))
    arm_y = y + int(205 * s)
    if wave:
        draw.line((x + int(78 * s), arm_y, x + int(210 * s), arm_y - int(100 * s)), fill=SKIN, width=max(12, int(28 * s)))
        draw.ellipse((x + int(190 * s), arm_y - int(125 * s), x + int(235 * s), arm_y - int(80 * s)), fill=SKIN_LIGHT, outline=INK, width=max(2, int(4 * s)))
    else:
        draw.line((x - int(78 * s), arm_y, x - int(190 * s), arm_y + int(55 * s)), fill=SKIN, width=max(12, int(28 * s)))
        draw.line((x + int(78 * s), arm_y, x + int(190 * s), arm_y + int(55 * s)), fill=SKIN, width=max(12, int(28 * s)))
    if teacher:
        draw.rounded_rectangle((x - int(132 * s), y + int(130 * s), x + int(132 * s), y + int(175 * s)), radius=12, outline=YELLOW, width=max(3, int(8 * s)))


def _germ(draw: ImageDraw.ImageDraw, x: int, y: int, r: int, phase: float) -> None:
    points = []
    for index in range(16):
        angle = index * math.pi / 8
        radius = r + (12 if index % 2 == 0 else 0)
        points.append((x + math.cos(angle + phase) * radius, y + math.sin(angle + phase) * radius))
    draw.polygon(points, fill=TEAL, outline=INK)
    draw.ellipse((x - 9, y - 9, x + 9, y + 9), fill=PINK)


def _draw_problem(image: Image.Image, frame: int) -> None:
    draw = _background(image, BG)
    t = _ease(_scene_progress(frame, 0, 60))
    _person(draw, 650, 470, 1.1, BLUE, "#2F3B52")
    draw.ellipse((220, 650, 550, 780), fill="#F7D48B", outline=INK, width=5)
    _text(draw, (380, 130), "খাওয়ার আগে?", 62, INK)
    _text(draw, (380, 215), "একটু থামুন!", 34, PINK)
    for index in range(3):
        _germ(draw, 860 + index * 105, 620 - int(40 * t), 42, index + t)
    draw.rounded_rectangle((1030, 340, 1660, 520), radius=28, fill="#FFFFFF", outline=INK, width=4)
    _text(draw, (1080, 390), "হাত পরিষ্কার", 34, TEAL)
    _text(draw, (1080, 445), "থাকলে স্বাস্থ্য ভালো!", 30, INK)


def _draw_steps(image: Image.Image, frame: int) -> None:
    draw = _background(image, "#E8F7FF")
    t = max(0.0, min(1.0, _scene_progress(frame, 60, 150)))
    _person(draw, 360, 440, 0.9, "#F0A35C", "#4D3155", teacher=True, wave=True)
    _text(draw, (180, 110), "হাত ধোয়ার ৩ ধাপ", 58, INK)
    cards = [("১", "পানি", BLUE), ("২", "সাবান", TEAL), ("৩", "২০ সেকেন্ড", PINK)]
    for index, (number, label, color) in enumerate(cards):
        x = 700 + index * 370
        slide = min(1.0, max(0.0, t * 3 - index * 0.55))
        x += int((1 - _ease(slide)) * 90)
        draw.rounded_rectangle((x, 320, x + 300, 690), radius=28, fill="#FFFFFF", outline=color, width=8)
        draw.ellipse((x + 95, 370, x + 205, 480), fill=color)
        _text(draw, (x + 150, 425), number, 48, "#FFFFFF", anchor="mm")
        _text(draw, (x + 150, 565), label, 34, INK, anchor="mm")
    _text(draw, (430, 790), "সহজ নিয়ম, সুস্থ জীবন", 34, TEAL)


def _draw_handwash(image: Image.Image, frame: int) -> None:
    draw = _background(image, "#DDF6FF")
    t = max(0.0, min(1.0, _scene_progress(frame, 150, 240)))
    _text(draw, (180, 110), "ভালোভাবে হাত ধুয়ে নিন", 54, INK)
    # faucet and basin
    draw.rounded_rectangle((760, 700, 1160, 790), radius=24, fill="#7CA9C9", outline=INK, width=5)
    draw.arc((820, 430, 1100, 760), 180, 360, fill="#7CA9C9", width=36)
    draw.line((960, 570, 960, 700), fill="#7CA9C9", width=36)
    # hands moving together under water
    hand_x = 960 + int(math.sin(t * math.pi * 4) * 90)
    draw.ellipse((hand_x - 90, 620, hand_x + 20, 720), fill=SKIN_LIGHT, outline=INK, width=4)
    draw.ellipse((hand_x - 20, 620, hand_x + 90, 720), fill=SKIN_LIGHT, outline=INK, width=4)
    for index in range(8):
        bx = hand_x - 120 + ((index * 83 + frame * 5) % 240)
        by = 480 + ((index * 47 + frame * 3) % 150)
        radius = 12 + index % 3 * 5
        draw.ellipse((bx - radius, by - radius, bx + radius, by + radius), outline="#FFFFFF", width=4)
    # timer ring
    draw.ellipse((1390, 390, 1690, 690), outline=TEAL, width=18)
    draw.arc((1390, 390, 1690, 690), -90, -90 + int(360 * t), fill=PINK, width=18)
    _text(draw, (1540, 540), str(max(1, int(20 * t))), 68, INK, anchor="mm")
    _text(draw, (1540, 620), "সেকেন্ড", 28, INK, anchor="mm")


def _draw_reminder(image: Image.Image, frame: int) -> None:
    draw = _background(image, "#FFF1D6")
    t = _ease(_scene_progress(frame, 240, 300))
    _person(draw, 610, 430, 0.9, BLUE, "#2F3B52", wave=True)
    _person(draw, 1260, 390, 0.95, "#F0A35C", "#4D3155", teacher=True, wave=True)
    _text(draw, (960, 140), "পরিষ্কার হাত, সুস্থ জীবন", 60, INK, anchor="ma")
    _text(draw, (960, 230), "খাওয়ার আগে হাত ধুয়ে নিন", 34, TEAL, anchor="ma")
    for index in range(6):
        angle = index * math.pi / 3
        x = 960 + int(math.cos(angle) * 170 * t)
        y = 520 + int(math.sin(angle) * 120 * t)
        draw.line((960, 520, x, y), fill=YELLOW, width=8)
    draw.ellipse((938, 498, 982, 542), fill=YELLOW)


def draw_frame(scene: str, frame: int, width: int, height: int) -> Image.Image:
    image = Image.new("RGBA", (width, height), BG)
    if scene == "problem":
        _draw_problem(image, frame)
    elif scene == "steps":
        _draw_steps(image, frame)
    elif scene == "handwash":
        _draw_handwash(image, frame)
    else:
        _draw_reminder(image, frame)
    return image


def _scene_for_frame(frame: int) -> str:
    if frame < 60:
        return "problem"
    if frame < 150:
        return "steps"
    if frame < 240:
        return "handwash"
    return "reminder"


def render_handwashing(project_path: str | Path, output_dir: str | Path, *, frame_step: int = 1) -> dict[str, Any]:
    if frame_step < 1:
        raise ValueError("frame_step must be >= 1")
    project = load_project(project_path)
    output = Path(output_dir)
    frame_dir = output / "frames"
    frame_dir.mkdir(parents=True, exist_ok=True)
    paths: list[Path] = []
    for frame in range(0, project.meta.duration_frames, frame_step):
        image = draw_frame(_scene_for_frame(frame), frame, project.meta.width, project.meta.height)
        target = frame_dir / f"frame_{len(paths):06d}.png"
        image.save(target)
        paths.append(target)
    fps = project.meta.fps / frame_step
    compositor = Compositor(overwrite=True)
    video_only = output / "handwashing-2d-video-only.mp4"
    compositor.frames_to_video(paths, video_only, fps=fps, preset="h264")
    from generate_audio import generate_bed

    audio = output / "handwashing-bed.wav"
    generate_bed(audio, duration_seconds=project.meta.duration_frames / project.meta.fps)
    final = output / "handwashing-2d.mp4"
    compositor.mux_audio(video_only, audio, final, preset="h264", video_copy=False)
    report = {
        "fallback_backend": "pillow-cartoon2d",
        "frame_count": len(paths),
        "width": project.meta.width,
        "height": project.meta.height,
        "fps": fps,
        "duration_seconds": len(paths) / fps,
        "video_path": str(final),
        "audio_path": str(audio),
    }
    (output / "render-report.json").write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Render the Bengali handwashing 2D animation.")
    parser.add_argument("--project", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--frame-step", type=int, default=1)
    args = parser.parse_args()
    print(json.dumps(render_handwashing(args.project, args.output, frame_step=args.frame_step), indent=2, ensure_ascii=False))
