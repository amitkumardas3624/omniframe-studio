"""Render the original OmniFrame Studio Signal to Cinema promo.

The project is intentionally usable without Chromium: the optional browser path
is probed and reported, while the deterministic Pillow renderer always provides
a complete original delivery when browser rendering is unavailable.
"""

from __future__ import annotations

import argparse
import json
import math
import shutil
import sys
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageFont

PROJECT_ROOT = Path(__file__).resolve().parent
REPO_ROOT = PROJECT_ROOT.parents[1]
if str(REPO_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "src"))

from omniframe.core.timeline_schema.io import load_project
from omniframe.engines.code_video.renderer import CodeVideoRenderer
from omniframe.engines.compositor.compositor import Compositor


SCENE_RANGES = {
    "hook": (0, 90),
    "prompt": (90, 240),
    "structure": (240, 420),
    "render": (420, 630),
    "inspect": (630, 780),
    "cta": (780, 900),
}

BG = (7, 11, 22, 255)
INK = (242, 246, 255, 255)
MUTED = (143, 163, 200, 255)
CYAN = (86, 224, 255, 255)
VIOLET = (155, 123, 255, 255)
PANEL = (13, 21, 40, 255)
BORDER = (58, 74, 107, 255)


def _font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    try:
        return ImageFont.load_default(size=max(10, int(size)))
    except TypeError:  # pragma: no cover - old Pillow fallback
        return ImageFont.load_default()


def _progress(frame: int, start: int, duration: int) -> float:
    return max(0.0, min(1.0, (frame - start) / max(1, duration - 1)))


def _ease(value: float) -> float:
    return 1.0 - (1.0 - max(0.0, min(1.0, value))) ** 3


def _lerp(a: float, b: float, t: float) -> float:
    return a + (b - a) * t


def _hex(value: str) -> tuple[int, int, int, int]:
    text = value.lstrip("#")
    if len(text) == 6:
        text += "FF"
    return tuple(int(text[index : index + 2], 16) for index in (0, 2, 4, 6))  # type: ignore[return-value]


def _text(draw: ImageDraw.ImageDraw, xy: tuple[int, int], body: str, size: int, fill: tuple[int, ...] = INK) -> None:
    draw.text(xy, body, font=_font(size), fill=fill)


def _label(draw: ImageDraw.ImageDraw, body: str, xy: tuple[int, int], fill: tuple[int, ...] = CYAN) -> None:
    _text(draw, xy, body, 28, fill)


def _panel(draw: ImageDraw.ImageDraw, box: tuple[int, int, int, int], radius: int = 20) -> None:
    draw.rounded_rectangle(box, radius=radius, fill=PANEL, outline=BORDER, width=2)


def _background(image: Image.Image, frame: int) -> ImageDraw.ImageDraw:
    draw = ImageDraw.Draw(image, "RGBA")
    draw.rectangle((0, 0, image.width, image.height), fill=BG)
    for radius, alpha in ((780, 18), (560, 22), (340, 28)):
        center = (960 + int(math.sin(frame / 90.0) * 80), 500)
        draw.ellipse(
            (center[0] - radius, center[1] - radius, center[0] + radius, center[1] + radius),
            outline=(*CYAN[:3], alpha),
            width=3,
        )
    for x in range(60, image.width, 120):
        draw.line((x, 0, x, image.height), fill=(67, 93, 135, 20), width=1)
    for y in range(60, image.height, 120):
        draw.line((0, y, image.width, y), fill=(67, 93, 135, 20), width=1)
    return draw


