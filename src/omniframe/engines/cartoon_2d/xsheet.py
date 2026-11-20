"""Exposure sheets (x-sheets).

An x-sheet is the classic animator's planning table: one column per frame,
one row per layer, so timing, holds and breakdowns can be read at a glance.
"""

from __future__ import annotations

import csv
from pathlib import Path
from typing import Any

from .scene import CartoonScene, evaluate_scene


def _cell(props: dict[str, float]) -> str:
    """A compact, human readable cell for a layer row."""

    parts = []
    for key in ("x", "y", "scale_x", "scale_y", "rotation", "opacity"):
        if key in props:
            value = float(props[key])
            parts.append(f"{key}={value:.2f}")
    return " ".join(parts)


def _rows(scene: CartoonScene) -> list[tuple[str, list[str]]]:
    """Build the row labels and cells of the sheet."""

    frames = range(scene.duration_frames)
    rows: list[tuple[str, list[str]]] = []

    camera_values: list[str] = []
    layer_values: dict[str, list[str]] = {layer.id: [] for layer in scene.sorted_layers()}
    dialogue_cells: list[str] = []
    beat_cells: list[str] = []
    hold_cells: list[str] = []

    dialogue_by_frame = {int(d.get("frame", -1)): d for d in scene.dialogue}
    beats_by_frame: dict[int, list[str]] = {}
    for beat in scene.beats:
        beats_by_frame.setdefault(int(beat.get("frame", -1)), []).append(str(beat.get("beat", "")))

    for frame in frames:
        state = evaluate_scene(scene, frame)
        camera = state["camera"]
        camera_values.append(f"x={camera.get('x', 0):.1f} y={camera.get('y', 0):.1f} s={camera.get('scale', 1):.2f}")
        for layer in scene.sorted_layers():
            layer_values[layer.id].append(_cell(state["layers"].get(layer.id, {})))

        marker = dialogue_by_frame.get(frame)
        dialogue_cells.append(
            f"{marker.get('speaker', '')}:{marker.get('text', '')}" if marker else ""
        )
        beat_cells.append(",".join(beats_by_frame.get(frame, [])))
        hold_cells.append("HOLD" if frame in set(scene.hold_frames) else "")

    rows.append(("camera", camera_values))
    for layer in scene.sorted_layers():
        rows.append((f"{layer.id} ({layer.kind})", layer_values[layer.id]))
    rows.append(("dialogue", dialogue_cells))
    rows.append(("beats", beat_cells))
    rows.append(("hold", hold_cells))
    return rows


def build_xsheet(
    scene: CartoonScene,
    output_path: str | Path,
    *,
    fmt: str = "csv",
) -> Path:
    """Write an exposure sheet for ``scene``.

    ``fmt`` is ``"csv"`` (default) or ``"markdown"``.
    """

    target = Path(output_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    rows = _rows(scene)
    header = [str(frame) for frame in range(scene.duration_frames)]

    if fmt.lower() == "markdown":
        lines = ["| layer | " + " | ".join(header) + " |"]
        lines.append("|---" * (len(header) + 1) + "|")
        for label, cells in rows:
            lines.append(f"| {label} | " + " | ".join(cells) + " |")
        target.write_text("\n".join(lines) + "\n", encoding="utf-8")
        return target

    with target.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["layer", *header])
        for label, cells in rows:
            writer.writerow([label, *cells])
    return target


def xsheet_summary(scene: CartoonScene) -> dict[str, Any]:
    """A structured summary of the scene's timing."""

    return {
        "frames": scene.duration_frames,
        "fps": scene.fps,
        "duration_seconds": round(scene.duration_frames / scene.fps, 3) if scene.fps else 0,
        "layers": [layer.id for layer in scene.sorted_layers()],
        "dialogue_markers": len(scene.dialogue),
        "beat_markers": len(scene.beats),
        "hold_frames": list(scene.hold_frames),
    }
