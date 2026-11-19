"""The canonical, vendor-neutral OmniFrame project model.

Everything OmniFrame renders — code-driven motion graphics, hand-drawn 2D
sequences, or an NLE timeline imported from Premiere / Resolve / CapCut — is
first normalised into a single :class:`OmniProject` document.  Engines consume
the universal model; bridges translate the universal model back out.

The model is intentionally verbose and explicit: an autonomous agent must be
able to read a project file and know exactly what will be rendered.
"""

from __future__ import annotations

import math
from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

SCHEMA_VERSION = "1.0"


class OmniModel(BaseModel):
    """Base model with forward-compatible, agent-friendly behaviour."""

    model_config = ConfigDict(
        extra="allow",
        validate_assignment=True,
        populate_by_name=True,
        use_enum_values=False,
    )


# ---------------------------------------------------------------------------
# Enumerations
# ---------------------------------------------------------------------------

class TrackKind(str, Enum):
    VIDEO = "video"
    TWO_D_ANIMATION = "2d_animation"
    CODE_SCENE = "code_scene"
    MOTION_FX = "motion_fx"
    COLOR_GRADE = "color_grade"
    AUDIO = "audio"
    SUBTITLE = "subtitle"


class ClipKind(str, Enum):
    VIDEO = "video"
    IMAGE = "image"
    AUDIO = "audio"
    TEXT = "text"
    CODE_SCENE = "code_scene"
    CARTOON_LAYER = "cartoon_layer"
    SOLID = "solid"
    SHAPE = "shape"
    SUBTITLE = "subtitle"
    ADJUSTMENT = "adjustment"
    GENERATOR = "generator"


class EasingKind(str, Enum):
    LINEAR = "linear"
    EASE_IN = "ease_in"
    EASE_OUT = "ease_out"
    EASE_IN_OUT = "ease_in_out"
    BEZIER = "bezier"
    STEP = "step"
    HOLD = "hold"


class ShotEngine(str, Enum):
    CODE_HTML_JS = "code_html_js"
    CARTOON_2D = "cartoon_2d"
    AFTER_EFFECTS = "after_effects"
    PREMIERE_PRO = "premiere_pro"
    DAVINCI_RESOLVE = "davinci_resolve"
    CAPCUT = "capcut"
    FFMPEG_COMPOSITOR = "ffmpeg_compositor"


class ValidationSeverity(str, Enum):
    ERROR = "error"
    WARNING = "warning"
    INFO = "info"


# ---------------------------------------------------------------------------
# Value objects
# ---------------------------------------------------------------------------

class Easing(OmniModel):
    """Interpolation curve applied *after* the keyframe it belongs to."""

    kind: EasingKind = EasingKind.LINEAR
    #: Cubic bezier control points, normalised 0..1, used when kind == bezier.
    control: list[float] = Field(default_factory=lambda: [0.0, 0.0, 1.0, 1.0])
    #: Duration in frames for stepped/hold-like curves.
    steps: int = 1

    def apply(self, t: float) -> float:
        """Map a normalised time ``t`` (0..1) through this curve."""

        t = min(1.0, max(0.0, t))
        kind = self.kind
        if kind == EasingKind.LINEAR:
            return t
        if kind == EasingKind.STEP:
            steps = max(1, self.steps)
            return math.floor(t * steps) / steps
        if kind == EasingKind.HOLD:
            return 0.0
        if kind == EasingKind.EASE_IN:
            return t * t
        if kind == EasingKind.EASE_OUT:
            return 1 - (1 - t) ** 2
        if kind == EasingKind.EASE_IN_OUT:
            return 2 * t * t if t < 0.5 else 1 - ((-2 * t + 2) ** 2) / 2
        if kind == EasingKind.BEZIER:
            return _bezier_ease(t, self.control)
        return t


def _bezier_ease(t: float, control: list[float]) -> float:
    """Cubic-bezier easing solved with Newton-Raphson + bisection fallback."""

    if len(control) < 4:
        return t
    x1, y1, x2, y2 = (float(c) for c in control[:4])

    def curve(u: float) -> tuple[float, float]:
        x = 3 * u * (1 - u) ** 2 * x1 + 3 * u * u * (1 - u) * x2 + u ** 3
        y = 3 * u * (1 - u) ** 2 * y1 + 3 * u * u * (1 - u) * y2 + u ** 3
        return x, y

    lo, hi = 0.0, 1.0
    u = t
    for _ in range(24):
        x, y = curve(u)
        if abs(x - t) < 1e-6:
            return y
        if x < t:
            lo = u
        else:
            hi = u
        u = (lo + hi) / 2
    _, y = curve(u)
    return y


