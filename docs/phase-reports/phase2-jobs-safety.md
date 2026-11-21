# Phase 2 — Durable Local Jobs and Safety — Gate Report

Date: 2026-11-21
Workspace: `.worktrees/omniframe-platform-hardening` (branch `omniframe-platform-hardening`, all uncommitted)
Plan: `docs/superpowers/plans/2026-11-21-omniframe-phase2-jobs-safety.md`

## Outcome: GATE PASS

All four tasks (SQLite job store, JobManager lifecycle, workspace/path policy, process/browser/resource bounds) implemented, independently verified PASS, and the Phase-2 acceptance gate checklist satisfied. Nothing committed (no user authorization). HEAD remains `6749271`.

---

## Task completion summary

| # | Task | Files | Verdict |
|---|------|-------|---------|
| 1 | Job store (SQLite) | `jobs/store.py`, `jobs/__init__.py`, `tests/test_jobs_store.py` | PASS |
| 2 | JobManager lifecycle | `jobs/manager.py`, `jobs/__init__.py`, `tests/test_jobs_manager.py` | PASS |
| 3 | Workspace and path policy | `jobs/safety.py`, `core/errors.py` (+`PathSecurityError`), `tests/test_jobs_safety.py` | PASS |
| 4 | Process/browser/resource bounds | `jobs/safety.py` (+`launch_guarded`/`browser_sandbox_args`), `code_video/backends.py` (+`sandbox`), `tests/test_jobs_resources.py` | PASS |

Each task had a scoped worker plus an independent verifier; all reviews issued `VERDICT: PASS` with file:line evidence. Verifier task IDs: Task1 `bg_0ad3c2fb`, Task2 `bg_2910f608`, Task3 `bg_a6ee070f`, Task4 `bg_792d828a`.

SDD ledger (worker + verifier reports per task): `.superpowers/sdd/2026-11-21-omniframe-phase2-jobs-safety/`.

---

## Acceptance gate checklist (run from worktree root)

### `python -m compileall -q src`
Exit 0 — clean compile of the whole tree, including the new `omniframe.jobs` package.

### `python -m pytest -q` (full suite)
**All collected tests pass (exit 0).** Full dot run completed 100% with no `F`/`E`/`s`; per-suite confirmation: resources(8) + safety(9) + artifact(8) + manager(10) + store(10) for the new Phase-2 tests, plus all pre-existing suites.

### `python -m ruff check src tests`
**Net-zero phase-introduced lint confirmed.**
- Throwaway ruff 0.17.6 used (ruff not on persistent PATH — pre-existing env limitation, same as Phases 0/1).
- Full current: **98 errors** — identical to the documented pristine-HEAD baseline of 98 (Phase-1 gate measured the same). Net-zero delta vs two phase boundaries.
- **Five genuine Phase-2-introduced errors were found and fixed:**
  - `jobs/manager.py:20` F401 `time` unused import — removed.
  - `jobs/manager.py:22` UP035 import `Callable` from `collections.abc` — moved (with `Any` split).
  - `jobs/safety.py:21` UP035 import `Sequence` from `collections.abc` — moved.
  - `tests/test_jobs_manager.py:8` I001 unsorted import block — isort-sorted via ruff `--fix`.
  - `tests/test_jobs_manager.py:10` F401 `threading` unused import — removed.
- After fixes, `ruff check` on all new Phase-2 modules/tests → "All checks passed" (exit 0); full tree back to 98 = baseline.
- CI gate (98 pre-existing errors) remains red until pre-existing debt is cleared; phase-introduced count is zero. Re-recorded as known debt.

### `python -c "from omniframe.jobs import JobManager, JobStore, CancelFlag; print('JOBS_OK')"`
`JOBS_OK` — the full job public surface imports cleanly from the package root.

---

## Additional gate guarantees

- **No `shell=True` anywhere in `src/omniframe/jobs/`** — confirmed by grep in every task and re-verified by all four verifiers. `launch_guarded` uses `subprocess.Popen(argv list)`; FFmpeg stays argument-list based.
- **Durable job lifecycle** — SQLite-backed `JobStore` (per-op context-managed connections, `row_factory=Row`, JSON payload/result) plus `JobManager` (bounded daemon-thread pool, default 2 concurrency, cooperative `CancelFlag` cancellation, `retry` from `failed|canceled`, idempotent `shutdown`). Unknown kind raises `ValidationError` listing registered kinds.
- **Workspace containment** — `resolve_workspace` materialises `<root>/.omniframe`; `ensure_within` rejects path traversal, absolute shortcuts resolving outside, and Windows drive changes via `PathSecurityError`.
- **Process/browser bounds** — `launch_guarded` polls `cancel.cancelled` and kills on cancel/timeout with captured stderr tail; `browser_sandbox_args` returns the 3 Chromium sandbox flags; `PlaywrightBackend` merges them only under `sandbox=True` into a fresh copy (default list never mutated).
- Public API surface agreed with Phase 4 (UI/server): the JSON-compatible `JobManager`/`JobStore` are importable from `omniframe.jobs` and suitable for the FastAPI server. Server `import` only — no runtime host test claimed.
- Optional Chromium/stub fallbacks preserved and truthfully labeled.

---

## Path-deviation adjudication (Task 4)

The plan/brief named `src/omniframe/engines/compositor/backends.py` for the `PlaywrightBackend` `sandbox` flag, but that file does not exist. `PlaywrightBackend` lives in `src/omniframe/engines/code_video/backends.py` (unique grep match). The worker implemented the `sandbox` flag in the correct real module and created no phantom `compositor/backends.py`. The independent verifier adjudicated this as **acceptable faithful realization of the task intent**, not a scope deviation. (Non-blocking: recommend correcting the plan path for traceability.)

---

## Known remaining unknowns / limitations

1. **Full `pytest -q`** produced no console summary line in some runs (stream quirk); counts confirmed via progress dots (no `F`/`E`/`s`) + per-suite runs in reports.
2. **ruff not on persistent PATH** — lint verified with the throwaway ruff 0.17.6 venv. Persistent env limitation, not a repo defect.
3. **`update_job` cannot clear a column via `None`** (None values are skipped) — benign design note; Phase-2 semantics only ever *set* non-None terminal status/result/error, so it does not block the lifecycle.
4. **Cancel/timeout kill in `launch_guarded` raises base `OmniFrameError`** (no dedicated `JobError`; `errors.py` additions limited to Task-3 `PathSecurityError`). Error carries `.details` (`argv`, `stderr` tail, `returncode`). Documented fallback.
5. **Playwright real sandbox launch** not exercised (flag wiring unit-tested; browser host optional absent). Honest scoped limitation.
6. **`submit` after `shutdown()`** persists a `queued` job but no worker runs it (out of Task-2 scope).
7. **CI not run on a real runner** — static/local verification only (established in Phase 0).
8. **Repository identity mismatch** still open (`docs/repository-identity.md`) — release-blocking only, deferred to Phase 5.

---

## How to reproduce

```powershell
cd .worktrees/omniframe-platform-hardening
$env:PYTHONPATH='src'
python -m compileall -q src
python -m pytest -q
python -m ruff check src tests
python -c "from omniframe.jobs import JobManager, JobStore, CancelFlag; print('JOBS_OK')"
```

---

## Next

Phase 2 gate PASS → proceed to **Phase 3 (bridge interoperability)**.