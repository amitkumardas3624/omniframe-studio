"""Frame rendering for the 2D cartoon pipeline (Pillow based)."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Sequence

from ...core.logging import get_logger
from .scene import CartoonScene, Layer, evaluate_scene, resolve_source

LOG = get_logger("engines.cartoon_2d.render")

#: The nominal size of a ``solid`` layer.
SOLID_SIZE = 100
#: The nominal radius of a ``vector`` layer.
VECTOR_RADIUS = 50


def parse_color(value: str, default: tuple[int, int, int, int] = (0, 0, 0, 255)) -> tuple[int, int, int, int]:
    """Parse ``#RRGGBB`` / ``#RRGGBBAA`` / ``#RGB`` into an RGBA tuple."""

    text = str(value or "").strip().lstrip("#")
    if len(text) == 3:
        text = "".join(ch * 2 for ch in text) + "FF"
    if len(text) == 6:
        text += "FF"
    if len(text) != 8:
        return default
    try:
        return (
            int(text[0:2], 16),
            int(text[2:4], 16),
            int(text[4:6], 16),
            int(text[6:8], 16),
        )
    except ValueError:
        return default


def _font(size: int):
    from PIL import ImageFont

    try:
        return ImageFont.load_default(size=size)
    except TypeError:  # pragma: no cover - very old Pillow
        return ImageFont.load_default()


def _layer_image(scene: CartoonScene, layer: Layer, props: dict[str, float]):
    """Build the RGBA bitmap of a single layer at a given frame."""

    from PIL import Image, ImageDraw

    kind = (layer.kind or "image").lower()

    if kind == "solid":
        image = Image.new("RGBA", (SOLID_SIZE, SOLID_SIZE), parse_color(layer.color))
        draw = ImageDraw.Draw(image)
        draw.rectangle([0, 0, SOLID_SIZE - 1, SOLID_SIZE - 1], outline=(255, 255, 255, 90))
        return image

    if kind == "vector":
        size = VECTOR_RADIUS * 2
        image = Image.new("RGBA", (size, size), (0, 0, 0, 0))
        draw = ImageDraw.Draw(image)
        draw.ellipse([0, 0, size - 1, size - 1], fill=parse_color(layer.color))
        return image

    if kind == "text":
        text = str(layer.timing.get("text", layer.timing.get("label", layer.name)))
        font_size = int(layer.timing.get("font_size", 48))
        font = _font(font_size)
        image = Image.new("RGBA", (1, 1), (0, 0, 0, 0))
        draw = ImageDraw.Draw(image)
        box = draw.textbbox((0, 0), text, font=font)
        width = max(1, box[2] - box[0] + 8)
        height = max(1, box[3] - box[1] + 8)
        image = Image.new("RGBA", (width, height), (0, 0, 0, 0))
        draw = ImageDraw.Draw(image)
        draw.text((4 - box[0], 4 - box[1]), text, font=font, fill=parse_color(layer.color))
        return image

    # image
    source = resolve_source(scene, layer)
    if source is None or not source.exists():
        LOG.warning("layer source not found", extra={"layer": layer.id, "source": str(source)})
        return None
    try:
        with Image.open(source) as handle:
            return handle.convert("RGBA")
    except Exception as exc:
        LOG.warning("could not read layer source", extra={"layer": layer.id, "error": str(exc)})
        return None


def _apply_transform(image, props: dict[str, float]):
    """Scale and rotate a layer bitmap around its anchor."""

    from PIL import Image

    scale_x = float(props.get("scale_x", 1.0))
    scale_y = float(props.get("scale_y", 1.0))
    rotation = float(props.get("rotation", 0.0))

    if abs(scale_x - 1.0) > 1e-6 or abs(scale_y - 1.0) > 1e-6:
        width = max(1, int(round(image.width * abs(scale_x))))
        height = max(1, int(round(image.height * abs(scale_y))))
        image = image.resize((width, height), Image.LANCZOS)
        if scale_x < 0 or scale_y < 0:
            image = image.transpose(Image.FLIP_LEFT_RIGHT)

    if abs(rotation) > 1e-6:
        image = image.rotate(-rotation, resample=Image.BICUBIC, expand=True)

    return image


def _apply_opacity(image, opacity: float):
    from PIL import Image

    opacity = max(0.0, min(1.0, float(opacity)))
    if opacity >= 0.999:
        return image
    alpha = image.getchannel("A").point(lambda value: int(value * opacity))
    image = image.copy()
    image.putalpha(alpha)
    return image


