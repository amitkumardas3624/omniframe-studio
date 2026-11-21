# OmniFrame Platform Hardening — Approved Design

**Date:** 2026-11-21  
**Status:** Design approved by user; implementation not started  
**Scope:** Full multi-phase platform productionization based on `docs/omniframe-technical-audit-bn.md`

## 1. Decision summary

OmniFrame Studio will be advanced as a **local-first, agent-first media orchestration and interchange platform**. The existing Python architecture, universal timeline, rendering engines, compositor, action registry and bridge model will be retained.

The implementation will proceed in gated phases:

1. correctness and source-of-truth baseline;
2. rendering/compositor hardening;
3. durable local job runtime and safety boundaries;
4. bridge interoperability and acceptance fixtures;
5. UI and agent experience;
6. packaging, release and compatibility hardening.

Each phase must have explicit tests and acceptance criteria before the next phase is treated as complete.

## 2. Goal

Make the current alpha platform dependable enough for repeatable agent-driven production workflows, while preserving the project’s honest capability boundaries.

The result must:

- expose one canonical, machine-readable action contract;
- produce reproducible render and composition artifacts;
- distinguish generated artifacts from host-verified artifacts;
- make long-running work observable, cancellable and recoverable;
- protect the local machine from unsafe paths, untrusted scene code and unbounded media jobs;
- provide evidence-backed bridge compatibility rather than unsupported clone claims;
- remain usable without proprietary hosts for the core rendering path.

## 3. Non-goals

This design does not attempt to:

- recreate Premiere Pro, After Effects or CapCut internals;
- patch proprietary binaries or bypass DRM;
- promise lossless conversion of proprietary projects;
- create a distributed SaaS control plane in the first implementation cycle;
- add a full interactive NLE editor before the core runtime is stable;
- silently alter or delete existing user work.

## 4. Current constraints to preserve

- Python `>=3.10` support remains the declared baseline.
- `src/` package layout remains supported.
- Pillow fallback remains available when Chromium/native acceleration is unavailable.
- FFmpeg invocation remains argument-list based; no `shell=True`.
- Optional dependencies must fail with actionable structured errors.
- Proprietary host integrations remain explicitly tiered as documented API, reverse-engineered interchange, or UI automation.
- Existing project files and untracked user work must not be overwritten by implementation scripts.

## 5. Target architecture

```text
CLI / MCP / REST / Web UI
          |
   Action Registry + generated schemas
          |
   Job Service + local durable store
          |
   OmniProject validation and routing
       /          |           \
 code-video   cartoon-2d     compositor
 Playwright     Pillow        FFmpeg
       \          |           /
      Artifact manifest + inspection
                    |
      translators / bridge adapters
                    |
       host acceptance evidence
```

### 5.1 Core boundaries

- **Action layer:** typed input/output contracts, validation, error codes and mutability metadata.
- **Job layer:** lifecycle, persistence, cancellation, retry, cleanup and progress events.
- **Engine layer:** render/compose operations; engines do not own API transport concerns.
- **Artifact layer:** outputs, manifests, hashes, diagnostics and verification level.
- **Bridge layer:** host-specific generation/inspection with explicit capability tiers.
- **UI layer:** presentation and control; it consumes generated runtime contracts rather than duplicating hard-coded action metadata.

## 6. Canonical status and evidence model

Every long-running or externally relevant operation should return a structured envelope similar to:

```json
{
  "success": true,
  "status": "completed",
  "job_id": "job-...",
  "warnings": [],
  "errors": [],
  "artifacts": [],
  "verification": "structurally_checked"
}
```

Allowed verification levels:

- `generated` — an output file was created;
- `structurally_checked` — schema/parser/ffprobe checks passed;
- `import_tested` — imported into the target host;
- `render_tested` — target host rendered successfully;
- `production_candidate` — compatibility and soak gates passed.

A generated bridge script or CapCut draft must never be reported as host success unless the corresponding host-level test was executed.

## 7. Phase 0 — correctness and source-of-truth baseline

### Deliverables

