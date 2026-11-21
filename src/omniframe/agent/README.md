# OmniFrame Studio

Open-source, agent-first video & animation control platform that unifies code-driven frame-by-frame rendering, 2D cartoon pipeline, and professional NLE/compositing bridges under one architecture.

## Quick Start

```bash
# Install
pip install -e .

# Doctor report
omniframe doctor

# List available tools
omniframe tools --list

# Validate a project
omniframe project validate examples/code-explainer/project.json

# Render code-driven scene
omniframe project render examples/code-explainer/project.json --out out/explainer

# Compose video from frames
omniframe project compose examples/code-explainer/project.json --frames out/explainer/intro --out out/code-explainer.mp4

# Inspect video frames
omniframe inspect media out/cartoon-bounce.mp4 --output-dir out/_inspect --count 8 --contact-sheet out/_inspect/cartoon-sheet.png
```

## Core Features

### Code-Driven Rendering
Render HTML/CSS/JS scenes frame-by-frame with deterministic PRNG output:

```python
from omniframe.engines.code_video import render_code_scene

result = render_code_scene({
    "html": "<html><body>Hello</body></html>",
    "output_dir": "/tmp/frames",
    "width": 1280,
    "height": 720,
    "fps": 30,
    "duration_frames": 60,
    "seed": 42,
})
```

### 2D Cartoon Animation
Render cartoon scenes with layers, keyframes, and Pillow compositing:

```python
from omniframe.engines.cartoon_2d import render_cartoon_frames

result = render_cartoon_frames({
    "scene": {
        "width": 960,
        "height": 540,
        "background": "#101425",
        "layers": [...],
    },
    "output_dir": "/tmp/cartoon",
    "fps": 24,
    "duration_frames": 48,
})
```

### Video Composition
Assemble PNG frames into video with FFmpeg, including audio mixing, subtitles, LUTs, and export presets:

```python
from omniframe.engines.compositor import compose_video

compose_video({
    "frames": ["frame_000001.png", "frame_000002.png", "..."],
    "output": "out.mp4",
    "fps": 30,
    "preset": "h264",
})
```

### DCC Bridges
Adapters for Premiere Pro, After Effects, DaVinci Resolve, CapCut, and Krita — all degrade gracefully when host apps are absent.

### Project Translation
Bidirectional translators between OmniProject and host formats: FCPXML, EDL, CapCut draft, AE manifest, Resolve XML.

## CLI Reference

### Subcommands

| Command | Description |
|---------|-------------|
| `doctor` | Report environment status |
| `tools --list` | List the current generated tool manifest |
| `project init <name>` | Initialize new project |
| `project validate <file>` | Validate OmniProject |
| `project render <file> --out <dir>` | Render to PNG frames |
| `project compose <file> --frames <dir> --out <video.mp4>` | Compose video from frames |
| `project translate --translator <format> <file> <output>` | Translate formats |
| `project report <file>` | Structured timeline report |
| `checkpoint save <file> --label <name>` | Snapshot project |
| `checkpoint list` | List stored checkpoints |
| `checkpoint restore <id> <file>` | Restore from checkpoint |
| `checkpoint diff <id1> <id2>` | Diff two checkpoints |
| `bridge list` | List DCC bridges and availability |
| `bridge detect <name>` | Detect host app |
| `bridge generate_script <name> <file> <dir>` | Generate host script |
| `bridge inspect <name> <target>` | Read-only project inspection |
| `engine route --capability <name>` | Choose best engine |
| `inspect media <video> --output-dir <dir> --count <n> --contact-sheet <sheet.png>` | Extract frames + contact sheet |
| `inspect frames <directory> --output <sheet.png> --columns <n> --strip` | Build contact sheet from frames |

### Global Options
- `--help` — Show help for any command
- `--version` — Show version (0.1.0)

## Platform Stack

- **Language**: Python-first hybrid (core/CLI/bridges in Python, frame capture via Playwright+Chromium)
- **Python**: 3.10+ (Windows 10/11, PowerShell)
- **Dependencies**: stdlib + Pillow + pydantic + PyYAML + typer; Playwright optional via `[render]` extra
- **No shell=True, no secrets, no binary patching/DRM circumvention**
- **RAE methodology**: reverse-engineer project formats read-only; prefer documented scripting APIs
- **Agent-first**: every capability exposed as typed action with JSON Schema, dry-run/validation, checkpoint/rollback, visual inspection (contact sheets)
- **Determinism**: seeded PRNG per frame, frozen CSS animations, exact frame numbering

## Error Model

Structured `OmniFrameError` hierarchy with stable `code` field for agent branching:
- `E_RENDER` — Rendering failures
- `E_BRIDGE_UNAVAILABLE` — Host DCC app not found
- `E_SCHEMA` — JSON Schema validation errors
- `E_VALIDATION` — Semantic validation errors with stable codes
- `E_ENGINE_UNAVAILABLE` — Engine not installed/available

## Checkpoint Storage

Filesystem JSON snapshots under `.omniframe/checkpoints/` with SHA-256 content hash for change detection.

## Test Markers

- `@pytest.mark.render` — Tests requiring Playwright browser frame capture
- `@pytest.mark.slow` — Tests requiring FFmpeg integration

## Examples

| Example | Description | Output |
|---------|-------------|--------|
| `code-explainer` | 90-frame HTML/JS kinetic title | `code-explainer.mp4 (30.8 KB)` |
| `cartoon-bounce` | 48-frame 2D squash/stretch ball | `cartoon-bounce.mp4 (15.9 KB)` |

## Development

```bash
# Run all tests
python -m pytest -q

# Run with markers
python -m pytest -q -m "not render"    # skip browser tests
python -m pytest -q -m "render"        # run browser tests only
```

## License

MIT. See `LICENSE` for details.