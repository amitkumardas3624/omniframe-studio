# OmniFrame Platform Hardening Roadmap

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement each phase task-by-task. Each phase is an independently reviewable plan with its own acceptance gate.

**Goal:** Advance OmniFrame Studio from alpha orchestration foundation to an evidence-backed, local-first production platform without claiming proprietary-host parity.

**Architecture:** Retain the existing Python universal timeline, action registry, rendering engines, FFmpeg compositor and bridge tiers. Add the smallest missing boundaries in order: canonical contracts, reproducible rendering, durable local jobs/safety, bridge evidence, UI integration, and release hardening.

**Tech Stack:** Python 3.10+, Pydantic, Typer, Pillow, PyYAML, optional Playwright/Chromium, FFmpeg/ffprobe, optional FastAPI/Uvicorn, pytest, ruff and mypy.

## Global Constraints

- Preserve Python `>=3.10` and the existing `src/` package layout.
- Keep Pillow fallback available when Chromium/native acceleration is unavailable.
- Keep FFmpeg argument-list based; never use `shell=True`.
- Do not patch proprietary binaries or bypass DRM.
- Do not overwrite existing user files, untracked work or generated outputs.
- Distinguish `generated`, `structurally_checked`, `import_tested`, `render_tested` and `production_candidate`.
- Do not commit changes unless the user explicitly authorizes commits.
- Do not call a bridge host-tested when the target host was not actually opened and tested.

## Phase order and gates

### Phase 0 — Correctness and source-of-truth baseline

**Plan:** `docs/superpowers/plans/2026-11-21-omniframe-phase0-correctness.md`

**Gate:** clean editable-install test run, 19-action contract consistency, audio import collision removed, compile/lint checks reported, repository identity mismatch explicitly handled.

### Phase 1 — Rendering and compositor hardening

**Plan:** `docs/superpowers/plans/2026-11-21-omniframe-phase1-rendering.md`

**Planned scope:** backend result metadata, golden frames, artifact manifests, FFmpeg media matrix, cancellation/timeout cleanup and bounded render resources.

**Dependency:** Phase 0 test and contract gate.

### Phase 2 — Durable local jobs and safety

**Plan:** `docs/superpowers/plans/2026-11-21-omniframe-phase2-jobs-safety.md`

**Planned scope:** SQLite-backed local job lifecycle, restart/retry/cancel semantics, workspace/path policy, browser isolation, process/resource limits and localhost/optional-token boundary.

**Dependency:** Phase 1 artifact and cleanup contracts.

### Phase 3 — Bridge interoperability

**Plan:** `docs/superpowers/plans/2026-11-21-omniframe-phase3-bridges.md`

**Planned scope:** host-independent fixtures, translator loss reports, verification levels, CapCut version fixtures and Adobe/Resolve acceptance runbooks.

**Dependency:** Phase 0 canonical contracts and Phase 1 artifact manifests.

### Phase 4 — UI and agent experience

**Plan:** `docs/superpowers/plans/2026-11-21-omniframe-phase4-ui.md`

**Planned scope:** runtime-generated action data, project/media/artifact views, job queue controls, timeline inspection, bridge verification display, offline assets and accessibility checks.

**Dependency:** Phase 2 job API and Phase 3 evidence model.

### Phase 5 — Packaging and release hardening

**Plan:** `docs/superpowers/plans/2026-11-21-omniframe-phase5-release.md`

**Planned scope:** cross-platform install/test matrix, schema migrations, reproducible artifacts, release checklist, compatibility matrix and production-readiness report.

**Dependency:** all prior phase gates.

## Cross-phase verification contract

Every phase must report:

- files changed;
- tests executed and exact result;
- skipped tests and why;
- host/dependency limitations;
- remaining unknowns;
- whether the phase gate passed.

The final platform is complete only when every phase gate passes. Full proprietary application cloning is explicitly outside this roadmap.
