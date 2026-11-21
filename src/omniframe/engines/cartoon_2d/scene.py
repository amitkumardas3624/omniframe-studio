"""The 2D cartoon scene model: layers, keyframes, camera and markers."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .tween import Easing, interpolate


@dataclass
class Keyframe:
    """One animated property value at an absolute frame."""

    frame: int
    values: dict[str, float] = field(default_factory=dict)
    easing: Any = "linear"

    def curve(self) -> Easing:
        return Easing.from_value(self.easing)


@dataclass
class Layer:
    """A single drawable layer of a cartoon scene."""

    id: str
    name: str = ""
    kind: str = "image"  # image | solid | text | vector
    source: str | None = None
    color: str = "#FFFFFFFF"
    z: int = 0
    opacity: float = 1.0
    visible: bool = True
    x: float = 0.0
    y: float = 0.0
    scale_x: float = 1.0
    scale_y: float = 1.0
    rotation: float = 0.0
    anchor_x: float = 0.5
    anchor_y: float = 0.5
    keyframes: list[Keyframe] = field(default_factory=list)
    #: Free-form timing metadata: ``hold``, ``smear``, ``anticipation``.
    timing: dict[str, Any] = field(default_factory=dict)

    # -- conversion -----------------------------------------------------
    @classmethod
    def from_spec(cls, spec: Any) -> Layer:
        """Build a layer from a :class:`CartoonLayerSpec`."""

        transform = getattr(spec, "transform", None)
        position = list(getattr(transform, "position", [0.0, 0.0]) or [0.0, 0.0])
        scale = list(getattr(transform, "scale", [1.0, 1.0]) or [1.0, 1.0])
        anchor = list(getattr(transform, "anchor", [0.5, 0.5]) or [0.5, 0.5])
        keyframes = [
            Keyframe(
                frame=int(kf.frame),
                values={str(k): float(v) for k, v in kf.values.items() if isinstance(v, (int, float))},
                easing=kf.easing,
            )
            for kf in getattr(spec, "keyframes", [])
        ]
        return cls(
            id=spec.id,
            name=getattr(spec, "name", "") or spec.id,
            kind=getattr(spec, "kind", "image"),
            source=getattr(spec, "source", None),
            color=getattr(spec, "color", "#FFFFFFFF"),
            z=int(getattr(spec, "z", 0)),
            opacity=float(getattr(spec, "opacity", 1.0)),
            visible=bool(getattr(spec, "visible", True)),
            x=float(position[0]),
            y=float(position[1]),
            scale_x=float(scale[0]),
            scale_y=float(scale[1]),
            rotation=float(getattr(transform, "rotation", 0.0)),
            anchor_x=float(anchor[0]),
            anchor_y=float(anchor[1]),
            keyframes=keyframes,
            timing=dict(getattr(spec, "timing", {}) or {}),
        )

    def to_spec(self) -> Any:
        """Convert back into a :class:`CartoonLayerSpec`."""

        from ...core.timeline_schema.models import CartoonLayerSpec, Transform
        from ...core.timeline_schema.models import Keyframe as SchemaKeyframe

        return CartoonLayerSpec(
            id=self.id,
            name=self.name,
            kind=self.kind,  # type: ignore[arg-type]
            source=self.source,
            color=self.color,
            z=self.z,
            opacity=self.opacity,
            transform=Transform(
                position=[self.x, self.y],
                scale=[self.scale_x, self.scale_y],
                rotation=self.rotation,
                anchor=[self.anchor_x, self.anchor_y],
            ),
            keyframes=[
                SchemaKeyframe(frame=kf.frame, values=dict(kf.values), easing=kf.curve().kind)
                for kf in self.keyframes
            ],
            timing=dict(self.timing),
            visible=self.visible,
        )

    @property
    def static_properties(self) -> dict[str, float]:
        """The properties a layer carries when it has no keyframes."""

        return {
            "x": self.x,
            "y": self.y,
            "scale_x": self.scale_x,
            "scale_y": self.scale_y,
            "rotation": self.rotation,
            "opacity": self.opacity,
        }


@dataclass
class CartoonScene:
    """A 2D scene: layers, camera, dialogue and beat markers."""

    width: int = 1920
    height: int = 1080
    background: str = "#00000000"
    layers: list[Layer] = field(default_factory=list)
    fps: float = 30.0
    duration_frames: int = 60
    camera_x: float = 0.0
    camera_y: float = 0.0
    camera_scale: float = 1.0
    camera_keyframes: list[Keyframe] = field(default_factory=list)
    dialogue: list[dict[str, Any]] = field(default_factory=list)
    beats: list[dict[str, Any]] = field(default_factory=list)
    hold_frames: list[int] = field(default_factory=list)
    base_dir: str | None = None

    # -- conversion -----------------------------------------------------
    @classmethod
    def from_spec(cls, spec: Any) -> CartoonScene:
        """Build a scene from a :class:`CartoonSceneSpec`."""

        camera = getattr(spec, "camera", None)
        position = list(getattr(camera, "position", [0.0, 0.0]) or [0.0, 0.0])
        scale = list(getattr(camera, "scale", [1.0, 1.0]) or [1.0, 1.0])
        camera_keyframes = [
            Keyframe(
                frame=int(kf.frame),
                values={str(k): float(v) for k, v in kf.values.items() if isinstance(v, (int, float))},
                easing=kf.easing,
            )
            for kf in getattr(spec, "camera_keyframes", [])
        ]
        return cls(
            width=int(getattr(spec, "width", 1920)),
            height=int(getattr(spec, "height", 1080)),
            background=getattr(spec, "background", "#00000000"),
            layers=[Layer.from_spec(layer) for layer in getattr(spec, "layers", [])],
            camera_x=float(position[0]),
            camera_y=float(position[1]),
            camera_scale=float(scale[0]),
            camera_keyframes=camera_keyframes,
            dialogue=[dict(d) for d in getattr(spec, "dialogue", [])],
            beats=[dict(b) for b in getattr(spec, "beats", [])],
            hold_frames=list(getattr(spec, "hold_frames", []) or []),
        )

    def to_spec(self) -> Any:
        """Convert back into a :class:`CartoonSceneSpec`."""

        from ...core.timeline_schema.models import CartoonSceneSpec, Transform
        from ...core.timeline_schema.models import Keyframe as SchemaKeyframe

        return CartoonSceneSpec(
            width=self.width,
            height=self.height,
            background=self.background,
            layers=[layer.to_spec() for layer in self.layers],
            camera=Transform(
                position=[self.camera_x, self.camera_y],
                scale=[self.camera_scale, self.camera_scale],
            ),
            camera_keyframes=[
                SchemaKeyframe(frame=kf.frame, values=dict(kf.values), easing=kf.curve().kind)
                for kf in self.camera_keyframes
            ],
            dialogue=[dict(d) for d in self.dialogue],
            beats=[dict(b) for b in self.beats],
            hold_frames=list(self.hold_frames),
        )

    def sorted_layers(self) -> list[Layer]:
        """Layers in draw order: lowest ``z`` first."""

        return sorted(self.layers, key=lambda layer: (layer.z, layer.id))


@dataclass
class CartoonProject:
    """A sequence of 2D scenes."""

    name: str = "untitled"
    fps: float = 30.0
    width: int = 1920
    height: int = 1080
    scenes: list[CartoonScene] = field(default_factory=list)

    def total_frames(self) -> int:
        return sum(scene.duration_frames for scene in self.scenes)


# ---------------------------------------------------------------------------
# Evaluation
# ---------------------------------------------------------------------------

def evaluate_layer(layer: Layer, frame: int) -> dict[str, float]:
    """The effective property values of ``layer`` at an absolute ``frame``.

    Keyframes are stored per property inside ``Keyframe.values``.  Between two
    keyframes the value is interpolated with the easing of the *earlier*
    keyframe; before the first and after the last keyframe the value is held.
    """

    values = dict(layer.static_properties)

    if not layer.keyframes:
        return values

    ordered = sorted(layer.keyframes, key=lambda kf: kf.frame)
    properties: dict[str, list[Keyframe]] = {}
    for keyframe in ordered:
        for prop in keyframe.values:
            properties.setdefault(prop, []).append(keyframe)

    for prop, keyframes in properties.items():
        if prop not in values:
            # Unknown properties are still exposed so custom rigs can use them.
            values[prop] = float(keyframes[0].values[prop])
        if frame <= keyframes[0].frame:
            values[prop] = float(keyframes[0].values[prop])
            continue
        if frame >= keyframes[-1].frame:
            values[prop] = float(keyframes[-1].values[prop])
            continue
        for index in range(len(keyframes) - 1):
            before = keyframes[index]
            after = keyframes[index + 1]
            if before.frame <= frame <= after.frame:
                span = after.frame - before.frame
                t = 0.0 if span == 0 else (frame - before.frame) / span
                values[prop] = float(
                    interpolate(
                        float(before.values[prop]),
                        float(after.values[prop]),
                        t,
                        before.curve(),
                    )
                )
                break

    return values


def evaluate_scene(scene: CartoonScene, frame: int) -> dict[str, Any]:
    """The camera transform and every layer's effective values at ``frame``."""

    camera = {
        "x": scene.camera_x,
        "y": scene.camera_y,
        "scale": scene.camera_scale,
    }

    if scene.camera_keyframes:
        ordered = sorted(scene.camera_keyframes, key=lambda kf: kf.frame)
        merged = {
            "x": scene.camera_x,
            "y": scene.camera_y,
            "scale": scene.camera_scale,
        }
        properties: dict[str, list[Keyframe]] = {}
        for keyframe in ordered:
            for prop in keyframe.values:
                properties.setdefault(prop, []).append(keyframe)
        for prop, keyframes in properties.items():
            if frame <= keyframes[0].frame:
                merged[prop] = float(keyframes[0].values[prop])
                continue
            if frame >= keyframes[-1].frame:
                merged[prop] = float(keyframes[-1].values[prop])
                continue
            for index in range(len(keyframes) - 1):
                before = keyframes[index]
                after = keyframes[index + 1]
                if before.frame <= frame <= after.frame:
                    span = after.frame - before.frame
                    t = 0.0 if span == 0 else (frame - before.frame) / span
                    merged[prop] = float(
                        interpolate(
                            float(before.values[prop]),
                            float(after.values[prop]),
                            t,
                            before.curve(),
                        )
                    )
                    break
        camera = merged

    return {
        "frame": frame,
        "camera": camera,
        "layers": {layer.id: evaluate_layer(layer, frame) for layer in scene.layers},
        "hold": frame in set(scene.hold_frames),
    }


