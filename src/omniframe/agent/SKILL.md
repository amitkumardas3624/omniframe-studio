# OmniFrame Studio Agent Skill

## Overview
This skill provides the agent-facing surface for OmniFrame Studio — an open-source, agent-first video & animation control platform. The platform unifies code-driven frame-by-frame rendering, 2D cartoon pipelines, and professional NLE/compositing bridges under one architecture.

## Agent Interaction Model

### CLI Entry Point
```
omniframe <subcommand> [options]
```

### Core Commands for Agents
All platform capabilities are exposed through the Typer CLI and can be invoked programmatically via the Python API or MCP (Model Context Protocol).

#### Environment & Doctor
- `omniframe doctor` — Report environment status (Python, Node, FFmpeg, Chromium, native accelerator, host app detection)
- `omniframe tools --list` — List the current generated tool manifest with JSON Schema contracts

#### Project Lifecycle
- `omniframe project validate <project.json>` — Validate an OmniProject document
- `omniframe project init <name>` — Initialize a new OmniProject skeleton
- `omniframe project render <project.json> --out <dir>` — Render to PNG frame sequence
- `omniframe project render <project.json> --stream-to-ffmpeg <video>` — Opt-in raw RGBA streaming for exactly one renderable clip; incompatible with `--resume`
- `omniframe project compose <project.json> --frames <dir> --out <video.mp4>` — Assemble video from frames
- `omniframe project translate --translator <format> <project.json> --out <output>` — Translate between formats (FCPXML, EDL, CapCut, AE, Resolve)
- `omniframe project report <project.json>` — Get structured timeline report

#### Checkpoint & Rollback
- `omniframe checkpoint save <project.json> --label <name>` — Snapshot project state
- `omniframe checkpoint list` — List all stored checkpoints
- `omniframe checkpoint restore <id> --project <project.json>` — Restore a checkpoint
- `omniframe checkpoint diff <before> <after>` — Diff two checkpoints

#### Bridge Automation
- `omniframe bridge list` — List all DCC bridges and availability
- `omniframe bridge detect <name>` — Detect if a host app is installed
- `omniframe bridge script <name> <project.json> --out <output_dir>` — Generate host script/project

#### Inspection & Visual Review
- `omniframe inspect media --video <video.mp4> --output-dir <dir> --count <n> --contact-sheet <sheet.png>` — Extract frames + contact sheet
- `omniframe inspect frames --directory <directory> --output <sheet.png> --columns <n> --strip` — Build contact sheet from frames

#### Engine Routing
- `omniframe route --capability <name>` — Choose best engine for a task

### Python API
```python
from omniframe import (
    register_builtin_actions,
    get_registry,
    EngineRouter,
    CheckpointStore,
)
from omniframe.engines import render_code_scene, render_cartoon_frames, compose_video
from omniframe.bridges import list_bridges, get_bridge
```

### MCP (Model Context Protocol) Server
The platform exposes an MCP server that publishes the same action schemas and contracts via:
```
mcp__omniframe list_tools
mcp__omniframe call_tool <tool_name> <arguments_json>
```

## Action Registry

All built-in actions are registered in `core.agent_runtime.actions.register_builtin_actions()`. Each action has:

- **JSON Schema input/output contracts**
- **Error code mappings** (E_RENDER, E_BRIDGE_UNAVAILABLE, E_SCHEMA, E_VALIDATION, etc.)
- **Tags** for categorization (doctor, render, checkpoint, bridge, inspector, etc.)
- **Engine assignment** (core, code_video, cartoon_2d, compositor, bridges)

### Registered Actions Summary
| Action | Engine | Tags | Purpose |
|--------|--------|------|---------|
| environment.detect | core | doctor, diagnostics | Probe host runtimes and apps |
| project.validate | core | project, validation | Validate OmniProject JSON |
| project.report | core | project, timeline | Structured timeline summary |
| project.translate | core | project, translate | Format translation |
| engine.route | core | planner | Engine selection |
| checkpoint.save | core | checkpoint, safety | Snapshot project |
| checkpoint.list | core | checkpoint | List checkpoints |
| checkpoint.restore | core | checkpoint, rollback | Restore from checkpoint |
| checkpoint.diff | core | checkpoint, diff | Diff two checkpoints |
| render.code_scene | code_video | render, code | HTML/CSS/JS scene render |
| render.cartoon_frames | cartoon_2d | render, 2d | 2D cartoon frame render |
| compose.video | compositor | compose, export | FFmpeg video assembly |
| inspect.media | core | inspect, vision | Video frame extraction + contact sheet |
| inspect.frames | core | inspect, vision | Frame directory contact sheet/strip |
| bridge.list | bridges | bridge, doctor | List DCC bridges |
| bridge.detect | bridges | bridge, doctor | Host app detection |
| bridge.generate_script | bridges | bridge, automation | Generate host script |
| bridge.inspect | bridges | bridge, rae, inspect | Read-only project inspection |
| timeline.diff | core | diff, timeline | Project document diff |

## Determinism Strategy
- **Frame-level seeded PRNG** (mulberry32) for reproducible output
- **CSS animation freeze** at render time
- **Double-rAF settle** before frame capture
- **`__OMNIFRAME_READY__`** opt-in for signaling render completion
- **Per-frame seed** support in the `render.code_scene` action

## Error Model
Structured `OmniFrameError` hierarchy with stable `code` field for agent branching:
- `E_RENDER` — Rendering failures (engine unavailable, dependency missing)
- `E_BRIDGE_UNAVAILABLE` — Host DCC app not found
- `E_SCHEMA` — JSON Schema validation errors
- `E_VALIDATION` — Semantic validation errors with stable codes
- `E_ENGINE_UNAVAILABLE` — Engine not installed/available

## Checkpoint Storage
- **Filesystem JSON snapshots** under `.omniframe/checkpoints/`
- **SHA-256 content hash** for change detection
- **Per-project directory** isolation
- **Save/list/restore/diff** operations via `CheckpointStore`

## Development & Contribution
- **Python 3.10+** (Windows 10/11, PowerShell)
- **Dependencies**: `pydantic>=2.6,<3`, `PyYAML>=6.0`, `typer>=0.12`, `Pillow>=10.2`
- **Optional**: `playwright>=1.44` (for `[render]` extra), `pybind11>=2.11` (for `[native]` extra and CMake C++17 build)
- **Fallback policy**: missing compiler, pybind11, or `_omniframe_native` selects the Python implementation automatically
- **Testing**: `pytest>=8.0`; run the suite with `python -m pytest -q`; `@pytest.mark.render` for browser tests, `@pytest.mark.slow` for FFmpeg integration
- **Package**: `pip install -e .` from repo root
- **Entry point**: `omniframe` CLI script (Typer-based)

## Versioning
- Current: `0.2.1` (Alpha)
- See `pyproject.toml` for full package metadata