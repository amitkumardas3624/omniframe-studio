"""Reference vs output compare gate (root SKILL.md section 7A).

A template is not done because its JSON validates, its lint passes and a frame
sequence renders. It is done when the same frame numbers taken from the
reference and from the output have been looked at side by side, and every
visual mechanic has been attested - matched, or declared as an explicit engine
limit. This module supplies the machinery for that gate: the 7A checklist as
data, frame list parsing, an fps-correct reference frame mapping, a perceptual
pixel gap, and the markdown record of a run.

Pillow and ffmpeg stay optional. The pixel gap returns None when Pillow is
missing, and reference extraction raises E_ENGINE_UNAVAILABLE when ffmpeg is
missing, so the gate degrades honestly instead of pretending to compare.
"""

from __future__ import annotations

import re
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ...core.errors import EngineUnavailable, RenderError, ValidationError

__all__ = [
    "ATTESTED",
    "CHECKLIST",
    "ChecklistItem",
    "build_compare",
    "extract_reference_frame",
    "mean_abs_diff",
    "parse_frames",
    "reference_fps",
    "reference_frame_index",
    "render_report_markdown",
    "verdict",
]

#: statuses an attested checklist row may carry
ATTESTED = frozenset({"match", "gap", "limit"})
@dataclass(frozen=True)
class ChecklistItem:
    """One visual mechanic from section 7A."""

    id: str
    label: str
    status: str = "unchecked"
    note: str = ""

    def to_dict(self) -> dict[str, str]:
        """Plain mapping for JSON results and the markdown report."""
        return {
            "id": self.id,
            "label": self.label,
            "status": self.status,
            "note": self.note,
        }


CHECKLIST: tuple[ChecklistItem, ...] = (
    ChecklistItem(
        "background_shifts",
        "Background shifts and kinetic typography layers and motion: not plain "
        "static text on a stuck background.",
    ),
    ChecklistItem(
        "grid_density",
        "Full density and motion of grids, arrays and patterns: not a few sparse "
        "outlines.",
    ),
    ChecklistItem(
        "particle_construction",
        "Particle-built typography and forms with colour transitions: not plain "
        "solid text or missing particle construction.",
    ),
    ChecklistItem(
        "3d_focal_objects",
        "3D focal objects, spheres and morphs over perspective and spatial layers: "
        "not empty grids or flat rings.",
    ),
    ChecklistItem(
        "outro_hierarchy",
        "Multi-layered curves, waves and transitions with the full outro "
        "hierarchy: not stripped-down single lines or text.",
    ),
)


def parse_frames(text: str, total: int) -> list[int]:
    """Parse a frame list such as "0, 120,240" into sorted unique frames.

    Every frame must be an integer in [0, total). An empty list, an empty token
    ("1,,2"), a non-integer and an out-of-range frame are validation errors: the
    gate is worthless if it silently compares a different frame than the one
    asked for.
    """

    raw = str(text or "").strip()
    if not raw:
        raise ValidationError("Frame list is empty; give at least one frame.")
    # A comma is a separator in its own right: "1,,2" has an empty field and must
    # fail rather than silently become [1, 2]. Whitespace around a comma is fine.
    if "," in raw:
        fields = raw.split(",")
        if any(not field.strip() for field in fields):
            raise ValidationError("Frame list has an empty entry.", value=raw)
        # One number per comma field: "1, 2 3" is two numbers and junk,
        # not three numbers, and the browser parser reads it the same way.
        tokens = [field.strip() for field in fields]
    else:
        tokens = raw.split()
    frames: list[int] = []
    for token in tokens:
        # Plain ASCII digits only. int() also accepts "+3", "1_0" and the
        # digits of other scripts, and the browser parser does not; the two
        # have to agree on which frame was asked for.
        if not token.isascii() or not token.isdigit():
            raise ValidationError(
                "Frame list entry is not a plain frame number.", value=token
            )
        frame = int(token)
        if frame < 0 or frame >= total:
            raise ValidationError(
                "Frame is outside the project range.",
                frame=frame,
                duration_frames=total,
            )
        frames.append(frame)
    return sorted(set(frames))


def reference_frame_index(frame: int, *, project_fps: float, reference_fps: float) -> int:
    """Map a project frame to the reference frame at the same instant.

    The contract is same instant, not same ordinal: project frame 10 of a 30 fps
    project is reference frame 20 of a 60 fps reference. Matching rates are the
    identity, so an fps mismatch never quietly compares the wrong moments.
    """

    project_rate = float(project_fps or 0.0)
    reference_rate = float(reference_fps or 0.0)
    if project_rate <= 0 or reference_rate <= 0:
        raise ValidationError(
            "Both frame rates must be positive to map a reference frame.",
            project_fps=project_fps,
            reference_fps=reference_fps,
        )
    # Half up, not banker rounding: at exactly half a reference frame the
    # later reference frame is the closer one.
    return int((int(frame) / project_rate) * reference_rate + 0.5)


