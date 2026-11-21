# Phase 3 — Bridge Interoperability — Gate Report

Date: 2026-11-21
Workspace: `.worktrees/omniframe-platform-hardening` (branch `omniframe-platform-hardening`, all uncommitted)
Plan: `docs/superpowers/plans/2026-11-21-omniframe-phase3-bridges.md`

## Outcome: GATE PASS

All four tasks (host-independent bridge fixtures, loss report, verification levels, CapCut fixtures + runbook) implemented, independently verified PASS, and the Phase-3 acceptance gate checklist satisfied. Nothing committed (no user authorization). HEAD remains `6749271`.

---

## Task completion summary

| # | Task | Files | Verdict |
|---|------|-------|---------|
| 1 | Host-independent bridge fixtures | `tests/fixtures/bridges/`, `tests/test_bridges_fixtures.py` | PASS |
| 2 | Translation/inspection loss report | `bridges/loss.py` (new), `bridges/base.py` (additive `loss` key), `tests/test_bridges_loss.py` | PASS |
| 3 | Verification levels bound to fixtures | `tests/test_bridges_verification.py`, `pyproject.toml` (`bridge_host` marker) | PASS |
| 4 | CapCut version fixtures + Adobe/Resolve runbook | `docs/runbooks/bridge-acceptance.md`, `tests/fixtures/bridges/capcut-13.0.0/`, `tests/test_bridges_capcut_fixture.py` | PASS |

Each task had a scoped worker plus an independent verifier; all reviews issued `VERDICT: PASS` with file:line evidence. Verifier task IDs: Task1 `bg_606654cc`, Task2 `bg_f6bfbdd0`, Task3 `bg_4ba3bdb0`, Task4 `bg_3c5094cc`.

SDD ledger (worker + verifier reports per task): `.superpowers/sdd/2026-11-21-omniframe-phase3-bridges/`.

---

## Acceptance gate checklist (run from worktree root)

### `python -m compileall -q src`
Exit 0 — clean compile of the whole tree including new `bridges/loss.py` and all fixture modules.

### `python -m pytest -q` (full suite)
**All collected tests pass (exit 0)** — verified across **three consecutive full-suite runs** (plus isolated manager runs), because a Phase-2 threading race surfaced under full-suite timing and was fixed first (see below). No failures; the only `s` is the expected `bridge_host` skip.

### `python -m ruff check src tests`
**Net-zero phase-introduced lint confirmed.**
- Throwaway ruff 0.17.6 used (ruff not on persistent PATH — pre-existing env limitation, same as Phases 0–2).
- Full current: **98 errors** — identical to the pristine-HEAD baseline of 98. Net-zero delta across three phase boundaries.
- All new Phase-3 modules/tests lint-clean ("All checks passed"): `bridges/loss.py`, `base.py` additions, all four new bridge test modules, `manager.py`, `test_jobs_manager.py`.
- CI gate (98 pre-existing errors) remains red until pre-existing debt is cleared; phase-introduced count is zero. Re-recorded as known debt.

### `python -c "from omniframe.bridges import list_bridges; print('BRIDGES', [b['id'] for b in list_bridges()])"`
`BRIDGES ['after_effects', 'capcut', 'davinci_resolve', 'krita', 'premiere_pro']` — all 5 bridges answer honestly.

---

## Blocking issue found and fixed: Phase-2 JobManager thread race

Full-suite timing surfaced a **real defect** plus two timing-fragile test assertions in Phase 2 Task 2 code (`src/omniframe/jobs/manager.py`, `tests/test_jobs_manager.py`). These had passed Phase 2's own gate because Phase 2's full run happened not to trip the race; Phase 3's gate did.

1. **Real bug — shutdown cancel ordering.** `shutdown()` cancels all cancel-flags, then sweeps `running`→`canceled` jobs, then joins workers. A worker that returns between the flag-set and the sweep could read `refreshed["status"] == "running"` (sweep not yet committed) and overwrite with `done`, leaving the job `done` instead of `canceled`. **Fix:** in `_execute`, check `flag.cancelled` directly (in-memory, set before join) *before* the store snapshot, so a canceled job is deterministically left `canceled`. Applied at `manager.py` `_execute`.
2. **Timing-fragile assertions.** `test_submit_runs_to_done_and_persists_result` and `test_retry_increments_attempts_and_reruns` asserted transient `queued`/`running` statuses read immediately after `submit`/`retry`. With fast in-memory workers the job can legally already be `done` (or `failed`) at that read. **Fix:** assert only stable facts (attempts bump; terminal outcome via `_wait_status`) and wait for terminal state deterministically.

**Verified stable:** manager suite 10/10 and the full suite pass on multiple consecutive runs (3+), where they previously flaked intermittently.

---

## Additional gate guarantees

- **No `shell=True` anywhere in the new/changed bridge or job code** — confirmed by grep in every task and re-verified by all four verifiers (and the Phase-2 fix).
- **Every bridge answers `detect().installed is False` honestly on this machine** — recorded in `docs/runbooks/bridge-acceptance.md` via a live `omniframe doctor --json` status; all five hosts are `available: false` here. No host test is claimed executed.
- **No fixture claims `render_tested`/`production_candidate`** — `tests/test_bridges_verification.py` enforces the hard honesty boundary (`BRIDGE_LEVELS` restricted to `generated`/`structurally_checked`); only `structurally_checked` is claimed anywhere.
- **`docs/runbooks/bridge-acceptance.md` exists** and makes launching the host a separate human/operator step, with per-capability pass/fail attribution, version recording and verification-level attainment for each of the 5 bridges, plus an operator log template.
- **`bridge_host` marker registered** in `pyproject.toml`; host-marked tests are **skipped** (not failed) with reason "host not installed".
- **CapCut format pinned honestly at v13.0.0** — the version literal is genuinely hard-coded in `translate.py` (`CapCutDraftTranslator`), the golden fixture is a true deep-equality match to `generate_script` output, and a future format drift fails loudly rather than being silently overwritten.

---

## How to reproduce

```powershell
cd .worktrees/omniframe-platform-hardening
$env:PYTHONPATH='src'
python -m compileall -q src
python -m pytest -q
python -m ruff check src tests
python -c "from omniframe.bridges import list_bridges; print('BRIDGES', [b['id'] for b in list_bridges()])"
```

---

## Next

Phase 3 gate PASS → proceed to **Phase 4 (UI and agent experience)**.