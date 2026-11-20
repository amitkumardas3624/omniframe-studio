# OmniFrame Studio Agent Skill

OmniFrame Studio exposes deterministic video and animation workflows through a Python API, the `omniframe` CLI, and a stdio MCP server.

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