def resolve_source(scene: CartoonScene, layer: Layer) -> Path | None:
    """Resolve a layer's media path relative to the scene's base directory."""

    if not layer.source:
        return None
    source = Path(layer.source)
    if not source.is_absolute() and scene.base_dir:
        source = Path(scene.base_dir) / source
    return source


def lower_native_scene(scene: CartoonScene, frame: int) -> dict[str, Any] | None:
    """Lower a conservative primitive scene into the native rasterizer shape.

    ``None`` means the scene uses a feature for which Python/Pillow remains the
    reference implementation.  Keeping the gate explicit prevents a partial
    native implementation from silently changing image output.
    """

    background = str(scene.background or "#00000000").lower()
    if background not in {"#00000000", "#000000000", "transparent", "#00000000ff"}:
        return None
    if scene.camera_x or scene.camera_y or scene.camera_scale != 1.0 or scene.camera_keyframes:
        return None

    state = evaluate_scene(scene, frame)
    lowered: list[dict[str, Any]] = []
    for layer in scene.sorted_layers():
        if not layer.visible or layer.kind.lower() not in {"solid", "vector"}:
            if layer.visible:
                return None
            continue
        props = state["layers"].get(layer.id, {})
        if layer.keyframes:
            # Animated primitive properties are only safe when evaluation did
            # not introduce any unsupported custom property.
            if any(key not in {"x", "y", "scale_x", "scale_y", "rotation", "opacity"} for key in props):
                return None
        if (
            float(props.get("scale_x", layer.scale_x)) != 1.0
            or float(props.get("scale_y", layer.scale_y)) != 1.0
            or float(props.get("rotation", layer.rotation)) != 0.0
            or float(props.get("anchor_x", layer.anchor_x)) != 0.5
            or float(props.get("anchor_y", layer.anchor_y)) != 0.5
        ):
            return None
        lowered.append(
            {
                "id": layer.id,
                "kind": layer.kind.lower(),
                "color": layer.color,
                "x": float(props.get("x", layer.x)),
                "y": float(props.get("y", layer.y)),
                "opacity": float(props.get("opacity", layer.opacity)),
                "anchor_x": 0.5,
                "anchor_y": 0.5,
            }
        )
    return {"width": scene.width, "height": scene.height, "layers": lowered, "frame": frame}
