#!/usr/bin/env python3
"""Render the kinetic intro template from `content.json`.

The template is data, not code to copy: edit ``content.json`` for a new brief.
Frame evaluation stays inside ``scene.js``'s single pure ``seek(t)`` function.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1] / "src"))

from omniframe.engines.code_video import CodeScene, CodeVideoRenderer  # noqa: E402

MARKER = "// === FRAME ==="
WIDTH = 1280
HEIGHT = 720
FPS = 24.0


def build_scene(content: dict, *, duration_frames: int = 373) -> CodeScene:
    html = (HERE / "scene.html").read_text(encoding="utf-8")
    script = (HERE / "scene.js").read_text(encoding="utf-8")
    if script.count(MARKER) != 1:
        raise SystemExit(f"scene.js must contain exactly one {MARKER!r} marker")
    bootstrap, javascript = script.split(MARKER, 1)
    return CodeScene(
        html=html,
        javascript=javascript.strip(),
        bootstrap=bootstrap.strip(),
        width=WIDTH,
        height=HEIGHT,
        fps=FPS,
        duration_frames=duration_frames,
        seed=7,
        params=dict(content),
        background=content.get("paper", "#FAFAFA"),
        settle_timeout_ms=1000,
    )


def read_content(path: str | None = None) -> dict:
    source = Path(path) if path else HERE / "content.json"
    return json.loads(source.read_text(encoding="utf-8"))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", default="out/kinetic-intro", help="frame output directory")
    parser.add_argument("--backend", default="auto", help="auto | playwright | stub")
    parser.add_argument("--frames", type=int, default=373, help="frames to render")
    parser.add_argument("--content", default=None, help="alternate content JSON")
    parser.add_argument("--verify", action="store_true", help="render 4 frames twice and compare")
    args = parser.parse_args()

    content = read_content(args.content)
    if args.verify:
        renderer = CodeVideoRenderer(backend=args.backend)
        scene = build_scene(content, duration_frames=4)
        first = renderer.render(scene, Path(args.out) / "verify-a")
        second = renderer.render(scene, Path(args.out) / "verify-b")
        same = (
            first.ok
            and second.ok
            and len(first.frames) == len(second.frames)
            and all(
                a.read_bytes() == b.read_bytes()
                for a, b in zip(first.frames, second.frames, strict=True)
            )
        )
        print(json.dumps({
            "deterministic": same,
            "backend": renderer.backend_name,
            "verification_level": first.verification_level,
            "frames": len(first.frames),
            "issues": [str(i) for i in first.issues + second.issues],
        }, indent=2))
        return 0 if same else 1

    scene = build_scene(content, duration_frames=args.frames)
    renderer = CodeVideoRenderer(backend=args.backend)
    result = renderer.render(scene, args.out)
    print(json.dumps({
        "ok": result.ok,
        "backend": result.backend,
        "verification_level": result.verification_level,
        "frames": len(result.frames),
        "fps": result.fps,
        "seconds": round(result.duration_frames / result.fps, 3),
        "frame_dir": str(result.frame_dir),
        "issues": [str(i) for i in result.issues[:10]],
    }, indent=2))
    return 0 if result.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())