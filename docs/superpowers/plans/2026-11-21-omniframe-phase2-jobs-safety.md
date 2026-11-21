# OmniFrame Phase 2 — Durable Local Jobs and Safety

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give OmniFrame a durable, resumable local job lifecycle with explicit safety boundaries. Today render/compress/translate are run as blocking in-process calls (see `src/omniframe/engines/*`, `src/omniframe/compositor/compositor.py`); there is **no** job queue, SQLite persistence, or workspace containment yet. This phase adds the smallest durable-job surface plus path/process/browser safety, without inventing features that do not exist.

**Architecture:** A SQLite-backed job store records each job's status (`queued|running|paused|done|failed|canceled`), owner, workspace, inputs, `CancelFlag` reference, logs and result pointer. A `JobManager` runs jobs by shelling out (argument-list only) or calling registered callables, with restart/retry/cancel semantics. Workspace policy forbids escaping a configured root; browser and subprocesses get bounded resources.

**Tech Stack:** Python 3.10+ stdlib `sqlite3`, `threading`, `subprocess` (no shell=True), JSON, existing `omniframe.core.config`, Phase 1 `CancelFlag`/`RenderResult`.

## Global Constraints

- Preserve Python `>=3.10` and `src/` layout.
- No `shell=True`; exec only argument-list subprocesses.
- Do not commit unless the user authorizes commits.
- Never claim tested behavior that was not executed (verification levels).
- Package the DB and job code under `src/omniframe/jobs/`; keep it optional toward the CLI (typer command surface only where it stays consistent).

## Pre-inspection note

`grep` shows **no** existing `job_queue`, `Job` model, SQLite usage, or workspace-lock code in `src/omniframe`. This phase therefore creates a new `src/omniframe/jobs/` package rather than modifying a non-existent one. Phase 4 (UI) and Phase 2 must agree on the job API: a JSON-returning `JobManager` suitable for the FastAPI server (`src/omniframe/backend/server.py`, optional `ui` extra).

---

### Task 1: Job store (SQLite)

**Files:**
- Create: `src/omniframe/jobs/store.py`
- Create: `src/omniframe/jobs/__init__.py`
- Test: create `tests/test_jobs_store.py`

**Interfaces:**
- Consumes: `sqlite3`, a configurable DB path (default `<workspace>/.omniframe/jobs.db`).
- Produces: `JobStore` with `create_job`, `get_job`, `update_job`, `list_jobs(status=None)`, `delete_job`.

Schema (TEXT/id + JSON columns, single table `jobs`):
```sql
CREATE TABLE IF NOT EXISTS jobs (
  id TEXT PRIMARY KEY,
  kind TEXT NOT NULL,
  status TEXT NOT NULL,
  workspace TEXT NOT NULL,
  owner TEXT,
  payload_json TEXT NOT NULL,
  result_json TEXT,
  error TEXT,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  attempts INTEGER NOT NULL DEFAULT 0
);
```

- [ ] **Step 1** — Implement `store.py` with context-managed connections (`with sqlite3.connect(...) as conn:`), `row_factory=sqlite3.Row`, and JSON (de)serialisation for payload/result. `create_job` returns the `job_id`; `update_job` bumps `updated_at` and merges fields.
- [ ] **Step 2** — Export `JobManager`, `CancelFlag` (re-export from Phase 1) and `JobStore` from `__init__.py`.
- [ ] **Step 3** — `tests/test_jobs_store.py`: create/read/update/list/delete, status filter, invalid `kind`→`ValidationError`. Run focused → pass; run `tests/test_artifact.py` to confirm no import cycle.

---

### Task 2: JobManager lifecycle

**Files:**
- Create: `src/omniframe/jobs/manager.py`
- Test: create `tests/test_jobs_manager.py`

**Interfaces:**
- Consumes: `JobStore`, a registry of `kind → callable` (the worker folds; e.g. `"render"` → `render_code_scene`).
- Produces: `JobManager.submit(kind, payload, owner=None) -> job_id`; `status(job_id)`; `cancel(job_id)`; `retry(job_id)`; `shutdown()`.

