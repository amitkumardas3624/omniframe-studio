"""Build the OmniFrame Studio motion showreel with the OmniFrame platform.

Everything here goes through the platform's own engines:

* ``omniframe.engines.code_video``   renders the scene in a headless Chromium
  through Playwright, one PNG per frame, with resume support.
* ``omniframe.engines.compositor``   assembles the frames with FFmpeg
  (``build_video_from_frames`` for the motion-blur pass, ``Compositor.mux_audio``
  for the delivery mux).

The only step outside the platform is the soundtrack: the brief asks for the
Web Audio API, so the scene's own ``window.renderSoundtrack()`` is rendered
offline inside the same Chromium and the resulting WAV is handed to the
platform's compositor.

Usage
-----
    python examples/showreel/build_showreel.py --stage beats
    python examples/showreel/build_showreel.py --stage full
    python examples/showreel/build_showreel.py --stage all
"""

from __future__ import annotations

import argparse
import base64
import json
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parents[1]
if str(REPO_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "src"))

from omniframe.engines.code_video.renderer import CodeVideoRenderer  # noqa: E402
from omniframe.engines.code_video.scene import CodeScene  # noqa: E402
from omniframe.engines.compositor.compositor import Compositor  # noqa: E402
from omniframe.engines.compositor.ffmpeg import ffprobe_info, run_ffmpeg  # noqa: E402

WIDTH = 1920
HEIGHT = 1080
DURATION = 15.0
OUT_FPS = 60
SUBFRAMES = 3
RENDER_FPS = OUT_FPS * SUBFRAMES
FRAME_COUNT = int(DURATION * RENDER_FPS)  # 2700

BG = "#0C0C0D"

SCENE_JS = "window.seek(window.__OMNIFRAME_FRAME__ / window.__OMNIFRAME_FPS__);"

BOOTSTRAP = """
window.__OMNIFRAME_WAIT_FOR_READY__ = true;
(function () {
  var ready = function () { window.__OMNIFRAME_READY__ = true; };
  if (document.fonts && document.fonts.load) {
    document.fonts.load('400 176px "Archivo Black"').then(ready).catch(ready);
  } else {
    ready();
  }
})();
"""

#: three subframes per output frame, blended with ffmpeg's tmix filter.
#: weights 1 2 1 centre-weight the middle subframe; select keeps every third
#: blended frame and setpts rewrites the timestamps to the 60 fps grid.
MOTION_BLUR = (
    "tmix=frames=3:weights='1 2 1',"
    "select=not(mod(n\\,3)),"
    "setpts=N/60/TB"
)


def scene_for(html: str, *, fps: float, frames: int) -> CodeScene:
    return CodeScene(
        html=html,
        css="",
        javascript=SCENE_JS,
        bootstrap=BOOTSTRAP,
        width=WIDTH,
        height=HEIGHT,
        fps=fps,
        duration_frames=frames,
        seed=0,
        transparent=False,
        background=BG,
        settle_timeout_ms=8000,
    )


def render_frames(html: str, out_dir: Path, *, fps: float, frames: int, resume: bool) -> list[Path]:
    """Render the scene to PNG frames with the platform's code-video engine."""

    out_dir.mkdir(parents=True, exist_ok=True)
    renderer = CodeVideoRenderer(backend="playwright", headless=True)
    if not renderer.available():
        raise SystemExit("The Playwright backend is not available on this machine.")
    scene = scene_for(html, fps=fps, frames=frames)
    started = time.monotonic()
    result = renderer.render(scene, out_dir, resume=resume)
    elapsed = time.monotonic() - started
    if not result.completed or result.errors:
        for issue in result.issues[:10]:
            print(f"  issue: {issue}", file=sys.stderr)
        raise SystemExit(f"render failed: completed={result.completed} errors={len(result.errors)}")
    print(
        f"  rendered {len(result.frames)} frames at {fps:g} fps in {elapsed:.1f}s "
        f"(backend={result.backend}, level={result.verification_level})"
    )
    return list(result.frames)


def contact_sheet(frames: list[Path], target: Path, *, cols: int = 5) -> Path:
    """Build a labelled contact sheet so the beats can actually be looked at."""

    from PIL import Image, ImageDraw

    thumb_w, thumb_h = 384, 216
    label_h = 22
    rows = (len(frames) + cols - 1) // cols
    sheet = Image.new("RGB", (cols * thumb_w, rows * (thumb_h + label_h)), (18, 18, 20))
    draw = ImageDraw.Draw(sheet)
    for index, frame_path in enumerate(frames):
        with Image.open(frame_path) as image:
            thumb = image.convert("RGB").resize((thumb_w, thumb_h), Image.LANCZOS)
        x = (index % cols) * thumb_w
        y = (index // cols) * (thumb_h + label_h)
        sheet.paste(thumb, (x, y))
        draw.text((x + 6, y + thumb_h + 4), f"beat {index:02d}", fill=(190, 190, 190))
    target.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(target)
    return target


def render_soundtrack(html: str, target: Path, *, sample_rate: int = 48000) -> Path:
    """Render the scene's Web Audio soundtrack to a 16-bit PCM WAV."""

    from playwright.sync_api import sync_playwright

    args = ["--autoplay-policy=no-user-gesture-required", "--force-color-profile=srgb"]
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True, args=args)
        try:
            page = browser.new_page(viewport={"width": WIDTH, "height": HEIGHT})
            page.set_content(html, wait_until="load")
            page.evaluate(
                "() => document.fonts.load('400 176px \"Archivo Black\"').catch(() => {})"
            )
            payload = page.evaluate(
                "(args) => window.renderSoundtrack(args.rate, args.duration)",
                {"rate": sample_rate, "duration": DURATION},
            )
        finally:
            browser.close()
    if not payload:
        raise SystemExit("The scene returned no audio payload.")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(base64.b64decode(payload))
    return target


