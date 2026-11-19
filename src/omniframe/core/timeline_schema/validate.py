"""Semantic validation for :class:`OmniProject` documents.

Pydantic guarantees the *shape* of a document.  This module guarantees the
*meaning*: no overlapping clips on a track, keyframes inside their clip, shots
that line up with the timeline, and so on.  Every issue carries a stable code
so an agent can fix problems deterministically.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Any

from pydantic import ValidationError

from .models import OmniProject, ValidationSeverity


@dataclass
class ValidationIssue:
    """One problem found in a project document."""

    severity: ValidationSeverity
    code: str
    message: str
    path: str = ""
    context: dict[str, Any] = field(default_factory=dict)

    @property
    def is_error(self) -> bool:
        return self.severity == ValidationSeverity.ERROR

    def to_dict(self) -> dict[str, Any]:
        return {
            "severity": self.severity.value,
            "code": self.code,
            "message": self.message,
            "path": self.path,
            "context": self.context,
        }

    def __str__(self) -> str:  # pragma: no cover - trivial
        where = f" at {self.path}" if self.path else ""
        return f"[{self.severity.value.upper()}] {self.code}{where}: {self.message}"


def _issue(
    severity: ValidationSeverity,
    code: str,
    message: str,
    path: str = "",
    **context: Any,
) -> ValidationIssue:
    return ValidationIssue(severity=severity, code=code, message=message, path=path, context=context)


def validate_document(document: dict[str, Any]) -> list[ValidationIssue]:
    """Validate a raw dictionary (e.g. parsed JSON/YAML) into issues."""

    issues: list[ValidationIssue] = []
    try:
        project = OmniProject.model_validate(document)
    except ValidationError as exc:
        for err in exc.errors():
            loc = ".".join(str(p) for p in err.get("loc", ()))
            issues.append(
                _issue(
                    ValidationSeverity.ERROR,
                    "E_SCHEMA_FIELD",
                    f"{err.get('msg', 'invalid value')}",
                    path=loc,
                    type=err.get("type", "value_error"),
                )
            )
        return issues
    issues.extend(validate_project(project))
    return issues


def validate_project(
    project: OmniProject,
    *,
    check_assets: bool = True,
    base_dir: str | os.PathLike[str] | None = None,
) -> list[ValidationIssue]:
    """Run every semantic check and return the list of issues found."""

    issues: list[ValidationIssue] = []
    meta = project.meta

    if meta.width % 2 or meta.height % 2:
        issues.append(
            _issue(
                ValidationSeverity.WARNING,
                "W_ODD_DIMENSIONS",
                f"Frame size {meta.width}x{meta.height} has odd dimensions; most H.264 "
                "encoders require even width and height.",
                path="meta",
            )
        )

    if meta.fps <= 0:
        issues.append(
            _issue(
                ValidationSeverity.ERROR,
                "E_BAD_FPS",
                "meta.fps must be greater than zero.",
                path="meta.fps",
            )
        )

    total = project.total_frames()

    # -- track level ----------------------------------------------------
    seen_track_ids: set[str] = set()
    for idx, track in enumerate(project.tracks):
        path = f"tracks[{idx}]"
        if track.id in seen_track_ids:
            issues.append(
                _issue(
                    ValidationSeverity.ERROR,
                    "E_DUPLICATE_TRACK_ID",
                    f"Duplicate track id '{track.id}'.",
                    path=path,
                    track_id=track.id,
                )
            )
        seen_track_ids.add(track.id)

        for a, b in track.overlaps():
            issues.append(
                _issue(
                    ValidationSeverity.ERROR,
                    "E_CLIP_OVERLAP",
                    f"Clip '{b.id}' overlaps clip '{a.id}' on track '{track.id}'.",
                    path=f"{path}.clips",
                    track_id=track.id,
                    clip_a=a.id,
                    clip_b=b.id,
                    overlap_frames=min(a.end_frame, b.end_frame) - b.start_frame,
                )
            )

        for clip in track.clips:
            issues.extend(_validate_clip(clip, track, total, path))

    # -- shots ----------------------------------------------------------
    shot_ids: set[str] = set()
    for idx, shot in enumerate(project.shots):
        path = f"shots[{idx}]"
        if shot.id in shot_ids:
            issues.append(
                _issue(
                    ValidationSeverity.ERROR,
                    "E_DUPLICATE_SHOT_ID",
                    f"Duplicate shot id '{shot.id}'.",
                    path=path,
                )
            )
        shot_ids.add(shot.id)
        if shot.end_frame < shot.start_frame:
            issues.append(
                _issue(
                    ValidationSeverity.ERROR,
                    "E_SHOT_RANGE",
                    f"Shot '{shot.id}' ends ({shot.end_frame}) before it starts ({shot.start_frame}).",
                    path=path,
                    shot_id=shot.id,
                )
            )

    for idx, asset in enumerate(project.assets):
        if check_assets and asset.path and not asset.url:
            path = f"assets[{idx}].path"
            resolved = asset.path
            if base_dir and not os.path.isabs(resolved):
                resolved = os.path.join(str(base_dir), resolved)
            if not os.path.exists(resolved):
                issues.append(
                    _issue(
                        ValidationSeverity.WARNING,
                        "W_ASSET_MISSING",
                        f"Asset '{asset.id}' references a missing file: {asset.path}",
                        path=path,
                        asset_id=asset.id,
                    )
                )

    for idx, target in enumerate(project.render_targets):
        if target.width and target.width % 2:
            issues.append(
                _issue(
                    ValidationSeverity.WARNING,
                    "W_ODD_TARGET_WIDTH",
                    f"Render target '{target.id}' has odd width {target.width}.",
                    path=f"render_targets[{idx}].width",
                )
            )

    return issues


def _validate_clip(clip: Any, track: Any, total_frames: int, track_path: str) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    path = f"{track_path}.clips[{clip.id}]"

    if clip.track_id and clip.track_id != track.id:
        issues.append(
            _issue(
                ValidationSeverity.WARNING,
                "W_CLIP_TRACK_MISMATCH",
                f"Clip '{clip.id}' declares track_id '{clip.track_id}' but lives on '{track.id}'.",
                path=path,
            )
        )

    if total_frames and clip.end_frame > total_frames:
        issues.append(
            _issue(
                ValidationSeverity.WARNING,
                "W_CLIP_BEYOND_DURATION",
                f"Clip '{clip.id}' ends at frame {clip.end_frame}, past the project "
                f"duration of {total_frames} frames.",
                path=path,
                clip_id=clip.id,
            )
        )

    prev: int | None = None
    for kf in clip.keyframes:
        if not clip.contains(kf.frame):
            issues.append(
                _issue(
                    ValidationSeverity.ERROR,
                    "E_KEYFRAME_OUT_OF_RANGE",
                    f"Keyframe at frame {kf.frame} is outside clip '{clip.id}' "
                    f"({clip.start_frame}..{clip.end_frame - 1}).",
                    path=path,
                    clip_id=clip.id,
                    frame=kf.frame,
                )
            )
        if prev is not None and kf.frame < prev:
            issues.append(
                _issue(
                    ValidationSeverity.ERROR,
                    "E_KEYFRAME_UNSORTED",
                    f"Keyframes of clip '{clip.id}' are not in ascending frame order.",
                    path=path,
                    clip_id=clip.id,
                )
            )
        prev = kf.frame

    if clip.kind.value == "code_scene" and clip.code is None:
        issues.append(
            _issue(
                ValidationSeverity.ERROR,
                "E_CODE_SCENE_MISSING",
                f"Clip '{clip.id}' is a code_scene but carries no 'code' payload.",
                path=path,
                clip_id=clip.id,
            )
        )

    if clip.kind.value == "text" and clip.text is None:
        issues.append(
            _issue(
                ValidationSeverity.WARNING,
                "W_TEXT_BODY_MISSING",
                f"Text clip '{clip.id}' has no text payload.",
                path=path,
                clip_id=clip.id,
            )
        )

    if clip.kind.value in {"video", "image", "audio"} and not clip.source:
        issues.append(
            _issue(
                ValidationSeverity.ERROR,
                "E_MEDIA_SOURCE_MISSING",
                f"Media clip '{clip.id}' has no source path.",
                path=path,
                clip_id=clip.id,
            )
        )

    return issues


def assert_valid(
    project: OmniProject,
    *,
    check_assets: bool = True,
    base_dir: str | os.PathLike[str] | None = None,
) -> None:
    """Raise :class:`~omniframe.core.errors.ValidationError` if errors exist."""

    from ...core.errors import ValidationError as OmniValidationError

    issues = validate_project(project, check_assets=check_assets, base_dir=base_dir)
    errors = [i for i in issues if i.is_error]
    if errors:
        raise OmniValidationError(
            f"Project failed validation with {len(errors)} error(s).",
            issues=[i.to_dict() for i in issues],
        )


def summarize(issues: list[ValidationIssue]) -> dict[str, Any]:
    """Aggregate issues into a compact, agent-friendly report."""

    by_severity: dict[str, int] = {}
    by_code: dict[str, int] = {}
    for issue in issues:
        by_severity[issue.severity.value] = by_severity.get(issue.severity.value, 0) + 1
        by_code[issue.code] = by_code.get(issue.code, 0) + 1
    return {
        "ok": by_severity.get("error", 0) == 0,
        "counts": by_severity,
        "codes": by_code,
        "issues": [i.to_dict() for i in issues],
    }