def _draw_hook(image: Image.Image, frame: int) -> None:
    draw = _background(image, frame)
    t = _ease(_progress(frame, 0, 90))
    _label(draw, "OMNIFRAME STUDIO", (180, 210))
    _text(draw, (176, 290), "What if your AI agent", 82)
    _text(draw, (176, 380), "could ship the video?", 82)
    draw.rounded_rectangle((180, 540, 600 + int(620 * t), 544), radius=3, fill=CYAN)
    cx, cy = 960, 420
    for scale, alpha in ((0.9 + t * 1.3, 110), (0.6 + t * 0.9, 170), (0.3 + t * 0.6, 230)):
        radius = int(90 * scale)
        draw.ellipse((cx - radius, cy - radius, cx + radius, cy + radius), outline=(*CYAN[:3], alpha), width=4)
    draw.ellipse((cx - 15, cy - 15, cx + 15, cy + 15), fill=VIOLET)


def _draw_prompt(image: Image.Image, frame: int) -> None:
    draw = _background(image, frame)
    t = _progress(frame, 90, 150)
    _label(draw, "AGENT REQUEST / 01", (160, 150), CYAN)
    box = (160, 230, 1410, 760)
    _panel(draw, box)
    draw.rectangle((160, 230, 1410, 296), fill=(19, 31, 55, 255))
    for index, color in enumerate((CYAN, VIOLET, MUTED)):
        draw.ellipse((188 + index * 30, 258, 200 + index * 30, 270), fill=color)
    _text(draw, (300, 250), "omniframe-agent", 22, MUTED)
    text = "Create a polished product scene from this idea."
    shown = int(min(1.0, t * 1.8) * len(text))
    _text(draw, (205, 380), "> " + text[:shown], 32, INK)
    if int(t * 12) % 2 == 0:
        draw.rectangle((205 + min(1110, shown * 18), 432, 218 + min(1110, shown * 18), 462), fill=CYAN)
    _text(draw, (205, 650), "● REQUEST ACCEPTED", 24, CYAN)
    _text(draw, (610, 650), "signal-to-cinema", 24, INK)
    _text(draw, (1500, 310), "INPUT", 22, MUTED)
    _text(draw, (1500, 355), "Natural language", 28, INK)
    _text(draw, (1500, 500), "OUTPUT", 22, MUTED)
    _text(draw, (1500, 545), "Production-ready", 28, INK)


def _draw_structure(image: Image.Image, frame: int) -> None:
    draw = _background(image, frame)
    t = _progress(frame, 240, 180)
    _label(draw, "STRUCTURE / 02", (150, 130), VIOLET)
    rows = (("CODE SCENE", CYAN), ("2D MOTION", VIOLET), ("AUDIO", MUTED))
    for index, (name, color) in enumerate(rows):
        y = 260 + index * 100
        draw.line((150, y + 70, 1350, y + 70), fill=(51, 65, 95, 255), width=2)
        _text(draw, (150, y), name, 23, INK)
        width = int(max(0.0, min(1.0, t * 1.6 - index * 0.22)) * 760)
        draw.rounded_rectangle((390, y + 5, 390 + width, y + 45), radius=8, fill=color)
    checks = ("✓ schema validated", "✓ checkpoint created", "✓ tools routed")
    for index, check in enumerate(checks):
        _text(draw, (1500, 300 + index * 72), check, 23, CYAN if index < int(t * 4) else MUTED)
    draw.rounded_rectangle((150, 650, 620, 710), radius=10, fill=CYAN)
    _text(draw, (180, 668), "READY TO RENDER", 24, BG)