class Keyframe(OmniModel):
    """A single animated property value at an absolute timeline frame."""

    frame: int = Field(ge=0, description="Absolute frame on the project timeline.")
    values: dict[str, Any] = Field(
        default_factory=dict,
        description="Property values at this frame, e.g. {'x': 120, 'opacity': 1.0}.",
    )
    easing: Easing = Field(
        default_factory=Easing,
        description="Curve applied when interpolating *from* this keyframe onwards.",
    )
    label: str | None = None

    @field_validator("values")
    @classmethod
    def _values_not_empty(cls, v: dict[str, Any]) -> dict[str, Any]:
        if not v:
            raise ValueError("keyframe.values must not be empty")
        return v


class Transform(OmniModel):
    """2D affine transform applied to a clip."""

    position: list[float] = Field(default_factory=lambda: [0.0, 0.0], description="[x, y] in pixels.")
    scale: list[float] = Field(default_factory=lambda: [1.0, 1.0], description="[sx, sy].")
    rotation: float = Field(default=0.0, description="Degrees, clockwise.")
    anchor: list[float] = Field(default_factory=lambda: [0.5, 0.5], description="[ax, ay] 0..1.")
    opacity: float = Field(default=1.0, ge=0.0, le=1.0)
    skew_x: float = 0.0
    skew_y: float = 0.0

    def to_css(self) -> str:
        sx, sy = self.scale
        ax, ay = self.anchor
        x, y = self.position
        return (
            f"translate({x}px, {y}px) rotate({self.rotation}deg) "
            f"scale({sx}, {sy}) skewX({self.skew_x}deg) skewY({self.skew_y}deg) "
            f"transform-origin({ax * 100:.2f}% {ay * 100:.2f}%)"
        )


class Effect(OmniModel):
    """A named effect / adjustment attached to a clip."""

    name: str
    kind: str = "generic"
    enabled: bool = True
    params: dict[str, Any] = Field(default_factory=dict)


class TextSpec(OmniModel):
    """Rich-text payload for ``ClipKind.TEXT`` / ``ClipKind.SUBTITLE``."""

    body: str = ""
    font_family: str = "Inter"
    font_size: float = 48.0
    font_weight: Literal["thin", "normal", "medium", "bold", "black"] = "bold"
    color: str = "#FFFFFF"
    stroke_color: str | None = None
    stroke_width: float = 0.0
    align: Literal["left", "center", "right"] = "center"
    line_height: float = 1.2
    letter_spacing: float = 0.0
    shadow: dict[str, Any] = Field(default_factory=dict)


class CodeSceneSpec(OmniModel):
    """An HTML/CSS/JS scene rendered frame-by-frame.

    The scene code receives ``frame`` and ``fps`` as deterministic inputs.
    """

    html: str = Field(default="<div id='scene'></div>")
    css: str = ""
    javascript: str = ""
    #: Optional entry script executed after the DOM is ready.
    bootstrap: str | None = None
    #: Deterministic seed exposed to the scene as ``__OMNIFRAME_SEED__``.
    seed: int = 0
    transparent: bool = False
    background: str = "#00000000"
    #: Per-scene variables injected as ``window.OMNIFRAME_PARAMS``.
    params: dict[str, Any] = Field(default_factory=dict)
    #: Milliseconds to wait for the scene to signal a stable paint.
    settle_timeout_ms: int = 250


class CartoonLayerSpec(OmniModel):
    """A single layer inside the 2D cartoon pipeline."""

    id: str
    name: str = ""
    kind: Literal["image", "solid", "text", "vector"] = "image"
    source: str | None = None
    color: str = "#FFFFFFFF"
    #: Draw order inside the parent scene; higher renders on top.
    z: int = 0
    opacity: float = Field(default=1.0, ge=0.0, le=1.0)
    transform: Transform = Field(default_factory=Transform)
    keyframes: list[Keyframe] = Field(default_factory=list)
    #: Optional hold/smear/anticipation metadata used by the in-between tool.
    timing: dict[str, Any] = Field(default_factory=dict)
    visible: bool = True