def _parse_rate(raw: Any) -> float | None:
    """Parse an ffprobe rate such as 30000/1001 into a float, else None."""

    text = str(raw or "").strip()
    if not text or text in {"0/0", "N/A"}:
        return None
    if "/" in text:
        numerator, _, denominator = text.partition("/")
        try:
            num = float(numerator)
            den = float(denominator)
        except (TypeError, ValueError):
            return None
        return num / den if den else None
    try:
        return float(text)
    except (TypeError, ValueError):
        return None


def reference_fps(video: str | Path) -> float:
    """Frame rate of the reference video.

    Raises when the rate cannot be read. The rate decides which reference
    instant each output frame is compared against, so an unreadable reference
    has to stop the run: falling back to the project rate would compare
    different moments while producing a plausible looking diff.
    """

    from .ffmpeg import ffprobe_info

    try:
        info = ffprobe_info(video)
    except RenderError as exc:
        raise ValidationError(
            "Reference video could not be read.", path=str(video)
        ) from exc
    for stream in info.get("streams", []) or []:
        if stream.get("codec_type") != "video":
            continue
        rate = _parse_rate(stream.get("r_frame_rate"))
        if rate is None:
            raise ValidationError(
                "Reference video has no usable frame rate.", path=str(video)
            )
        return rate
    raise ValidationError("Reference file has no video stream.", path=str(video))


def extract_reference_frame(video: str | Path, index: int, output_dir: str | Path) -> Path:
    """Write reference frame ``index`` (0-based, ffmpeg n) of ``video`` as PNG.

    The frame number is absolute, so the gate can ask for exactly the frame a
    reviewer names. Requires ffmpeg; raises E_ENGINE_UNAVAILABLE when absent.
    """

    from .ffmpeg import ffmpeg_available, run_ffmpeg

    if not ffmpeg_available():
        raise EngineUnavailable(
            "ffmpeg is required to extract a reference frame but was not found on PATH."
        )
    target = Path(output_dir) / f"reference_{int(index):06d}.png"
    if target.exists():
        target.unlink()
    run_ffmpeg(
        [
            "-i", str(video),
            "-vf", f"select=eq(n\\,{int(index)})",
            "-vsync", "0",
            "-frames:v", "1",
            str(target),
        ]
    )
    if not target.exists():
        raise ValidationError(
            "Reference frame could not be extracted; the video may be shorter.",
            video=str(video),
            reference_frame=int(index),
        )
    return target


def mean_abs_diff(first: str | Path, second: str | Path) -> float | None:
    """Mean absolute RGBA difference between two PNGs, 0.0 to 255.0.

    Returns None when Pillow is unavailable, when either file cannot be read,
    or when the sizes disagree - a numeric gap between mismatched sizes would be
    a lie, so the caller gets no number instead.
    """

    try:
        from PIL import Image, ImageChops, ImageStat
    except ImportError:
        return None
    try:
        with Image.open(Path(first)) as left, Image.open(Path(second)) as right:
            actual = left.convert("RGBA")
            expected = right.convert("RGBA")
            if actual.size != expected.size:
                return None
            # The same metric as the per-pixel loop, computed in C: the mean
            # absolute difference of every band, averaged over the bands.
            means = ImageStat.Stat(ImageChops.difference(actual, expected)).mean
            return sum(means) / len(means)
    except Exception:
        return None