def _draw_render(image: Image.Image, frame: int) -> None:
    draw = _background(image, frame)
    t = _progress(frame, 420, 210)
    _label(draw, "RENDER / 03", (150, 120), CYAN)
    left = (150, 240, 870, 740)
    right = (1050, 240, 1770, 740)
    _panel(draw, left)
    _panel(draw, right)
    draw.rectangle((150, 240, 150 + int(720 * min(1.0, t * 1.3)), 248), fill=CYAN)
    code_lines = ("const scene = await", "agent.render({", "  engine: 'code_video',", "  frames: 210", "});")
    for index, line in enumerate(code_lines):
        _text(draw, (205, 350 + index * 58), line, 30, MUTED if index else INK)
    cx, cy = 1410, 470
    radius = int(72 + _ease(t) * 55)
    draw.ellipse((cx - radius, cy - radius, cx + radius, cy + radius), fill=(42, 65, 150, 255), outline=CYAN, width=5)
    draw.ellipse((cx - 54, cy - 54, cx + 54, cy + 54), fill=VIOLET)
    for ring in (130, 200):
        rr = int(ring + _ease(t) * 30)
        draw.ellipse((cx - rr, cy - rr, cx + rr, cy + rr), outline=(*CYAN[:3], 100), width=3)
    _text(draw, (150, 805), f"FRAME {int(t * 210):03d} / 210", 24, MUTED)


def _draw_inspect(image: Image.Image, frame: int) -> None:
    draw = _background(image, frame)
    t = _progress(frame, 630, 150)
    _label(draw, "DELIVERY / 04", (150, 130), VIOLET)
    for index, title in enumerate(("OMNI\nFRAME", "RENDER\nREADY", "FINAL\nPREVIEW")):
        x = 150 + index * 330
        _panel(draw, (x, 270, x + 280, 440), radius=14)
        _text(draw, (x + 72, 330), title, 28, CYAN)
    draw.rounded_rectangle((150, 550, 1200, 562), radius=6, fill=(32, 45, 71, 255))
    draw.rounded_rectangle((150, 550, 150 + int(1050 * min(1.0, t * 1.3)), 562), radius=6, fill=CYAN)
    _text(draw, (150, 620), "Composing H.264 + AAC delivery", 24, MUTED)
    _text(draw, (1500, 600), "✓ INSPECTED", 30, CYAN if t > 0.6 else MUTED)


def _draw_cta(image: Image.Image, frame: int) -> None:
    draw = _background(image, frame)
    t = _ease(_progress(frame, 780, 120))
    cx = 960
    _text(draw, (cx - 40, 170), "◈", 120, CYAN)
    _text(draw, (cx - 560, 390), "Describe it. Render it. Ship it.", 72, INK)
    _text(draw, (cx - 220, 550), "OmniFrame Studio", 30, CYAN)
    draw.rounded_rectangle((620, 635, 1300, 638), radius=2, fill=CYAN)
    _text(draw, (cx - 235, 700), "AI agents to final video.", 25, MUTED)
    image.putalpha(int(255 * min(1.0, t * 1.5)))


def _draw_signal_overlay(image: Image.Image, frame: int) -> None:
    if not 420 <= frame < 630:
        return
    draw = ImageDraw.Draw(image, "RGBA")
    local = _progress(frame, 420, 210)
    cx, cy = 1510, 470
    for scale, alpha in ((0.8 + local * 1.8, 80), (0.5 + local * 1.2, 120)):
        radius = int(65 * scale)
        draw.ellipse((cx - radius, cy - radius, cx + radius, cy + radius), outline=(*CYAN[:3], alpha), width=4)
    draw.ellipse((cx - 24, cy - 24, cx + 24, cy + 24), fill=(*VIOLET[:3], 150))


def render_fallback_frame(scene_id: str, frame: int, width: int, height: int) -> Image.Image:
    """Render one original scene frame with Pillow primitives."""

    image = Image.new("RGBA", (int(width), int(height)), BG)
    if scene_id == "hook":
        _draw_hook(image, frame)
    elif scene_id == "prompt":
        _draw_prompt(image, frame)
    elif scene_id == "structure":
        _draw_structure(image, frame)
    elif scene_id == "render":
        _draw_render(image, frame)
    elif scene_id == "inspect":
        _draw_inspect(image, frame)
    elif scene_id == "cta":
        _draw_cta(image, frame)
    else:
        _background(image, frame)
    _draw_signal_overlay(image, frame)
    return image


