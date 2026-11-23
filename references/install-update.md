# Install, update, UI and MCP

Read this only when the task is about installing, updating, running the UI, or connecting MCP.

## Install

Linux/macOS:

```bash
curl -fsSL https://raw.githubusercontent.com/amitkumardas3624/omniframe-studio/master/install.sh | bash
```

Windows PowerShell:

```powershell
iwr https://raw.githubusercontent.com/amitkumardas3624/omniframe-studio/master/install.ps1 -UseBasicParsing | iex
```

The installers check Python, pip/uv, FFmpeg and Playwright/Chromium, then run `doctor`. Missing optional tools are reported with repair commands, never silently skipped. Use `OMNIFRAME_REPO_URL` to install a fork or a different Git ref.

Local development from a checkout:

```powershell
python -m pip install -e ".[ui,render,dev]"
python -m playwright install chromium
python -m omniframe.cli doctor --json
```

Optional native accelerator: `python -m pip install -e ".[native]"`. If it is absent, the Python fallback is used automatically.

## Update

```powershell
omniframe update check
omniframe update check --json
omniframe update apply
omniframe self-update
```

- CLI JSON responses and MCP responses include `update_available` and `update_info` when a newer version is known from the local cache.
- GitHub outages are non-fatal; the last cache or an offline status is used.
- Web UI: `GET /api/v1/system/update-status`, `POST /api/v1/system/update` (streams logs), `POST /api/v1/system/restart`.
- Configure with `OMNIFRAME_REPO_SLUG`, `OMNIFRAME_UPDATE_URL`, `OMNIFRAME_UPDATE_CACHE`, `OMNIFRAME_UPDATE_TTL_SECONDS`, `OMNIFRAME_UPGRADE_COMMAND`.
- After a successful update, restart the process.

## Local web UI

```powershell
omniframe ui --host 127.0.0.1 --port 8765
```

UI: <http://127.0.0.1:8765/ui>. Health check: <http://127.0.0.1:8765/health>.

## MCP server

Run `omniframe mcp` (stdio). Client config:

```json
{ "mcpServers": { "omniframe": { "command": "omniframe", "args": ["mcp"] } } }
```

If `omniframe` is not on PATH: `"command": "python", "args": ["-m", "omniframe.mcp_server"]`.
Supported requests: `initialize`, `tools/list`, `tools/call` (legacy `list_tools` / `call_tool` still work).
