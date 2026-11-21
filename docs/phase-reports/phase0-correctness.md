# Phase 0 — Correctness Baseline: Phase Report

Date: 2026-11-21 (implementation worktree branch `omniframe-platform-hardening`, uncommitted).
Baseline commit: `6749271`. All verification ran in the isolated worktree at
`C:\Users\AK ANIK\Desktop\RAE\.worktrees\omniframe-platform-hardening`.

## Conclusion

**Pass (correctness scope), with two recorded, explicitly deferred items:**

1. The CI lint gate is red against **pre-existing** ruff debt (98 violations, net-zero delta from this phase). Lint remediation is out of the Phase 0 correctness scope and deferred to a later phase.
2. Repository identity is unresolved (three distinct URLs) and was intentionally **not** silently rewritten.

Phase 0 introduced **no new** lint errors and **no correctness regression**; the full suite passes with zero failures.

## Verification commands and exit codes

Run from the worktree root.

| Command | Exit | Result |
| --- | --- | --- |
| `python -m compileall -q src` | 0 | Compiled |
| `python -m pytest -q` (with `PYTHONPATH` cleared) | 0 | **185 tests collected, 0 failures** |
| `python -m ruff check src tests` (ruff 0.17.6) | 1 | 98 errors, **all pre-existing at HEAD** (baseline HEAD=98; phase fixes I001 in new test → net-zero) |
| `python -m omniframe.cli doctor --json` | 0 | Core ready; optional hosts separated |
| `python -c "…ensure_builtin_actions()…"` | 0 | `ACTION_COUNT 19` |
| `python -m omniframe.cli tools --list` | 0 | 19 names |

## Acceptance criteria

Per the plan (`Task 6, Step 2`):

- **Package collection has no `ModuleNotFoundError`** — PASS (compileall + full pytest collection with `PYTHONPATH` cleared).
- **Full pytest has zero failures** — PASS (`185 tests collected`, exit 0).
- **Promo audio test sees 30 s; handwashing tests see 10 s** — PASS (promo frame count 30 s, handwashing frame count 10 s, 48 kHz stereo).
- **Manifest and guides agree with 19 runtime actions** — PASS (`tools.json` regenerated from runtime; `16 test assertions` in `test_tool_manifest_consistency.py` pass).
- **Compile and lint checks pass** — PARTIAL. Compile: PASS. Lint: `ruff check` returns exit 1 with 98 **pre-existing** violations; the one **phase-introduced** I001 (blank line in `tests/test_tool_manifest_consistency.py`) was fixed, yielding a **net-zero** delta against pristine HEAD. Per the plan's `Task 4, Step 4` instruction ("record … and fix only errors introduced or exposed by this phase"), the 98 pre-existing violations are recorded as deferred debt, not a phase regression. Breakdown: F401×28, I001×15, UP045×13, UP035×12, UP031×10, UP037×6, UP006×4, F822×2, F841×2, B905×2, B027×1, UP034×1, B904×1, B007×1, E703×1.
- **Doctor output recorded with unavailable optional hosts separated from core readiness** — PASS (below).
- **Repository identity mismatch documented, not silently rewritten** — PASS (`docs/repository-identity.md`).

## Doctor capabilities (recorded)

- **Available / core:** python 3.12.10, node v24.14.0, ffmpeg 8.1.1, ffprobe 8.1.1, chromium 151.0.7922.34 (playwright).
- **Unavailable (optional):** `native_accelerator` (native extension not installed), `premiere_pro`, `after_effects`, `davinci_resolve`, `capcut`, `krita` (executables not located).
- `doctor.ready = true` with the optional-host matrix clearly separated.

## Changed / created files (Phase 0, worktree, uncommitted)

- `pyproject.toml` — added `pythonpath = ["src"]` under `[tool.pytest.ini_options]`.
- `.github/workflows/ci.yml` — new CI (push `[main, master]`, `pull_request`, `workflow_dispatch`; matrix 3.10/3.11/3.12; install `.[dev]`; compileall; pytest; `ruff check src tests`).
- `src/omniframe/agent/schemas/tools.json` — regenerated from runtime (19 actions, `schema_version:1.0`, `kind:omniframe_tool_manifest`).
- `AGENT_GUIDE.md`, `src/omniframe/agent/AGENT_GUIDE.md`, `src/omniframe/agent/SKILL.md`, `src/omniframe/agent/README.md`, `src/omniframe/backend/server.py` — stale 18-action / count / `project.render` / `project.compose` / cartoon-seed claims corrected.
- `tests/test_tool_manifest_consistency.py` — new regression suite (manifest equality, stable names, docs guards).
- `tests/test_omniframe_promo_audio.py`, `tests/test_handwashing_render.py` — import isolation (`importlib.util`) replacing `sys.path` mutation.
- `docs/repository-identity.md` — identity mismatch record (Task 5).
- `.superpowers/sdd/2026-11-21-omniframe-phase0-correctness/` — SDD ledger (briefs, reports, review diffs).
- `docs/phase-reports/phase0-correctness.md` — this report.

Untouched (per constraint): `examples/handwashing-2d/`, `tests/test_handwashing_project.py`, audit/spec/plan docs and other user-created untracked files.

## Known limitations / deferred

- **Lint gate is red in CI** against the recorded 98 pre-existing ruff violations. CI will not go green until lint remediation lands. This is deferred and out of Phase 0 scope.
- **Repository identity unresolved** — see `docs/repository-identity.md`. One canonical URL must be selected and propagated to remote, installers and `pyproject.toml` before any release. Also note `pyproject.toml` `Documentation` points to `tree/main` while the default branch is `master`.
  - *Resolved 2026-11-22:* the user named `https://github.com/amitkumardas3624/omniframe-studio` canonical (cause: a GitHub username change) and it was propagated to the remote, both installers, README/`SKILL.md`, `pyproject.toml` `[project.urls]`, the updater slug and the server fallback link; `Documentation` now points at `tree/master`. A drift guard was added to `tests/test_installers.py`. The line above records the state **as it stood at the Phase-0 gate**.
- **CI workflow has never executed on a real GitHub runner**; locally verified only (except the ruff command was executed locally in a throwaway venv).
- **Optional DCC hosts** (Premiere, AE, Resolve, CapCut, Krita) not installed on this machine; their bridges are not end-to-end tested here (verification level: `generated`/`structurally_checked`/`import_tested`).
- Scope-defensive decision: ruff 0.17.6 auto-includes current upstream rules; a different ruff version (CI pins `ruff>=0.4`) may report a slightly different count, but the phase-introduced net-zero conclusion is version-independent (only the I001 in the new test file was phase-introduced and it is fixed).
- No commit was created (no user authorization).

## Phase 0 is complete for the correctness scope.

Per the roadmap, later phases (rendering/compositor hardening, durable jobs and safety, bridge interoperability, UI/agent experience, packaging/release hardening) are to be planned next against the post-Phase-0 code.