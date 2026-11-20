# OmniFrame Studio

OmniFrame Studio is an open-source, agent-first video and animation control platform. It combines deterministic HTML/CSS/JS frame rendering, a Pillow-based 2D cartoon pipeline, FFmpeg composition, timeline translation, visual inspection, checkpoints, and bridges for Premiere Pro, After Effects, DaVinci Resolve, CapCut, and Krita.

## Quickstart for AI Agents

Requirements: Python 3.10+ on Windows 10/11 or another supported platform. FFmpeg is required for video composition. Chromium and Playwright are required for browser-backed code-video rendering; install them with the optional render extra.

```powershell
# Clone and install
python -m pip install -e .
python -m pip install -e ".[render]"
python -m playwright install chromium
# Optional native C++17/pybind11 accelerator; Python fallback remains automatic
python -m pip install -e ".[native]"

# Inspect the environment and action contracts
omniframe doctor
omniframe tools --list

# Validate, render, compose, and inspect an example
omniframe project validate examples/code-explainer/project.json
omniframe project render examples/code-explainer/project.json --out out/code-explainer
omniframe project compose examples/code-explainer/project.json --frames out/code-explainer/intro --out out/code-explainer.mp4
omniframe inspect media --video out/code-explainer.mp4 --output-dir out/inspect --count 8 --contact-sheet out/inspect/contact-sheet.png

# Opt-in direct raw RGBA streaming for a project containing one renderable clip.
# Streaming does not create resumable PNG checkpoints.
omniframe project render examples/code-explainer/project.json --out out/stream-cache \
  --backend playwright --stream-to-ffmpeg out/code-explainer-stream.mp4
```

### Optional acceleration and compatibility

The default renderer remains PNG-first and supports resume/checkpoint workflows. The
`--stream-to-ffmpeg` flag is opt-in, streams raw RGBA frames through FFmpeg stdin,
and rejects `--resume` because no PNG checkpoint files are produced. Compatible
H.264/HEVC/ProRes/VP9 segments are automatically concatenated or audio-muxed with
`-c copy`; incompatible metadata falls back to the selected encoder with a logged
reason. `omniframe doctor --json` reports `native_accelerator` as either `native` or
`python-fallback`. Native failures never prevent installation or normal PNG rendering.

Every capability is available as a typed action with JSON Schema validation:

```powershell
omniframe run-tool environment.detect --params '{"include_hosts":true}'
```

## MCP server

The native stdio MCP server exposes the built-in action registry to MCP-compatible clients:

```powershell
omniframe mcp
```

Claude Code configuration:

```json
{
  "mcpServers": {
    "omniframe": {
      "command": "omniframe",
      "args": ["mcp"]
    }
  }
}
```

Cursor or generic MCP clients can use the same command. If the package is not on `PATH`, use the interpreter explicitly:

```json
{
  "mcpServers": {
    "omniframe": {
      "command": "python",
      "args": ["-m", "omniframe.mcp_server"]
    }
  }
}
```

The protocol supports standard `initialize`, `tools/list`, and `tools/call` requests. Legacy `list_tools` and `call_tool` aliases are retained for compatibility. The action schemas are also available in `src/omniframe/agent/schemas/tools.json`.

## Local Web UI

Start the FastAPI control surface with:

```powershell
omniframe ui --host 127.0.0.1 --port 8765
```

Then open <http://127.0.0.1:8765/ui>. The UI provides agent activity streaming, timeline inspection, frame/contact-sheet preview, code-video controls, bridge status, and checkpoint management.

## Examples

- `examples/code-explainer/` — deterministic HTML/CSS/JS kinetic title.
- `examples/cartoon-bounce/` — squash-and-stretch 2D animation.
- `examples/full-studio-demo/` — combined code-video, cartoon, and audio timeline.

## Development

```powershell
python -m pip install -e ".[dev,render]"
python -m playwright install chromium
python -m pytest -q
python -m pytest -q -m "not render"
python -m pytest -q -m render
```

The project uses only the documented dependencies in `pyproject.toml`, avoids `shell=True`, and does not bypass DRM or patch proprietary binaries. DCC bridges degrade gracefully when the host application is not installed.

## Architecture

- `src/omniframe/core/timeline_schema/` — Pydantic timeline models, semantic validation, JSON Schema, and translators.
- `src/omniframe/core/agent_runtime/` — action registry, routing, checkpoints, and visual inspection.
- `src/omniframe/engines/` — code-video, cartoon-2D, and FFmpeg compositor engines.
- `src/omniframe/bridges/` — documented API and read-only RAE bridge adapters.
- `src/omniframe/backend/` — FastAPI API, WebSocket activity stream, MCP HTTP adapter, and UI serving.
- `src/omniframe/agent/` — agent manifest, schemas, skill, and programming guide.

## License

MIT. See [LICENSE](LICENSE).