Semantics:
- `submit` persists a `queued` job and returns `job_id` immediately; a worker thread claims and runs it, updating status `running`, then `done` (with `result_json`) or `failed` (with `error`).
- `cancel` sets the `CancelFlag` (from Phase 1) and marks `canceled`; the running worker checks the flag at cooperative points (per-frame, per-ffmpeg-wait via Phase 1 hooks) and stops.
- `retry` only from `failed|canceled`; increments `attempts`, resets status to `queued`.
- `shutdown` cancels all running and waits for workers (bounded join).

- [ ] **Step 1** — Implement `JobManager` with a `threading.Thread` worker pool (max concurrent jobs bounded, configurable, default 2). Register the stock `kind`s: `render`, `compose`, `translate`, `validate`. For a missing kind raise `ValidationError` listing registered kinds.
- [ ] **Step 2** — `tests/test_jobs_manager.py`: submit→done, retry increments attempts, cancel a sleeping job → canceled, unknown kind → `ValidationError`, `shutdown` is idempotent. Use small in-thread callables (not real ffmpeg) so the test is deterministic and fast.

---

### Task 3: Workspace and path policy

**Files:**
- Create: `src/omniframe/jobs/safety.py`
- Test: create `tests/test_jobs_safety.py`

**Interfaces:**
- Produces: `ensure_within(workspace, candidate) -> Path` and `resolve_workspace(root)`.

- [ ] **Step 1** — `resolve_workspace(root)` creates `root/.omniframe` and returns its absolute path; refuse an empty/root/bare path (raise `ValidationError`).
- [ ] **Step 2** — `ensure_within(workspace, candidate)` resolves both and raises `PathSecurityError` (new, subclass `OmniFrameError`) when `candidate` screams outside the workspace (path traversal, absolute shortcuts, drive change).
- [ ] **Step 3** — Tests: nested path ok; `..` escape rejected; a second-drive path rejected; missing workspace auto-created.

---

### Task 4: Process, browser and resource bounds

**Files:**
- Modify: `src/omniframe/jobs/safety.py` (add process/kill helpers) and `src/omniframe/engines/compositor/ffmpeg.py` (honor a cancel flag while running, from Phase 1)
- Test: create `tests/test_jobs_resources.py`

**Interfaces:**
- Produces: `launch_guarded(argv, *, cwd, cancel, timeout)` running `subprocess.Popen` (list args, no shell) with optional `timeout` and cancel-kill; and `browser_sandbox_args()` returning Chromium args restricting disk/IO.

- [ ] **Step 1** — `launch_guarded`: use `subprocess.Popen(argv, cwd=cwd, stdout=PIPE, stderr=PIPE)`, poll `cancel.cancelled` in a loop; on timeout or cancel `proc.kill()` and collect tail of stderr into a `RenderError`/new `JobError`.
- [ ] **Step 2** — `browser_sandbox_args()` returns `["--disable-dev-shm-usage", "--disable-background-networking", "--no-first-run"]` and merge into the existing `PlaywrightBackend.browser_args` only when a `sandbox=True` flag is passed; default behavior unchanged.
- [ ] **Step 3** — Tests: `launch_guarded` runs a trivial `[python, -c, ...]` and returns rc=0; a pre-cancelled flag kills early; timeout kills and raises; `browser_sandbox_args` contains the sandbox strings and does not mutate the phase-1 defaults before the flag.

---

## Acceptance gate (Phase 2)

Run and record:

```powershell
python -m compileall -q src
python -m pytest -q
python -m ruff check src tests
python -c "from omniframe.jobs import JobManager, JobStore, CancelFlag; print('JOBS_OK')"
```

Gate passes only if:
- full pytest zero failures (all new `tests/test_jobs_*.py` included);
- job lifecycle, workspace containment and cancel/timeout tests pass;
- no `shell=True` anywhere in `src/omniframe/jobs/`;
- optional UI/server imports still hold (server `import` only, no runtime host test claimed);
- lint shows no phase-introduced errors;
- `docs/phase-reports/phase2-jobs-safety.md` written.

When the gate passes, continue to Phase 3 (bridge interoperability).