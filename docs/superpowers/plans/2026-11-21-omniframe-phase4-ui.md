# OmniFrame Phase 4 — UI and Agent Experience

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the optional web UI render *current* runtime data — action registry, projects/media/artifacts, job queue (Phase 2 API), timeline inspection, and bridge verification — with offline assets and basic accessibility, without claiming server-host production behavior it was not tested against.

**Architecture:** `src/omniframe/backend/server.py` (optional `ui` extra) already serves `/api/v1/...` (actions/execute, projects/validate, projects/render, bridges, bridges/detect, tools, environment, system/update-status, system/update, system/restart, mcp/call) and an HTML UI at `/ui` (current `src/omniframe/ui/index.html`, ~32 KB single-file). This phase makes the UI consume the real endpoints + the Phase 2 job API, keeps it dependency-light (vanilla JS/single HTML, no mandatory bundler), and adds offline + a11y checks.

**Tech Stack:** HTML/CSS/vanilla JS, existing FastAPI server, optional Playwright/Chromium for a11y/visual checks (skip when absent). No new mandatory frontend build step.

## Global Constraints

- The UI is optional (`ui` extra); changes must not break `import omniframe.backend.server` without FastAPI installed (guard imports).
- Do not claim production_candidate for a server/UI not loaded in a tested host browser; mark checks `render_tested` only when actually exercised.
- Preserve single-file `index.html` orientation (no mandatory build pipeline) unless the change is explicitly additive and opt-in.
- No `shell=True`; no external CDN dependency for core offline operation.
- Do not commit unless the user authorizes commits.

## Pre-inspection note

Server exposes the endpoints above; `index.html` exists but its consumers were not exhaustively re-mapped in this plan. Each task must re-read `server.py` + `index.html` before editing (no stale line numbers).

---

### Task 1: Runtime-generated action tools view

**Files:**
- Modify: `src/omniframe/ui/index.html`
- Test: `tests/test_ui_data.py` (host-independent JSON contract checks)

**Interfaces:**
- Consumes: `GET /api/v1/tools` (returns the runtime action/tool manifest).
- Produces: a UI section that lists actions with name, description and schema, and a test asserting the returned `tools` payload matches `ensure_builtin_actions().to_json_document()`.

- [ ] **Step 1** — Add a "Actions" panel that fetches `/api/v1/tools` and renders name + description (+ collapsible schema). Fall back to a friendly error box when fetch fails.
- [ ] **Step 2** — `tests/test_ui_data.py`: call `GET /api/v1/tools` against the FastAPI app (TestClient, guarded `pytest.importorskip("fastapi")`) and assert it equals the runtime manifest; ensure the test is `skip`ped when `fastapi`/`httpx` is missing.

---

### Task 2: Project / media / artifact views + job queue controls

**Files:**
- Modify: `src/omniframe/ui/index.html`
- Modify (additive): `src/omniframe/backend/server.py` — add `/api/v1/jobs/*` routes if and only if Phase 2 `JobManager` is importable (guard import; routes absent when `jobs` package missing)
- Test: `tests/test_ui_jobs.py`

**Interfaces:**
- Consumes: `POST /api/v1/projects/validate`, `POST /api/v1/projects/render`; Phase 2 job endpoints.
- Produces: UI panels for project validation/render status and a job list with submit/cancel controls; a server-side job route smoke test.

- [ ] **Step 1** — Add a "Jobs" panel reading `GET /api/v1/jobs` (Phase 2) with per-job status, and a "Cancel" button → `POST /api/v1/jobs/{id}/cancel`. Guard all job calls so a build without the `jobs` package degrades to a clear "jobs unavailable" message.
- [ ] **Step 2** — Server: add `/api/v1/jobs` list and `/api/v1/jobs/{job_id}/cancel` that instantiate the Phase 2 `JobManager` (in-memory default store) — only if importable.
- [ ] **Step 3** — `tests/test_ui_jobs.py`: with fastapi present, submit a trivial job and cancel it; assert HTTP 200 and job status transitions. Guarded to skip when deps/jobs absent.

---

### Task 3: Timeline inspection and bridge verification display

**Files:**
- Modify: `src/omniframe/ui/index.html`
- Test: `tests/test_ui_bridge_status.py`

**Interfaces:**
- Consumes: `GET /api/v1/bridges` and a timeline/document endpoint (`io.load_project` result).
- Produces: a "Bridges" panel showing each bridge's `installed`/`scripting_api`/`version` and tier; a "Timeline" panel showing tracks/clips from the loaded project JSON.

- [ ] **Step 1** — Bridges panel renders `BridgeReport` fields (installed, version, scripting_api, capabilities with tier badge). Offline-friendly.
- [ ] **Step 2** — Timeline panel: given a project file path, show sorted tracks + clips (kind, source, frames) using `omniframe.core.timeline_schema.io.load_project`.
- [ ] **Step 3** — Test asserts the bridge JSON fields are surfaced and that a sample `project.json` produced by the panel matches the load result (host-independent; no proprietary host required).

---

### Task 4: Offline assets and accessibility checks

**Files:**
- Modify: `src/omniframe/ui/index.html`
- Tooling: `tests/test_ui_a11y.py` using Playwright/Chromium when available (marked `@pytest.mark.render`; skipped otherwise)
- Docs: note in `index.html` head comment the offline policy

**Interfaces:**
- Produces: self-contained UI (no runtime dependency on external fonts/CDNs; CSP-friendly inline styles/scripts where feasible), and an a11y smoke check.

- [ ] **Step 1** — Confirm the UI has no mandatory external origin resource for core layout (search `https://` in `index.html`; if found, inline or document). Add `lang` attribute and aria-labels on interactive controls.
- [ ] **Step 2** — `tests/test_ui_a11y.py`: if Chromium/Playwright available, load `/ui` in the in-app test browser, assert the title and that key panels are reachable (basic landmark/heading presence); else `@pytest.mark.skip`. Record the execution or skip reason.
- [ ] **Step 3** — Run `python -m pytest -q tests/test_ui_a11y.py tests/test_ui_data.py tests/test_ui_jobs.py` and record result.

---

## Acceptance gate (Phase 4)

Run and record:

```powershell
python -m compileall -q src
python -m pytest -q
python -m ruff check src tests
python -c "from omniframe.backend.server import create_app; app=create_app(); print('UI_APP_OK', len(app.routes))"
```

Gate passes only if:
- full pytest zero failures (UI tests skipped gracefully without fastapi/jobs/playwright — not failed);
- `index.html` has an offline, dependency-light Actions/Jobs/Bridges/Timeline surface;
- server imports without fastapi installed (guarded) and with it installed (tested);
- no external-CDN hard dependency for core layout;
- lint adds no phase-introduced errors;
- `docs/phase-reports/phase4-ui.md` written.

When the gate passes, continue to Phase 5 (packaging and release hardening).