class CartoonSceneSpec(OmniModel):
    """A 2D cartoon scene: layers, camera and per-frame audio markers."""

    width: int = 1920
    height: int = 1080
    background: str = "#00000000"
    layers: list[CartoonLayerSpec] = Field(default_factory=list)
    camera: Transform = Field(default_factory=Transform)
    camera_keyframes: list[Keyframe] = Field(default_factory=list)
    #: [{"frame": 12, "speaker": "char1", "text": "hello", "phoneme": "A"}]
    dialogue: list[dict[str, Any]] = Field(default_factory=list)
    #: [{"frame": 40, "beat": "kick"}] - beat markers for sync.
    beats: list[dict[str, Any]] = Field(default_factory=list)
    hold_frames: list[int] = Field(default_factory=list)


class AudioSpec(OmniModel):
    """Audio playback description for an audio/video clip."""

    source: str | None = None
    volume: float = Field(default=1.0, ge=0.0, le=4.0)
    fade_in_frames: int = 0
    fade_out_frames: int = 0
    #: When mixing several audio tracks, this track is ducked under others.
    duck_under: list[str] = Field(default_factory=list)
    normalization: Literal["none", "peak", "ebu_r128"] = "none"
    target_lufs: float = -14.0


# ---------------------------------------------------------------------------
# Timeline entities
# ---------------------------------------------------------------------------

class Clip(OmniModel):
    """A timed piece of content on a track."""

    id: str
    name: str = ""
    kind: ClipKind = ClipKind.VIDEO
    track_id: str | None = None
    start_frame: int = Field(ge=0, description="Absolute start frame on the timeline.")
    duration_frames: int = Field(gt=0, description="Length in frames (>= 1).")
    source: str | None = Field(default=None, description="File path or URL of the media.")
    #: Trim offset into the source, in frames.
    in_frame: int = Field(default=0, ge=0)
    out_frame: int | None = None
    transform: Transform = Field(default_factory=Transform)
    opacity: float = Field(default=1.0, ge=0.0, le=1.0)
    volume: float = Field(default=1.0, ge=0.0, le=4.0)
    speed: float = Field(default=1.0, gt=0.0)
    blend_mode: str = "normal"
    keyframes: list[Keyframe] = Field(default_factory=list)
    effects: list[Effect] = Field(default_factory=list)
    text: TextSpec | None = None
    code: CodeSceneSpec | None = None
    cartoon: CartoonSceneSpec | None = None
    audio: AudioSpec | None = None
    prompt: str | None = Field(default=None, description="Free-form brief for generative steps.")
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _check_trim(self) -> "Clip":
        if self.out_frame is not None and self.out_frame <= self.in_frame:
            raise ValueError("clip.out_frame must be greater than clip.in_frame")
        return self

    @property
    def end_frame(self) -> int:
        """Exclusive end frame."""

        return self.start_frame + self.duration_frames

    @property
    def frames(self) -> range:
        return range(self.start_frame, self.end_frame)

    def contains(self, frame: int) -> bool:
        return self.start_frame <= frame < self.end_frame

    def local_frame(self, frame: int) -> int:
        return frame - self.start_frame

    def keyframe_at(self, frame: int) -> Keyframe | None:
        for kf in self.keyframes:
            if kf.frame == frame:
                return kf
        return None


class Track(OmniModel):
    """An ordered lane of clips."""

    id: str
    name: str = ""
    kind: TrackKind = TrackKind.VIDEO
    index: int = 0
    clips: list[Clip] = Field(default_factory=list)
    locked: bool = False
    muted: bool = False
    hidden: bool = False
    #: Rendering order within the same track kind; higher renders on top.
    z: int = 0
    metadata: dict[str, Any] = Field(default_factory=dict)

    def sorted_clips(self) -> list[Clip]:
        return sorted(self.clips, key=lambda c: (c.start_frame, c.id))

    def clip_at(self, frame: int) -> Clip | None:
        for clip in self.sorted_clips():
            if clip.contains(frame):
                return clip
        return None

    def overlaps(self) -> list[tuple[Clip, Clip]]:
        """Return pairs of clips that overlap on the same track."""

        result: list[tuple[Clip, Clip]] = []
        ordered = self.sorted_clips()
        for i, a in enumerate(ordered):
            for b in ordered[i + 1 :]:
                if b.start_frame >= a.end_frame:
                    break
                result.append((a, b))
        return result


