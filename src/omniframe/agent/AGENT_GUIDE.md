# Agent Guide: OmniFrame Studio

This guide helps agents (LLM-based automation) operate the OmniFrame Studio platform programmatically.

## Agent Interaction Patterns

### 1. Discovery Pattern
```python
# Step 1: Check environment
result = call_action("environment.detect", {"include_hosts": True})
# Returns: python version, node, ffmpeg, chromium, and host app detection

# Step 2: List available tools
result = call_action("tools --list")  
# Returns: JSON Schema for all 18 actions

# Step 3: Route to best engine
result = call_action("engine.route", {
    "capability": "code_scene_render",
    "required_capabilities": ["html_render", "playwright"]
})
```

### 2. Project Workflow Pattern
```python
# Validate project file
result = call_action("project.validate", {
    "project": "examples/code-explainer/project.json",
    "check_assets": True
})

# If valid, render
result = call_action("project.render", {
    "project": "examples/code-explainer/project.json",
    "out": "/tmp/rendered"
})

# Compose to video
result = call_action("project.compose", {
    "project": "examples/code-explainer/project.json",
    "frames": "/tmp/rendered/frames",
    "out": "/tmp/output.mp4"
})
```

### 3. Checkpoint Safety Pattern
```python
# Save before destructive operation
result = call_action("checkpoint.save", {
    "project": "my_project.json",
    "label": "before_render"
})

# ... perform operations ...

# Restore if needed
result = call_action("checkpoint.restore", {
    "checkpoint_id": "cp_abc123",
    "project": "my_project.json"
})
```

### 4. Bridge Automation Pattern
```python
# Detect if host app is available
result = call_action("bridge.detect", {
    "bridge": "premiere_pro"
})

# If available, generate script
result = call_action("bridge.generate_script", {
    "bridge": "premiere_pro",
    "project": "my_project.json",
    "output_dir": "/tmp/scripts"
})

# Inspect project structure
result = call_action("bridge.inspect", {
    "bridge": "krita",
    "target": "my_project.json"
})
```

## Available Actions (Full List)

### Environment & Diagnostics
- `environment.detect` — Probe host machine for runtimes and applications

### Project Management
- `project.validate` — Validate OmniProject document
- `project.report` — Structured timeline summary
- `project.translate` — Translate between formats
- `engine.route` — Choose best engine for task

### Checkpoint & Rollback
- `checkpoint.save` — Snapshot project state
- `checkpoint.list` — List all checkpoints
- `checkpoint.restore` — Restore from checkpoint
- `checkpoint.diff` — Diff two checkpoints

### Rendering
- `render.code_scene` — Render HTML/CSS/JS to PNG frames
- `render.cartoon_frames` — Render 2D cartoon to PNG frame sequence
- `compose.video` — Assemble PNG frames into video with FFmpeg

### Inspection & Vision
- `inspect.media` — Extract video frames + contact sheet
- `inspect.frames` — Build contact sheet/strip from frame directory

### Bridge Automation
- `bridge.list` — List DCC bridges and availability
- `bridge.detect` — Detect host application
- `bridge.generate_script` — Generate host script/project
- `bridge.inspect` — Read-only project inspection

### Timeline Diffing
- `timeline.diff` — Diff two project documents

## JSON Schema Contracts

Every action follows a consistent contract pattern:

```json
{
  "action": "render.code_scene",
  "input": {
    "type": "object",
    "properties": {
      "html": {"type": "string"},
      "output_dir": {"type": "string"},
      "fps": {"type": "number", "default": 30.0}
    },
    "required": ["html", "output_dir"]
  },
  "output": {
    "type": "object",
    "properties": {
      "frames": {"type": "array", "items": {"type": "string"}},
      "count": {"type": "integer"}
    }
  },
  "error_codes": ["E_RENDER", "E_ENGINE_UNAVAILABLE"],
  "tags": ["render", "code"]
}
```

Agents should:
1. **Validate input** against the JSON Schema before calling
2. **Handle error codes** in branching logic
3. **Use tags** for categorization and routing
4. **Respect `mutating` flag** for checkpoint/restore operations

## Determinism for Agents

All rendering operations support seeded PRNG for reproducible output:

```python
# Code scene with deterministic output
result = call_action("render.code_scene", {
    "html": scene_html,
    "output_dir": "/frames",
    "seed": 42,  # Reproducible across runs
    "transparent": false
})

# Cartoon frames with deterministic interpolation
result = call_action("render.cartoon_frames", {
    "scene": cartoon_spec,
    "output_dir": "/frames",
    "seed": 123
})
```

## Error Handling

Agents should branch on the `code` field of `OmniFrameError`:

```python
try:
    result = call_action("render.code_scene", {"html": html, "output_dir": "/frames"})
except OmniFrameError as e:
    if e.code == "E_RENDER":
        # Retry or fallback
    elif e.code == "E_ENGINE_UNAVAILABLE":
        # Check if dependency is missing
    elif e.code == "E_SCHEMA":
        # Fix input validation
    else:
        # Unknown error
```

## MCP (Model Context Protocol) Integration

The platform also exposes an MCP server:

```
mcp__omniframe list_tools    # List all 18 actions with schemas
mcp__omniframe call_tool <name> <args_json>  # Call any action
```

See `agent/schemas/tools.json` for the full schema registry.

## Package Installation

```powershell
# From repo root; native is optional
python -m pip install -e .
python -m pip install -e ".[native]"

# Verify
omniframe doctor --json

# List tools
omniframe tools --list
```

## Streaming and copy-safe delivery

Use the normal PNG path when checkpoints, resume, or visual inspection of every
frame is required. For a single code or cartoon clip, opt into direct raw RGBA
streaming:

```powershell
omniframe project render project.json --out out/stream-cache `
  --stream-to-ffmpeg out/clip.mp4 --cartoon-backend auto
```

Streaming rejects `--resume` by design. The optional native accelerator is
reported by `doctor` as `native_accelerator`; `auto` falls back to Python when
native code is unavailable or a scene uses unsupported primitives. Compatible
video segments are selected for FFmpeg `-c copy` during concat/audio mux, while
incompatible streams are re-encoded with a structured reason in logs.

## Version

0.1.0 — Alpha release