def build_compare(
    frames: Sequence[int],
    *,
    render_frame: Callable[[int], dict[str, Any]],
    project_path: str | Path,
    project_fps: float,
    total_frames: int,
    reference_video: str | Path | None = None,
    reference_frames_dir: str | Path | None = None,
    width: int | None = None,
    height: int | None = None,
    backend: str = "stub",
    work_dir: str | Path | None = None,
) -> dict[str, Any]:
    """Render the same frame numbers from the output and from the reference.

    Each returned row carries the current PNG and, when a reference was
    supplied, the reference PNG at the same instant plus the pixel gap. The
    checklist rows are returned unattested: a machine cannot tick a visual
    mechanic, and pretending otherwise is the failure this gate exists to stop.
    """

    import base64
    import tempfile

    wanted = [int(frame) for frame in frames]
    if not wanted:
        raise ValidationError("Compare needs at least one frame.")
    for frame in wanted:
        if frame < 0 or frame >= int(total_frames):
            raise ValidationError(
                "Compare frame is outside the project range.",
                frame=frame,
                duration_frames=int(total_frames),
            )
    if reference_video is not None and reference_frames_dir is not None:
        raise ValidationError(
            "Give either a reference video or a reference frame directory, not both."
        )

    scratch = Path(work_dir) if work_dir is not None else None
    owned = None
    if scratch is None:
        owned = tempfile.TemporaryDirectory(prefix="omniframe-compare-")
        scratch = Path(owned.name)

    kind = None
    rate = float(project_fps)
    rows: list[dict[str, Any]] = []
    problems: list[str] = []
    try:
        if reference_video is not None:
            kind = "video"
            # The reference rate decides the instant mapping, so an unreadable
            # reference stops the run instead of silently reusing the project
            # rate and comparing the wrong moments.
            rate = float(reference_fps(reference_video))
        elif reference_frames_dir is not None:
            kind = "frames"
            directory = Path(reference_frames_dir)
            if not directory.is_dir():
                raise ValidationError(
                    "Reference frames directory not found.", path=str(directory)
                )
            if not any(directory.glob("*.png")):
                raise ValidationError(
                    "Reference frames directory has no PNG frames.",
                    path=str(directory),
                )

        for frame in wanted:
            rendered = dict(render_frame(frame))
            current_b64 = rendered.get("image_base64")
            row: dict[str, Any] = {
                "frame": frame,
                "t": rendered.get("t"),
                "verification_level": rendered.get("verification_level"),
                "current": current_b64,
                "reference": None,
                "reference_frame": None,
                "reference_file": None,
                "reference_match": None,
                "diff": None,
            }
            if kind == "video":
                index = reference_frame_index(
                    frame, project_fps=float(project_fps), reference_fps=rate
                )
                try:
                    ref_path = extract_reference_frame(reference_video, index, scratch)
                except EngineUnavailable:
                    # No ffmpeg means no comparison is possible; say so.
                    raise
                except Exception as exc:
                    problems.append(
                        f"Reference frame {index} could not be extracted: {exc}"
                    )
                    ref_path = None
                if ref_path is not None:
                    row["reference_frame"] = index
                    row["reference_match"] = "video"
                    row["reference"] = base64.b64encode(
                        Path(ref_path).read_bytes()
                    ).decode("ascii")
            elif kind == "frames":
                ref_path, match_kind = _resolve_reference_png(
                    Path(reference_frames_dir), frame
                )
                row["reference_match"] = match_kind
                if ref_path is not None:
                    row["reference_frame"] = frame
                    row["reference_file"] = ref_path.name
                    row["reference"] = base64.b64encode(ref_path.read_bytes()).decode(
                        "ascii"
                    )
                else:
                    problems.append(
                        f"No reference frame {frame} in {reference_frames_dir}."
                    )
            if row["reference"] and current_b64:
                current_png = scratch / f"current_{frame:06d}.png"
                ref_png = scratch / f"reference_in_{frame:06d}.png"
                current_png.write_bytes(base64.b64decode(current_b64))
                ref_png.write_bytes(base64.b64decode(row["reference"]))
                row["diff"] = mean_abs_diff(current_png, ref_png)
            rows.append(row)
    finally:
        if owned is not None:
            owned.cleanup()

    checklist = [item.to_dict() for item in CHECKLIST]
    return {
        "project_path": str(project_path),
        "project_fps": float(project_fps),
        "total_frames": int(total_frames),
        "reference_supplied": kind is not None,
        "reference_kind": kind,
        "reference_path": str(reference_video or reference_frames_dir or "") or None,
        "reference_fps": rate if kind == "video" else None,
        "reference_frames_requested": len(rows),
        "reference_frames_extracted": sum(
            1 for row in rows if row.get("reference")
        ),
        "reference_problems": problems,
        "frames": rows,
        "checklist": checklist,
        "verdict": verdict(checklist),
    }


def _find_reference_png(directory: Path, frame: int) -> Path | None:
    """Locate the reference PNG for ``frame`` inside ``directory``."""

    path, _match = _resolve_reference_png(directory, frame)
    return path


def _resolve_reference_png(directory: Path, frame: int) -> tuple[Path | None, str]:
    """Locate the reference PNG for ``frame`` and report how it was matched.

    The exact name conventions come first. Then a file whose name carries the
    frame number is matched by that number, so ``f060.png`` is reference frame
    60 and never "the first file in the folder". Positional order is not used
    at all: guessing an index there would compare a different frame than the
    one that was asked for and would report it as a real difference.
    """

    number = int(frame)
    for name in (
        f"frame_{number:05d}.png",
        f"{number:05d}.png",
        f"frame_{number}.png",
        f"{number}.png",
    ):
        candidate = directory / name
        if candidate.exists():
            return candidate, "name"

    numbered: dict[int, Path] = {}
    for png in sorted(directory.glob("*.png")):
        digits = re.findall(r"\d+", png.stem)
        if digits:
            numbered.setdefault(int(digits[-1]), png)
    if number in numbered:
        return numbered[number], "frame_number"
    return None, "no_match"