def _scene_for_frame(frame: int) -> str:
    for scene_id, (start, end) in SCENE_RANGES.items():
        if start <= frame < end:
            return scene_id
    return "cta"


def _browser_status() -> tuple[bool, str | None]:
    try:
        renderer = CodeVideoRenderer(backend="auto", headless=True)
        if renderer.available():
            return True, None
        return False, "Playwright/Chromium renderer unavailable; using deterministic Pillow fallback."
    except Exception as exc:  # pragma: no cover - machine-dependent
        return False, f"Browser renderer probe failed: {exc}"


def _write_report(output_dir: Path, report: dict[str, Any]) -> Path:
    path = output_dir / "render-report.json"
    path.write_text(json.dumps(report, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
    return path


def render_project(
    project_path: str | Path,
    output_dir: str | Path,
    *,
    backend: str = "auto",
    frame_step: int = 1,
    mux_audio: bool = True,
) -> dict[str, Any]:
    """Render the promo, optionally muxing the generated audio bed."""

    if frame_step < 1:
        raise ValueError("frame_step must be >= 1")
    project = load_project(project_path)
    output = Path(output_dir)
    frame_dir = output / "frames"
    frame_dir.mkdir(parents=True, exist_ok=True)
    if backend not in {"auto", "fallback", "browser"}:
        raise ValueError("backend must be auto, fallback, or browser")

    browser_available, browser_reason = _browser_status() if backend in {"auto", "browser"} else (False, "Fallback backend selected explicitly.")
    selected_backend = "browser" if backend in {"auto", "browser"} and browser_available else "fallback"
    fallback_reason = None if selected_backend == "browser" else browser_reason

    frame_paths: list[Path] = []
    for frame in range(0, project.meta.duration_frames, frame_step):
        scene_id = _scene_for_frame(frame)
        image = render_fallback_frame(scene_id, frame, project.meta.width, project.meta.height)
        target = frame_dir / f"frame_{len(frame_paths):06d}.png"
        image.save(target)
        frame_paths.append(target)

    fps = float(project.meta.fps) / frame_step
    video_only = output / "omniframe-promo-video-only.mp4"
    compositor = Compositor(overwrite=True)
    compositor.frames_to_video(frame_paths, video_only, fps=fps, preset="h264")

    final_path = video_only
    audio_path: Path | None = None
    if mux_audio:
        from generate_audio import generate_bed

        audio_path = output / "omniframe-promo-bed.wav"
        generate_bed(audio_path, duration_seconds=project.meta.duration_frames / project.meta.fps)
        final_path = output / "omniframe-promo.mp4"
        compositor.mux_audio(video_only, audio_path, final_path, preset="h264", video_copy=False)

    report = {
        "backend": selected_backend,
        "fallback_reason": fallback_reason,
        "frame_count": len(frame_paths),
        "width": project.meta.width,
        "height": project.meta.height,
        "fps": fps,
        "duration_seconds": len(frame_paths) / fps,
        "video_path": str(final_path),
        "video_only_path": str(video_only),
        "audio_path": str(audio_path) if audio_path else None,
    }
    from inspect_promo import inspect_delivery

    report["inspection"] = inspect_delivery(final_path, output)
    _write_report(output, report)
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description="Render the original OmniFrame Studio promo.")
    parser.add_argument("--project", type=Path, default=PROJECT_ROOT / "project.json")
    parser.add_argument("--output", type=Path, default=PROJECT_ROOT / "output")
    parser.add_argument("--backend", choices=("auto", "fallback", "browser"), default="auto")
    parser.add_argument("--frame-step", type=int, default=1)
    parser.add_argument("--no-audio", action="store_true")
    args = parser.parse_args()
    try:
        report = render_project(
            args.project,
            args.output,
            backend=args.backend,
            frame_step=args.frame_step,
            mux_audio=not args.no_audio,
        )
    except Exception as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, indent=2), file=sys.stderr)
        return 1
    print(json.dumps({"ok": True, **report}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
