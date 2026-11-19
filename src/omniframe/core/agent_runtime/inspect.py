"""Visual inspection helpers — the agent's eyes.

These utilities turn rendered output into artefacts a multimodal agent can
look at: contact sheets (grid of thumbnails), frame strips (horizontal
timeline), and timeline diff reports.  Nothing here needs a GUI.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any, Iterable, Sequence

from ..errors import OmniFrameError
from ..logging import get_logger
from .checkpoint import diff_projects

LOG = get_logger("core.agent_runtime.inspect")

IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".tif", ".tiff"}


# ---------------------------------------------------------------------------
# Frame extraction
# ---------------------------------------------------------------------------

def _ffmpeg() -> str:
    path = shutil.which("ffmpeg")
    if not path:
        raise OmniFrameError(
            "ffmpeg is required for frame extraction but was not found on PATH.",
            code="E_ENGINE_UNAVAILABLE",
        )
    return path


def extract_frames(
    video: str | Path,
    output_dir: str | Path,
    *,
    fps: float | None = None,
    count: int | None = None,
    start: float = 0.0,
    duration: float | None = None,
    prefix: str = "frame",
) -> list[Path]:
    """Extract PNG frames from ``video`` and return their paths in order.

    Either ``fps`` (frames per second to sample) or ``count`` (number of
    evenly spaced frames) must be provided.
    """

    video_path = Path(video)
    if not video_path.exists():
        raise OmniFrameError(f"Video not found: {video_path}")

    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    if fps and not count:
        pattern = str(out_dir / f"{prefix}_%06d.png")
        cmd = [
            _ffmpeg(), "-hide_banner", "-loglevel", "error", "-y",
            "-ss", str(start),
        ]
        if duration is not None:
            cmd += ["-t", str(duration)]
        cmd += ["-i", str(video_path), "-vf", f"fps={fps}", pattern]
    elif count:
        pattern = str(out_dir / f"{prefix}_%06d.png")
        cmd = [
            _ffmpeg(), "-hide_banner", "-loglevel", "error", "-y",
            "-ss", str(start),
        ]
        if duration is not None:
            cmd += ["-t", str(duration)]
        cmd += ["-i", str(video_path), "-vf", "select='not(mod(n\\,1))'", "-vsync", "0", pattern]
        cmd = cmd[:-1] + ["-frames:v", str(count), pattern]
    else:
        raise OmniFrameError("extract_frames requires either 'fps' or 'count'.")

    LOG.debug("extracting frames", extra={"video": str(video_path), "cmd": cmd})
    proc = subprocess.run(cmd, capture_output=True, text=True, check=False)  # noqa: S603
    if proc.returncode != 0:
        raise OmniFrameError(
            f"ffmpeg failed to extract frames: {proc.stderr.strip()[:800]}",
            code="E_RENDER",
        )

    frames = sorted(out_dir.glob(f"{prefix}_*.png"))
    return frames


def list_image_frames(directory: str | Path, *, pattern: str = "*.png") -> list[Path]:
    """Return the sorted image frames inside ``directory``."""

    folder = Path(directory)
    if not folder.is_dir():
        raise OmniFrameError(f"Not a directory: {folder}")
    return sorted(p for p in folder.glob(pattern) if p.suffix.lower() in IMAGE_SUFFIXES)


# ---------------------------------------------------------------------------
# Contact sheets & strips
# ---------------------------------------------------------------------------

def _open_image(path: Path):
    from PIL import Image

    return Image.open(path).convert("RGB")


def build_contact_sheet(
    frames: Sequence[str | Path],
    output: str | Path,
    *,
    columns: int = 4,
    thumb_width: int = 320,
    padding: int = 8,
    label: bool = True,
) -> Path:
    """Compose a grid contact sheet from ``frames``.

    This is the primary artefact a multimodal agent inspects to judge whether
    a render is correct.
    """

    from PIL import Image, ImageDraw

    paths = [Path(f) for f in frames]
    if not paths:
        raise OmniFrameError("build_contact_sheet requires at least one frame.")

    columns = max(1, min(columns, len(paths)))
    rows = (len(paths) + columns - 1) // columns

    first = _open_image(paths[0])
    ratio = first.height / max(1, first.width)
    thumb_height = max(1, int(thumb_width * ratio))
    label_height = 18 if label else 0

    sheet_width = columns * thumb_width + (columns + 1) * padding
    sheet_height = rows * (thumb_height + label_height) + (rows + 1) * padding

    sheet = Image.new("RGB", (sheet_width, sheet_height), (16, 16, 20))
    draw = ImageDraw.Draw(sheet)

    for index, path in enumerate(paths):
        row, col = divmod(index, columns)
        x = padding + col * (thumb_width + padding)
        y = padding + row * (thumb_height + label_height + padding)
        try:
            with _open_image(path) as image:
                thumb = image.resize((thumb_width, thumb_height), Image.LANCZOS)
                sheet.paste(thumb, (x, y))
        except Exception as exc:  # pragma: no cover - corrupt frame
            LOG.warning("could not paste frame", extra={"frame": str(path), "error": str(exc)})
            continue
        if label:
            draw.text((x + 2, y + thumb_height + 3), path.stem[-14:], fill=(200, 200, 210))

    out = Path(output)
    out.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(out)
    LOG.info("contact sheet written", extra={"path": str(out), "frames": len(paths)})
    return out


def frame_strip(
    frames: Sequence[str | Path],
    output: str | Path,
    *,
    thumb_width: int = 240,
    padding: int = 4,
) -> Path:
    """Compose a single horizontal strip — ideal for judging timing/pacing."""

    from PIL import Image

    paths = [Path(f) for f in frames]
    if not paths:
        raise OmniFrameError("frame_strip requires at least one frame.")

    first = _open_image(paths[0])
    ratio = first.height / max(1, first.width)
    thumb_height = max(1, int(thumb_width * ratio))

    strip_width = len(paths) * thumb_width + (len(paths) + 1) * padding
    strip = Image.new("RGB", (strip_width, thumb_height + 2 * padding), (16, 16, 20))

    for index, path in enumerate(paths):
        x = padding + index * (thumb_width + padding)
        try:
            with _open_image(path) as image:
                strip.paste(image.resize((thumb_width, thumb_height), Image.LANCZOS), (x, padding))
        except Exception as exc:  # pragma: no cover - corrupt frame
            LOG.warning("could not paste frame", extra={"frame": str(path), "error": str(exc)})

    out = Path(output)
    out.parent.mkdir(parents=True, exist_ok=True)
    strip.save(out)
    LOG.info("frame strip written", extra={"path": str(out), "frames": len(paths)})
    return out


# ---------------------------------------------------------------------------
# Timeline reports
# ---------------------------------------------------------------------------

def timeline_report(project: Any) -> dict[str, Any]:
    """A structured, agent-readable summary of a project's timeline."""

    from ..timeline_schema.models import OmniProject

    if not isinstance(project, OmniProject):
        project = OmniProject.model_validate(project)

    frames = project.total_frames()
    fps = project.meta.fps
    tracks = []
    for track in project.sorted_tracks():
        clips = track.sorted_clips()
        tracks.append(
            {
                "id": track.id,
                "name": track.name,
                "kind": track.kind.value,
                "clip_count": len(clips),
                "busy_frames": sum(c.duration_frames for c in clips),
                "clips": [
                    {
                        "id": c.id,
                        "name": c.name,
                        "kind": c.kind.value,
                        "start_frame": c.start_frame,
                        "duration_frames": c.duration_frames,
                        "timecode": project.timecode(c.start_frame),
                        "source": c.source,
                        "keyframes": len(c.keyframes),
                    }
                    for c in clips
                ],
            }
        )

    return {
        "name": project.meta.name,
        "fps": fps,
        "resolution": [project.meta.width, project.meta.height],
        "duration_frames": frames,
        "duration_seconds": round(frames / fps, 3) if fps else 0,
        "timecode": project.timecode(frames),
        "tracks": tracks,
        "shots": [
            {
                "id": s.id,
                "name": s.name,
                "start_frame": s.start_frame,
                "end_frame": s.end_frame,
                "duration_frames": s.duration_frames,
                "engine": s.engine.value if s.engine else None,
            }
            for s in project.sorted_shots()
        ],
        "assets": [{"id": a.id, "kind": a.kind, "path": a.path, "url": a.url} for a in project.assets],
        "render_targets": [t.model_dump(mode="json") for t in project.render_targets],
    }


def timeline_diff(before: Any, after: Any) -> dict[str, Any]:
    """Compare two project documents and return a structured diff report."""

    from ..timeline_schema.models import OmniProject

    if not isinstance(before, OmniProject):
        before = OmniProject.model_validate(before)
    if not isinstance(after, OmniProject):
        after = OmniProject.model_validate(after)
    return diff_projects(before, after)


def write_report(report: dict[str, Any], path: str | Path) -> Path:
    """Persist a JSON report to disk."""

    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    return out


def make_temp_dir(prefix: str = "omniframe-inspect-") -> Path:
    """Create a temporary directory (caller owns cleanup)."""

    return Path(tempfile.mkdtemp(prefix=prefix))