class Shot(OmniModel):
    """A narrative unit of the project; the unit the planner routes."""

    id: str
    name: str = ""
    index: int = 0
    start_frame: int = 0
    end_frame: int = 0
    description: str = ""
    engine: ShotEngine | None = None
    transition_in: str | None = None
    transition_out: str | None = None
    tags: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @property
    def duration_frames(self) -> int:
        return max(0, self.end_frame - self.start_frame)


class Transition(OmniModel):
    """A transition applied between two clips or at a cut point."""

    id: str
    kind: str = "cut"
    at_frame: int = 0
    duration_frames: int = 0
    payload: dict[str, Any] = Field(default_factory=dict)


class Asset(OmniModel):
    """An external resource referenced by clips."""

    id: str
    kind: Literal["image", "video", "audio", "font", "videojs", "script", "other"] = "other"
    path: str | None = None
    url: str | None = None
    sha256: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class RenderTarget(OmniModel):
    """A concrete output the compositor should produce."""

    id: str = "default"
    name: str = "default"
    container: str = "mp4"
    video_codec: str = "h264"
    audio_codec: str = "aac"
    width: int | None = None
    height: int | None = None
    fps: float | None = None
    path: str = "out/render.mp4"
    preset: str = "medium"
    bitrate: str | None = None
    crf: int | None = None
    transparent: bool = False
    extra_args: list[str] = Field(default_factory=list)


class ProjectMeta(OmniModel):
    """Global project settings."""

    name: str = "untitled"
    version: str = SCHEMA_VERSION
    fps: float = Field(default=30.0, gt=0)
    width: int = Field(default=1920, gt=0)
    height: int = Field(default=1080, gt=0)
    duration_frames: int = Field(default=0, ge=0)
    color_space: str = "Rec.709"
    audio_sample_rate: int = 48000
    audio_channels: int = 2
    background: str = "#000000"
    created_at: str | None = None
    updated_at: str | None = None


class OmniProject(OmniModel):
    """The root document of an OmniFrame project."""

    schema_version: str = SCHEMA_VERSION
    meta: ProjectMeta = Field(default_factory=ProjectMeta)
    tracks: list[Track] = Field(default_factory=list)
    shots: list[Shot] = Field(default_factory=list)
    transitions: list[Transition] = Field(default_factory=list)
    assets: list[Asset] = Field(default_factory=list)
    render_targets: list[RenderTarget] = Field(default_factory=list)
    scene_graph: dict[str, Any] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)

    # -- helpers ---------------------------------------------------------
    def track(self, track_id: str) -> Track | None:
        for track in self.tracks:
            if track.id == track_id:
                return track
        return None

    def clip(self, clip_id: str) -> Clip | None:
        for track in self.tracks:
            for clip in track.clips:
                if clip.id == clip_id:
                    return clip
        return None

    def sorted_tracks(self) -> list[Track]:
        return sorted(self.tracks, key=lambda t: (t.index, t.id))

    def sorted_shots(self) -> list[Shot]:
        return sorted(self.shots, key=lambda s: (s.start_frame, s.index))

    def total_frames(self) -> int:
        """Effective duration: the larger of the declared duration and the content."""

        end = 0
        for track in self.tracks:
            for clip in track.clips:
                end = max(end, clip.end_frame)
        for shot in self.shots:
            end = max(end, shot.end_frame)
        return max(end, self.meta.duration_frames)

    def frame_to_seconds(self, frame: int) -> float:
        return frame / self.meta.fps

    def seconds_to_frame(self, seconds: float) -> int:
        return int(round(seconds * self.meta.fps))

    def timecode(self, frame: int) -> str:
        """SMPTE-ish timecode ``HH:MM:SS:FF``."""

        fps = int(round(self.meta.fps))
        frames = max(0, frame)
        ff = frames % fps
        total_seconds = frames // fps
        ss = total_seconds % 60
        mm = (total_seconds // 60) % 60
        hh = (total_seconds // 3600) % 24
        return f"{hh:02d}:{mm:02d}:{ss:02d}:{ff:02d}"

    def active_clips(self, frame: int) -> list[Clip]:
        """Every clip covering ``frame``, ordered back-to-front."""

        found: list[Clip] = []
        for track in self.sorted_tracks():
            if track.hidden:
                continue
            clip = track.clip_at(frame)
            if clip is not None:
                found.append(clip)
        return found
