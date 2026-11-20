# OmniFrame Studio Agent Skill

OmniFrame Studio exposes deterministic video and animation workflows through a Python API, the `omniframe` CLI, and a stdio MCP server.

## One-Line Install

Fresh GitHub installs (the installers check Python, pip/uv, FFmpeg, Playwright/Chromium, and finish with `doctor`):

```bash
curl -fsSL https://raw.githubusercontent.com/gbd718106-cmyk/omniframe-studio/master/install.sh | bash
```

```powershell
iwr https://raw.githubusercontent.com/gbd718106-cmyk/omniframe-studio/master/install.ps1 -UseBasicParsing | iex
```

For local development from a checkout:

```powershell
python -m pip install -e ".[ui,render,dev]"
python -m playwright install chromium
python -m omniframe.cli doctor --json
```

The installers warn with repair commands when FFmpeg or Chromium is absent; those optional checks do not silently pass. Override the Git source for a fork or ref with `OMNIFRAME_REPO_URL`.

## Local Web UI

Start the local control surface with:

```powershell
omniframe ui --host 127.0.0.1 --port 8765
```

Inspect it at <http://127.0.0.1:8765/ui>; the health endpoint is <http://127.0.0.1:8765/health>.

## Updates

Use explicit update commands:

```powershell
omniframe update check
omniframe update check --json
omniframe update apply
omniframe self-update
```

The Web UI uses `GET /api/v1/system/update-status`, streams `POST /api/v1/system/update` logs, and exposes `POST /api/v1/system/restart` instructions. CLI JSON responses and MCP initialize/tool responses include `update_available` and `update_info` when a newer version is known from the local cache. GitHub outages are non-fatal and fall back to cached/offline status.

Configure `OMNIFRAME_REPO_SLUG`, `OMNIFRAME_UPDATE_URL`, `OMNIFRAME_UPDATE_CACHE`, `OMNIFRAME_UPDATE_TTL_SECONDS`, or `OMNIFRAME_UPGRADE_COMMAND` when using a fork, mirror, custom cache, or controlled upgrade command.

## Core agent workflow

1. Run `omniframe doctor` to detect Python, FFmpeg, Chromium, and optional DCC hosts.
2. Run `omniframe tools --list` to discover typed actions.
3. Validate a project before rendering: `omniframe project validate <project.json>`.
4. Save a checkpoint before destructive edits.
5. Render, compose, and inspect contact sheets.
6. Branch on stable `OmniFrameError.code` values such as `E_RENDER`, `E_SCHEMA`, `E_VALIDATION`, and `E_BRIDGE_UNAVAILABLE`.

## MCP

Run `omniframe mcp` as a stdio MCP server. Action contracts are in `src/omniframe/agent/schemas/tools.json`; the detailed programming guide is in `src/omniframe/agent/AGENT_GUIDE.md`.

## Determinism

Rendering uses seeded frame-level PRNG, frozen CSS animations, exact frame numbering, and optional `__OMNIFRAME_READY__` synchronization.

## Safety

Use documented host scripting APIs where available and read-only inspection for reverse-engineered formats. Do not use `shell=True`, expose secrets, bypass DRM, or patch proprietary binaries.