- generated action schema consumed by `tools.json`, guide output and UI;
- runtime count and documentation count reconciled at 19 actions or generated dynamically;
- unique module/package paths for example audio generators;
- editable-install and CI setup that works without manually setting `PYTHONPATH`;
- full test suite passing;
- repository/package metadata consistency report;
- no destructive cleanup of existing untracked files.

### Acceptance criteria

- `python -m pytest -q` passes from a clean editable install;
- focused and full tests cannot import the wrong `generate_audio` module;
- `/api/v1/tools`, MCP `tools/list`, `tools.json` and guide output expose the same action set;
- no stale `18 actions` claim remains where the runtime exposes 19;
- package URLs and installer URLs are intentionally configured and documented;
- `compileall` and lint/type checks pass for the changed code.

## 8. Phase 1 — rendering and compositor hardening

### Deliverables

- explicit backend result metadata: `playwright`, `stub`, `native`, or `python-fallback`;
- deterministic golden-frame fixtures for representative code and cartoon scenes;
- FFmpeg test matrix for supported containers, codecs, audio, subtitle and failure paths;
- artifact manifest with dimensions, frame rate, duration, streams, hashes and warnings;
- cancellation/timeout cleanup for browser and FFmpeg subprocesses;
- long-duration smoke test and bounded resource reporting.

### Acceptance criteria

- Playwright output is visually stable for fixed scene/seed/browser fixture;
- stub output is never presented as a real browser render;
- missing Chromium produces a structured degraded result;
- malformed scenes produce actionable errors without leaking secrets;
- representative 10-second and 30-second projects complete with expected media metadata;
- interrupted jobs do not leave orphan processes or misleading completed artifacts.

## 9. Phase 2 — durable local job runtime and safety

### Deliverables

- local durable job store, preferably SQLite-backed unless current project constraints prove a simpler format safer;
- lifecycle states: `queued`, `running`, `completed`, `failed`, `cancelled`, `resumable`;
- job progress, structured event log, retry policy and cleanup policy;
- workspace root enforcement, symlink/path traversal checks and asset boundary validation;
- browser scene policy with timeout, no-network default and controlled temporary directory;
- FFmpeg process limits and disk/resource quota hooks;
- localhost-only default with optional token authentication for non-loopback use.

### Acceptance criteria

- process restart preserves job state and does not mark incomplete work completed;
- cancellation is idempotent and leaves an inspectable failure/cancel record;
- all file outputs are inside the configured workspace/artifact roots;
- malicious relative paths and symlinks are rejected;
- remote binding without authentication is rejected or explicitly warned;
- job logs contain no credential-shaped values or raw secret payloads.

## 10. Phase 3 — bridge interoperability

### Deliverables

- bridge fixture corpus with minimal projects and expected generated outputs;
- capability report fields for `generated`, `import_tested`, `render_tested` and `production_candidate`;
- FCPXML, Resolve XML and EDL round-trip tests for supported fields;
- CapCut draft fixtures pinned to known application versions;
- Adobe and Resolve host acceptance scripts/manual runbooks;
- explicit warnings for unsupported effects, fonts, media, expressions and metadata;
- no host-success claim when the host is not installed or the fixture was not opened.

### Acceptance criteria

- every bridge can run host-independent generation tests;
- every bridge reports missing host/dependency without false success;
- at least one target-version acceptance result exists before a bridge is called import-tested;
- translator reports preserve unsupported-field warnings;
- CapCut draft compatibility is version-labelled;
- `.prproj`, `.aep/.aepx` and `.drp` inspection remains read-only.

## 11. Phase 4 — UI and agent experience

### Deliverables

- UI consumes `/api/v1/tools` and never hard-codes action counts;
- project/media browser and artifact manifest viewer;
- job queue/progress/cancel/retry surface;
- timeline inspection with clip, track, marker and validation details;
- bridge capability tier and verification-level display;
- offline/local copies of required UI assets or an explicit offline fallback;
- keyboard, focus, labels and contrast checks for primary controls.

### Acceptance criteria

- a user can start, inspect, cancel and review a local job;
- warnings distinguish degraded renderer from failed renderer;
- UI displays the same action and bridge data as the API;
- a project validation error is actionable from the UI;
- UI works when external CDN assets are unavailable.

