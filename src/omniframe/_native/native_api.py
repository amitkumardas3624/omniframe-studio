"""Stable Python-facing API for optional native primitives.

This module intentionally remains importable without a compiler, pybind11, or a
compiled extension.  Callers can use the same names in both modes.
"""

from __future__ import annotations

from typing import Any

from .fallback import FramePipeSink


def _parse_color(value: Any) -> tuple[int, int, int, int]:
    text = str(value or "#000000").strip().lstrip("#")
    if len(text) == 3:
        text = "".join(ch * 2 for ch in text) + "FF"
    elif len(text) == 6:
        text += "FF"
    if len(text) != 8:
        return (0, 0, 0, 255)
    try:
        return tuple(int(text[index : index + 2], 16) for index in range(0, 8, 2))  # type: ignore[return-value]
    except ValueError:
        return (0, 0, 0, 255)


class CartoonRasterizer:
    """Fallback rasterizer with the native class's public method shape."""

    backend = "python"

    def render_rgba(
        self,
        width: int,
        height: int,
        layers: list[dict[str, Any]],
        frame: int = 0,
        *,
        background: Any = "#00000000",
    ) -> bytes:
        del frame
        from PIL import Image, ImageDraw

        canvas = Image.new("RGBA", (int(width), int(height)), _parse_color(background))
        for layer in layers:
            kind = str(layer.get("kind", "")).lower()
            if kind not in {"solid", "vector"}:
                raise NotImplementedError(f"unsupported native cartoon layer: {kind}")
            color = _parse_color(layer.get("color", "#000000"))
            opacity = max(0.0, min(1.0, float(layer.get("opacity", 1.0))))
            color = (*color[:3], int(color[3] * opacity))
            if kind == "solid":
                image = Image.new("RGBA", (100, 100), color)
                draw = ImageDraw.Draw(image)
                draw.rectangle([0, 0, 99, 99], outline=(255, 255, 255, 90))
            else:
                image = Image.new("RGBA", (100, 100), (0, 0, 0, 0))
                ImageDraw.Draw(image).ellipse([0, 0, 99, 99], fill=color)
            scale_x = float(layer.get("scale_x", 1.0))
            scale_y = float(layer.get("scale_y", 1.0))
            if scale_x != 1.0 or scale_y != 1.0:
                image = image.resize(
                    (max(1, round(image.width * abs(scale_x))), max(1, round(image.height * abs(scale_y))))
                )
                if scale_x < 0:
                    image = image.transpose(Image.Transpose.FLIP_LEFT_RIGHT)
                if scale_y < 0:
                    image = image.transpose(Image.Transpose.FLIP_TOP_BOTTOM)
            if float(layer.get("rotation", 0.0)):
                image = image.rotate(-float(layer["rotation"]), expand=True)
            x = float(layer.get("x", 0.0)) - float(layer.get("anchor_x", 0.5)) * image.width
            y = float(layer.get("y", 0.0)) - float(layer.get("anchor_y", 0.5)) * image.height
            canvas.alpha_composite(image, (round(x), round(y)))
        return canvas.tobytes("raw", "RGBA")


# The Python API's fallback is intentionally usable even when the loader reports
# that the compiled module is absent.
def native_available() -> bool:
    from .loader import native_available as _native_available

    return _native_available()


__all__ = ["CartoonRasterizer", "FramePipeSink", "native_available"]