def build_motion_blurred(frames: list[Path], target: Path) -> Path:
    """Blend the subframes with ffmpeg tmix and write the 60 fps H.264 video.

    The frames are read through the image2 demuxer rather than the concat
    demuxer: a concat list whose per-file duration is 1/180s is shorter than
    the image2 demuxer's own cadence, so ffmpeg drops frames to catch up and
    the output comes out short.  The numbered sequence keeps every frame, so
    the 3 subframes blended into each output frame are exactly the ones that
    were rendered.
    """

    if not frames:
        raise SystemExit("No frames to compose.")
    target.parent.mkdir(parents=True, exist_ok=True)
    pattern = str(Path(frames[0]).parent / "frame_%06d.png")
    args = [
        "-framerate", str(RENDER_FPS),
        "-start_number", "0",
        "-i", pattern,
        "-vf", MOTION_BLUR,
        "-r", str(OUT_FPS),
        "-frames:v", str(OUT_FPS * int(DURATION)),
        "-c:v", "libx264",
        "-crf", "14",
        "-preset", "slow",
        "-pix_fmt", "yuv420p",
        str(target),
    ]
    run_ffmpeg(args)
    return target


def mux(video: Path, audio: Path, target: Path) -> Path:
    compositor = Compositor(overwrite=True)
    compositor.mux_audio(video, audio, target, preset="h264", video_copy=True)
    return target


def loop_check(frames: list[Path]) -> dict[str, object]:
    """Compare the first and the last rendered frame: they must match."""

    from PIL import Image, ImageChops

    if len(frames) < 2:
        return {"checked": False}
    with Image.open(frames[0]) as first, Image.open(frames[-1]) as last:
        a = first.convert("RGB")
        b = last.convert("RGB")
        diff = ImageChops.difference(a, b)
        bbox = diff.getbbox()
        changed = 0
        if bbox is not None:
            histogram = diff.convert("L").histogram()
            changed = sum(histogram[8:])
    return {
        "checked": True,
        "first": frames[0].name,
        "last": frames[-1].name,
        "identical": bbox is None,
        "differing_pixels": changed,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the OmniFrame motion showreel.")
    parser.add_argument("--stage", choices=("beats", "full", "all"), default="all")
    parser.add_argument("--out", type=Path, default=HERE / "output")
    parser.add_argument("--html", type=Path, default=HERE / "showreel.html")
    parser.add_argument("--no-resume", action="store_true")
    args = parser.parse_args()

    html = args.html.read_text(encoding="utf-8")
    out = args.out
    out.mkdir(parents=True, exist_ok=True)
    report: dict[str, object] = {"stage": args.stage}

    if args.stage in ("beats", "all"):
        print("[1/4] beat sheet")
        beat_frames = render_frames(
            html, out / "beats", fps=2, frames=int(DURATION * 2), resume=False
        )
        sheet = contact_sheet(beat_frames, out / "beat-sheet.png")
        print(f"  contact sheet: {sheet}")
        report["beat_sheet"] = str(sheet)
        report["beat_count"] = len(beat_frames)

    if args.stage in ("full", "all"):
        print("[2/4] full render (180 fps subframes)")
        frames = render_frames(
            html,
            out / "frames",
            fps=RENDER_FPS,
            frames=FRAME_COUNT,
            resume=not args.no_resume,
        )
        report["frame_count"] = len(frames)
        report["loop_check"] = loop_check(frames)

        print("[3/4] motion blur pass (ffmpeg tmix, 3 subframes -> 60 fps)")
        video = build_motion_blurred(frames, out / "showreel-video-only.mp4")
        report["video_only"] = str(video)

        print("[4/4] soundtrack (Web Audio) + mux")
        audio = render_soundtrack(html, out / "showreel-soundtrack.wav")
        report["audio"] = str(audio)
        final = mux(video, audio, out / "omniframe-showreel.mp4")
        report["final"] = str(final)
        report["probe"] = ffprobe_info(final)

    (out / "build-report.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False, default=str), encoding="utf-8"
    )
    print(json.dumps(report, indent=2, ensure_ascii=False, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