## 12. Phase 5 — packaging and release hardening

### Deliverables

- reproducible build/install instructions for Windows, Linux and macOS where supported;
- CI matrix for Python versions and optional dependency profiles;
- schema migration/version policy;
- changelog, release checklist and compatibility matrix;
- signed or integrity-checked release artifacts where project infrastructure supports it;
- production readiness report that separates passing checks from untested host workflows.

### Acceptance criteria

- fresh environment can install and run doctor, tests and a representative render;
- release artifacts contain no generated output, secrets or unrelated workspace files;
- schema migration tests cover at least the previous supported project version;
- release notes state exact host/dependency limitations;
- all claims in README are backed by a test, fixture, or explicit manual acceptance result.

## 13. Error handling

Errors must remain machine-readable and human-actionable.

Required categories include:

- `E_SCHEMA` — malformed project or action input;
- `E_VALIDATION` — semantically invalid project/assets;
- `E_DEPENDENCY_MISSING` — optional runtime unavailable;
- `E_ENGINE_UNAVAILABLE` — requested engine cannot run;
- `E_JOB_NOT_FOUND` — unknown durable job;
- `E_JOB_CANCELLED` — cancellation completed;
- `E_PATH_POLICY` — output/input outside workspace policy;
- `E_HOST_UNAVAILABLE` — target DCC not installed or not reachable;
- `E_TRANSLATION_LOSS` — unsupported fields were dropped or approximated;
- `E_ARTIFACT_INVALID` — output failed structural/media checks.

Warnings must not be swallowed. The API, CLI, MCP and UI should expose the same warning/error identifiers.

## 14. Testing strategy

### Unit tests

- action schemas and registry generation;
- project validation and migration;
- path policy and workspace boundaries;
- job state transitions;
- artifact manifest and verification levels;
- translator field mapping and loss warnings.

### Integration tests

- CLI → engine → artifact manifest;
- REST/MCP → action registry;
- job restart/cancel/retry;
- browser and FFmpeg cleanup;
- UI API contract.

### Media regression tests

- fixed scene/seed golden frames;
- ffprobe metadata assertions;
- audio channel/sample-rate/duration assertions;
- subtitle and muxing fixtures;
- representative long-duration smoke renders.

### Bridge tests

- host-independent generated-file checks;
- fixture parsing/inspection;
- target-host manual acceptance records;
- compatibility matrix by host/application version.

### Security tests

- path traversal and symlink rejection;
- oversized asset/resource limits;
- untrusted HTML/JS timeout and network policy;
- localhost/remote binding policy;
- secret-shaped log redaction.

## 15. Rollout and change safety

- Work phase-by-phase; do not silently skip a failed acceptance gate.
- Preserve user-created untracked files and generated outputs.
- Prefer additive migrations and feature flags over destructive rewrites.
- Do not modify proprietary applications or binaries.
- Keep each phase in reviewable commits when the user later explicitly authorizes commits; until then, leave changes uncommitted.
- Report changed files, tests run, failures, skipped host tests and remaining unknowns after every phase.

## 16. Open items to resolve during implementation

These do not block the approved design but must be made explicit before the corresponding phase:

1. Exact canonical GitHub repository URL for package metadata and installers.
2. Whether local durable jobs should use SQLite or a JSON journal after measuring current runtime constraints.
3. Supported host/application versions for Adobe, Resolve, CapCut and Krita fixtures.
4. Whether non-loopback API access is required; default remains localhost-only.
5. CI providers and available host runners for proprietary application acceptance tests.

## 17. Definition of complete

The multi-phase implementation is complete only when:

- Phase 0 and Phase 1 automated gates pass;
- Phase 2 safety/job gates pass for local production workflows;
- every bridge has an honest verification level and compatibility record;
- UI/API/MCP expose the same generated contracts;
- release packaging and migration checks pass;
- remaining proprietary-host limitations are documented rather than implied away.

“Complete” does not mean that OmniFrame has recreated proprietary creative software. It means the OmniFrame control plane and its documented interchange/bridge workflows are dependable, bounded and evidence-backed.
