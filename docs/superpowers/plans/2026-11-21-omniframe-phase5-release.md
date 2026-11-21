# OmniFrame Phase 5 — Packaging and Release Hardening

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Prepare OmniFrame for a trustworthy local-first release: reproducible install/test matrix, a schema-migration story, reproducible artifacts (checksums/manifests), a release checklist, a compatibility matrix, and a production-readiness report. The repository-identity mismatch from Phase 0 remains unresolved and is a **hard release blocker** until the user picks a canonical URL.

**Architecture:** Reuse the Phase 0 CI (`compileall`+`pytest`+`ruff`), Phase 1 artifact manifests, Phase 2 job store and Phase 4 UI. Add migration and release tooling as small, testable modules.

**Tech Stack:** Python 3.10+, setuptools, pytest, ruff/mypy, optional GitHub Actions, `zipfile`/`hashlib` stdlib for reproducible archives. No new mandatory runtime deps.

## Global Constraints

- Preserve Python `>=3.10` and `src/` layout.
- No `shell=True`.
- Do not commit or publish anything unless the user authorizes it and the canonical repository identity is confirmed.
- Never claim a compatibility result for hosts not present on the test machines.
- Distinguish `generated | structurally_checked | import_tested | render_tested | production_candidate` exactly.

---

### Task 1: Cross-platform install/test matrix

**Files:**
- Modify: `.github/workflows/ci.yml` (extend, additive)
- Test: `tests/test_install_matrix.py` (host-independent packaging checks)

**Interfaces:**
- Produces: CI matrix that, beyond the existing 3.10/3.11/3.12, also runs `pip install -e .` under (a) no-extras and (b) `[dev]`, verifies the package builds a wheel/sdist and that `pm. ` `omniframe --help` exits 0.

- [ ] **Step 1** — In CI, add a job step `python -m build` (or `pip wheel . --no-deps -w dist`) and verify artifacts appear; keep existing steps.
- [ ] **Step 2** — `tests/test_install_matrix.py`: assert `pyproject.toml` requires-python `>=3.10`, package-data includes `agent/schemas/*.json` and `py.typed`, and `entry_points` declare `omniframe` and `mcp` scripts. No host invocation.
- [ ] **Step 3** — Record the exact CI config is still unreviewed by a live runner (existing limitation) and note it in the phase report.

---

### Task 2: Schema migrations

**Files:**
- Create: `src/omniframe/migrations/__init__.py`, `src/omniframe/migrations/registry.py`
- Test: create `tests/test_migrations.py`

**Interfaces:**
- Produces: `apply_migrations(db_path, *, to_version=...)` and `current_version(db_path)` for the Phase 2 job DB (schema version integer, guard table `schema_migrations`).

- [ ] **Step 1** — Implement a minimal ordered migration list `[1 -> base job schema]`; `apply_migrations` runs pep in-order inside transactions and records `(version, applied_at)` in `schema_migrations`.
- [ ] **Step 2** — `JobStore` uses `apply_migrations` on open (idempotent). 
- [ ] **Step 3** — `tests/test_migrations.py`: fresh DB → `current_version` latest; reopening idempotent; a corrupt/garbage DB raises a documented `OmniFrameError`, not a silent wipe.

---

### Task 3: Reproducible artifacts and release checklist

**Files:**
- Create: `src/omniframe/release/sign.py` and `src/omniframe/release/__init__.py`
- Create: `docs/release-checklist.md`
- Test: create `tests/test_release_artifacts.py`

**Interfaces:**
- Produces: `checksum_archive(archive_path, *, algorithm="sha256") -> dict` listing per-entry digests + an `artifacts.sha256` sidecar; and a written release checklist.

- [ ] **Step 1** — `checksum_archive` opens a zip/tar (`zipfile`/`tarfile`) and returns `{entry: hexdigest, algorithm: ..., entry_count: N, archive: ...}`; deterministic ordering (sorted entries) for reproducibility.
- [ ] **Step 2** — `docs/release-checklist.md`: pre-release (resolve repo identity, run full matrix, confirm artifacts, run `omniframe doctor`), during-release (bump version in `pyproject.toml`, tag), post-release (record compatibility matrix, verify download). Mark identity resolution as a prerequisite.
- [ ] **Step 3** — `tests/test_release_artifacts.py`: build a tiny archive, assert per-entry digests deterministic across two runs, and that sidecar matches.

---

### Task 4: Compatibility matrix and production-readiness report

**Files:**
- Create: `src/omniframe/release/compat.py`
- Create: `docs/compatibility-matrix.md`
- Create: `docs/phase-reports/phase5-release.md`
- Test: create `tests/test_compat.py`

**Interfaces:**
- Produces: `compatibility_report(env, presets=None) -> dict` mapping each export preset + codec to status (`import_tested` / `render_tested` / `unverified`) based on ffprobe probing done in this phase, plus a human-written matrix.

- [ ] **Step 1** — `compatibility_report`: for presets that can be probed (h264/webm/gif via ffmpeg presence on this machine: h264 render_tested; webm/vp9 render_tested if ffmpeg probe succeeds; qtrle/prores marked `unverified` unless actually produced) return a dict; never claim a codec was delivered unless the file was produced and probed.
- [ ] **Step 2** — Write `docs/compatibility-matrix.md` mirroring the report with a clear "tested here / not tested here" split and the exact machine/env.
- [ ] **Step 3** — `docs/phase-reports/phase5-release.md`: consolidate ALL phases' evidence into one production-readiness summary with the unresolved identity blocker flagged as **release-blocking**.

---

## Acceptance gate (Phase 5 and final)

Run and record:

```powershell
python -m compileall -q src
python -m pytest -q
python -m ruff check src tests
python -c "from omniframe.release.compat import compatibility_report; print(compatibility_report({}))"
python -m omniframe.cli doctor --json
```

Gate passes only if:
- full pytest zero failures;
- migration, release-artifact and compatibility modules import cleanly and their tests pass;
- no new lint errors introduced;
- release-checklist + compatibility-matrix + phase5 report exist;
- the repository-identity blocker is explicitly documented as unresolved and release-blocking (no silent rewrite);
- final confirmation that every earlier phase gate (0–4) passed.

## Final platform completeness

The platform is declared complete only when every phase gate (0–5) passes and the release-blocking repository-identity question is recorded for the user. Full proprietary application cloning is explicitly out of scope.