def render_frame(scene: CartoonScene, frame: int, output_path: str | Path) -> Path:
    """Composite ``scene`` at an absolute ``frame`` and write it as a PNG."""

    from PIL import Image

    canvas = Image.new("RGBA", (scene.width, scene.height), parse_color(scene.background))
    state = evaluate_scene(scene, frame)
    camera = state["camera"]

    for layer in scene.sorted_layers():
        if not layer.visible:
            continue
        props = state["layers"].get(layer.id, {})
        image = _layer_image(scene, layer, props)
        if image is None:
            continue

        image = _apply_transform(image, props)
        image = _apply_opacity(image, float(props.get("opacity", layer.opacity)))

        anchor_x = float(props.get("anchor_x", layer.anchor_x))
        anchor_y = float(props.get("anchor_y", layer.anchor_y))
        pos_x = float(props.get("x", layer.x)) + float(camera.get("x", 0.0))
        pos_y = float(props.get("y", layer.y)) + float(camera.get("y", 0.0))

        left = int(round(pos_x - anchor_x * image.width))
        top = int(round(pos_y - anchor_y * image.height))
        canvas.alpha_composite(image, (left, top))

    target = Path(output_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(target)
    return target


def frame_filename(frame: int) -> str:
    """The canonical frame file name."""

    return f"frame_{frame:06d}.png"


def render_frames(
    scene: CartoonScene,
    output_dir: str | Path,
    *,
    resume: bool = False,
) -> list[Path]:
    """Render the whole scene to a PNG sequence and return the frame paths."""

    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    frames: list[Path] = []
    for frame in range(scene.duration_frames):
        target = out_dir / frame_filename(frame)
        if resume and target.exists():
            frames.append(target)
            continue
        frames.append(render_frame(scene, frame, target))
    return frames


def build_contact_sheet(
    frames: Sequence[str | Path],
    output_path: str | Path,
    *,
    columns: int = 4,
    thumb_width: int = 320,
    padding: int = 8,
) -> Path:
    """Compose a grid contact sheet from rendered frames."""

    from PIL import Image, ImageDraw

    paths = [Path(f) for f in frames]
    if not paths:
        raise ValueError("build_contact_sheet requires at least one frame.")

    columns = max(1, min(columns, len(paths)))
    rows = (len(paths) + columns - 1) // columns

    with Image.open(paths[0]) as first:
        ratio = first.height / max(1, first.width)
    thumb_height = max(1, int(thumb_width * ratio))
    label_height = 18

    sheet = Image.new(
        "RGB",
        (columns * thumb_width + (columns + 1) * padding,
         rows * (thumb_height + label_height) + (rows + 1) * padding),
        (16, 16, 20),
    )
    draw = ImageDraw.Draw(sheet)

    for index, path in enumerate(paths):
        row, col = divmod(index, columns)
        x = padding + col * (thumb_width + padding)
        y = padding + row * (thumb_height + label_height + padding)
        try:
            with Image.open(path) as handle:
                sheet.paste(handle.convert("RGB").resize((thumb_width, thumb_height), Image.LANCZOS), (x, y))
        except Exception as exc:  # pragma: no cover - corrupt frame
            LOG.warning("could not paste frame", extra={"frame": str(path), "error": str(exc)})
            continue
        draw.text((x + 2, y + thumb_height + 3), path.stem[-14:], fill=(200, 200, 210))

    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(out)
    return out


def build_frame_strip(
    frames: Sequence[str | Path],
    output_path: str | Path,
    *,
    thumb_width: int = 240,
    padding: int = 4,
) -> Path:
    """Compose a single horizontal strip for judging timing and pacing."""

    from PIL import Image

    paths = [Path(f) for f in frames]
    if not paths:
        raise ValueError("build_frame_strip requires at least one frame.")

    with Image.open(paths[0]) as first:
        ratio = first.height / max(1, first.width)
    thumb_height = max(1, int(thumb_width * ratio))

    strip = Image.new(
        "RGB",
        (len(paths) * thumb_width + (len(paths) + 1) * padding, thumb_height + 2 * padding),
        (16, 16, 20),
    )
    for index, path in enumerate(paths):
        x = padding + index * (thumb_width + padding)
        try:
            with Image.open(path) as handle:
                strip.paste(handle.convert("RGB").resize((thumb_width, thumb_height), Image.LANCZOS), (x, padding))
        except Exception as exc:  # pragma: no cover
            LOG.warning("could not paste frame", extra={"frame": str(path), "error": str(exc)})

    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    strip.save(out)
    return out