def verdict(rows: Sequence[dict[str, Any]]) -> dict[str, Any]:
    """Decide whether the checklist can carry a pass.

    A pass needs every 7A mechanic present in ``rows`` and attested as either
    match or limit, no entry left as gap, and a written note for every limit -
    an engine limit that is not named is indistinguishable from a silent
    failure.
    """

    seen: dict[str, dict[str, str]] = {}
    for row in rows:
        key = str(row.get("id", ""))
        seen[key] = {
            "status": str(row.get("status") or "unchecked"),
            "note": str(row.get("note") or "").strip(),
        }

    pending: list[str] = []
    gaps: list[str] = []
    limits_without_note: list[str] = []
    for item in CHECKLIST:
        entry = seen.get(item.id, {"status": "unchecked", "note": ""})
        status = entry["status"]
        if status not in ATTESTED:
            pending.append(item.id)
        elif status == "gap":
            gaps.append(item.id)
        elif status == "limit" and not entry["note"]:
            limits_without_note.append(item.id)
    return {
        "ok": not pending and not gaps and not limits_without_note,
        "pending": pending,
        "gaps": gaps,
        "limits_without_note": limits_without_note,
    }


def render_report_markdown(payload: dict[str, Any]) -> str:
    """Render a compare run as the markdown record kept beside the template."""

    project = str(payload.get("project_path") or "")
    kind = payload.get("reference_kind")
    path = payload.get("reference_path")
    result = payload.get("verdict") or {}
    rows = list(payload.get("frames") or [])
    extracted = payload.get("reference_frames_extracted")
    if extracted is None:
        extracted = sum(1 for row in rows if row.get("reference"))
    requested = payload.get("reference_frames_requested")
    if requested is None:
        requested = len(rows)
    problems = [str(item) for item in (payload.get("reference_problems") or [])]

    if path:
        reference = f"`{path}` ({kind})"
        if extracted:
            reference += f" - {extracted} of {requested} frame(s) compared"
        else:
            reference += " - NOT COMPARED, no reference frame could be read"
    else:
        reference = "none supplied - current output only"

    lines = [
        "# OmniFrame compare gate",
        "",
        f"Project: `{project}`",
        f"Reference: {reference}",
        "",
        "`diff` is the mean absolute RGBA difference over 0 to 255. It is a",
        "perceptual gap, not proof that the motion matches; the checklist",
        "attestation below is the verdict.",
        "",
        "## Frames looked at",
        "",
        "| frame | reference frame | reference file | diff |",
        "|---|---|---|---|",
    ]
    for row in rows:
        diff_text = "n/a"
        if row.get("diff") is not None:
            try:
                diff_text = format(float(row["diff"]), "g")
            except (TypeError, ValueError):
                diff_text = "n/a"
        ref = row.get("reference_frame")
        ref_text = "n/a" if ref is None else str(ref)
        name = row.get("reference_file")
        name_text = "-" if not name else str(name)
        try:
            frame_number = int(row.get("frame") or 0)
        except (TypeError, ValueError):
            frame_number = "?"
        lines.append(
            f"| frame {frame_number} | {ref_text} | {name_text} | {diff_text} |"
        )
    if problems:
        lines += ["", "## Reference problems", ""]
        for problem in problems:
            lines.append(f"- {problem}")
    lines += ["", "## Checklist", "", "| mechanic | status | note |", "|---|---|---|"]
    for row in payload.get("checklist") or []:
        mechanic = row.get("id")
        status = row.get("status")
        note = row.get("note") or ""
        lines.append(f"| {mechanic} | {status} | {note} |")
    limits = [
        row for row in (payload.get("checklist") or []) if row.get("status") == "limit"
    ]
    lines += ["", "## Engine limits (not expressible)", ""]
    if limits:
        for row in limits:
            label = row.get("id")
            detail = row.get("note") or "no note recorded"
            lines.append(f"- {label}: {detail}")
    else:
        lines.append("- None recorded.")
    lines += ["", "## Verdict", ""]
    lines.append("PASS" if result.get("ok") else "FAIL")
    if result.get("pending"):
        lines.append("")
        lines.append("Unattested: " + ", ".join(result["pending"]))
    if result.get("gaps"):
        lines.append("")
        lines.append("Gaps: " + ", ".join(result["gaps"]))
    if result.get("limits_without_note"):
        lines.append("")
        lines.append("Limits without a note: " + ", ".join(result["limits_without_note"]))
    return "\n".join(lines)
