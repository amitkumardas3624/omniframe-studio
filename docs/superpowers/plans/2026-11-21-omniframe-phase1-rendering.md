# OmniFrame Phase 1 — Rendering and Compositor Hardening

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make every render and composite produce an auditable, reproducible artifact contract: structured backend result metadata, golden-frame verification, an artifact manifest per delivery, a deterministic FFmpeg media matrix, and bounded cleanup for timeout/cancellation. Preserve current runtime behavior and never claim host parity.

**Architecture:** The runtime already returns `RenderResult` (with `to_dict()`), `RenderIssue`, `ExportPreset` (data-only) and thin FFmpeg wrappers. This phase hardens that boundary by (1) making `RenderResult` carry accurate backend/verification metadata, (2) adding golden-frame checks against a stored reference, (3) emitting a JSON artifact manifest next to every delivery, (4) proving the preset matrix through real FFmpeg probes, and (5) guaranteeing temp-dir cleanup and timeout propagation.

**Tech Stack:** Python 3.10+, Pydantic, Pillow, FFmpeg/ffprobe, pytest, optional Playwright/Chromium. No new mandatory runtime dependencies.

## Global Constraints

- Preserve Python `>=3.10` and the existing `src/` package layout.
- Keep FFmpeg argument-list based; never use `shell=True`.
- Do not overwrite existing user files, untracked work or generated outputs.
- Distinguish `generated`, `structurally_checked`, `import_tested`, `render_tested` and `production_candidate`.
- Do not commit changes unless the user explicitly authorizes commits.
- Optional hosts (Chromium/DCC) absent → keep Pillow/stub fallback working and report the degraded backend truthfully.

## Verification contract

Every phase task must report: files changed; tests executed and exact result; skipped tests and why; host/dependency limitations; remaining unknowns; whether the task gate passed.

---

### Task 1: Backend result metadata accuracy

**Files:**
- Modify: `src/omniframe/engines/code_video/renderer.py` (RenderResult)
- Modify: `src/omniframe/engines/code_video/backends.py` (placeholders/fatal flag)
- Inspect only: `src/omniframe/engines/compositor/compositor.py`
- Test: extend/create `tests/test_render_metadata.py`

**Interfaces:**
- Consumes: existing `RenderResult.to_dict()`, `RenderIssue`.
- Produces: a `RenderResult` that records `backend_available`, `resume_requested`, `completed`, and an explicit `verification_level` enum string.

- [ ] **Step 1: Add the metadata fields**

Extend `RenderResult` with:
- `verification_level: str = "generated"` — one of `generated | structurally_checked | import_tested | render_tested | production_candidate`.
- `backend_available: bool = False`
- `resume_requested: bool = False`

Include all of them in `to_dict()`. Set `backend_available` from `self.backend.available()` (but guard the try/except already used by `CodeVideoRenderer.available()`).

- [ ] **Step 2: Wire the render call**

In `CodeVideoRenderer.render(...)`, set `resume_requested=bool(resume)` and, per roadmap levels, keep `verification_level` as `render_tested` when `completed and ok and backend not in {"stub","unknown"}`, else `import_tested` (`stub`) or `generated` (not completed). Do not claim `production_candidate` anywhere in this phase.

- [ ] **Step 3: Test**

Create `tests/test_render_metadata.py`:
- stub backend render → `verification_level == "import_tested"`, `backend == "stub"`, `backend_available` reflects reality, `to_dict()` contains all three new keys.
- `resume=True` sets `resume_requested is True`.
- a scene that fails to complete → `verification_level == "generated"`.

Run: `python -m pytest -q tests/test_render_metadata.py` — expected pass. Then run `python -m pytest -q tests/test_code_video.py` to confirm no regression.

---

### Task 2: Golden-frame verification

**Files:**
- Create: `src/omniframe/engines/compositor/golden.py`
- Modify: `src/omniframe/engines/code_video/renderer.py` (optional verify hook)
- Test: create `tests/test_golden.py`

**Interfaces:**
- Consumes: a directory of PNG frames (or a single frame image) + a stored reference.
- Produces: a `verify_frames(reference_dir, produced_dir, *, hash="sha256", tolerance=0)` function returning a structured report of matched/mismatched/missing frames.

- [ ] **Step 1: Implement `golden.py`**

```python
@dataclass
class GoldenReport:
    total: int
    matched: int
    mismatched: list[dict]   # {frame, expected_hash, actual_hash}
    missing: list[str]       # relative filenames expected but absent
    ok: bool
    def to_dict(self) -> dict: ...
```

`verify_frames(reference_dir, produced_dir, *, hash="sha256", tolerance=0.0)`:
- Reference filenames = sorted `frame_*.png` in `reference_dir`.
- For each, compute SHA-256 (or perceptual similarity within `tolerance` if provided, tolerance = max mean-abs-diff across RGBA via Pillow) against the produced file.
- Missing produced file → `missing`. Content differs → `mismatched`.
- `ok = len(mismatched)==0 and len(missing)==0`.

- [ ] **Step 2: Regression test**

Construct a reference dir and an identical produced dir in `tmp_path` (Pillow-generated deterministic images). Assert `ok is True`. Mutate one frame → assert `mismatched` has 1 entry and `ok is False`. Remove one file → assert `missing` records it.

Run: `python -m pytest -q tests/test_golden.py` — expected pass.

- [ ] **Step 3: Wire an optional verify hook**

Add `CodeVideoRenderer.render(..., verify_against: str|Path|None = None)`; when set, after a completed render call `verify_frames` and attach the `GoldenReport.to_dict()` to `RenderResult` (new field `golden: dict | None = None`, surfaced in `to_dict()`). No behavior change when `verify_against` is `None`.

---

### Task 3: Artifact manifest per delivery

**Files:**
- Create: `src/omniframe/engines/compositor/artifact.py`
- Modify: `src/omniframe/engines/compositor/compositor.py` (emit manifest in delivery methods)
- Test: create `tests/test_artifact.py`

**Interfaces:**
- Consumes: an output path produced by a compositor method.
- Produces: `write_artifact_manifest(output, *, tool, preset=None, meta=None, extra_inputs=()) -> dict` written to `output.with_suffix(output.suffix + ".manifest.json")`.

- [ ] **Step 1: Implement `artifact.py`**

Manifest JSON schema (all keys present):
```json
{
  "schema_version": "1.0",
  "kind": "omniframe_composite_artifact",
  "output": "<absolute path>",
  "sha256": "<of output file>",
  "size_bytes": 0,
  "produced_by": {"tool": "compositor", "preset": "...", "python": "...", "platform": "..."},
  "inputs": ["<absolute inputs>"],
  "meta": {},
  "created_at": "<iso>",
  "verification_level": "render_tested"
}
```
`write_artifact_manifest` computes SHA-256 of the output file, records inputs (normalized absolute), embeds `meta`, and returns the dict it wrote. Refuse to proceed if output does not exist.

- [ ] **Step 2: Emit manifests**

In `Compositor`, after a successful `frames_to_video`, `concat_videos`, `mux_audio`, `render_project`, `burn_subtitles`, `apply_lut`, `scale_video`, `extract_audio`, `mix_audio`, call `write_artifact_manifest` with the method name as `tool` and the selected preset. Keep method return values (`Path`) unchanged.

- [ ] **Step 3: Test**

Create `tests/test_artifact.py`: call `write_artifact_manifest` on a `tmp_path` file; assert schema keys, sha256 correctness, and that the JSON parses. Then for one compositor method that cannot run without ffmpeg, unit-test the manifest emission by monkeypatching `run_ffmpeg` if needed; otherwise assert the function-level behavior only.

Run: `python -m pytest -q tests/test_artifact.py` — expected pass.

---

### Task 4: FFmpeg media matrix

**Files:**
- Create: `src/omniframe/engines/compositor/probe.py`
- Modify: `src/omniframe/cli/main.py` (add a `doctor --matrix` or `probe` command surface) — only if CLI consistency allows it
- Test: create `tests/test_media_matrix.py`

**Interfaces:**
- Consumes: `ffprobe_info`, presets.
- Produces: `probe_media_matrix(media_files) -> list[dict]` that, for each media file, reports `path`, `container`, `video_codec`, `audio_codec`, `width`, `height`, `duration_seconds`, `fps`, and `compatible_with` (a dict mapping each preset name to a `(bool, reason)` from `video_copy_compatible`).

- [ ] **Step 1: Implement `probe.py`**

Reuse `ffprobe_info` and `video_copy_compatible`. Skip gracefully (report `"error"` reason) when a file is absent or ffprobe fails; never crash the matrix.

- [ ] **Step 2: Matrix tests**

Create `tests/test_media_matrix.py`. Since real encoded media may not exist in the fixture suite, test:
- a missing file → single entry with an error reason and `compatible_with` present as empty or error-annotated;
- a synthetic WAV or PNG (generated via Pillow) probed with ffprobe when available — mark `@pytest.mark.render` if it requires ffprobe/ffmpeg so CI on a bare runner reports a documented skip rather than a hard failure;
- `probe_media_matrix([])` returns `[]`.

Run the base (non-render) assertion tests; report the render-marked ones as skip-or-pass per the machine.

---

### Task 5: Cancellation, timeout and bounded cleanup

**Files:**
- Modify: `src/omniframe/engines/compositor/ffmpeg.py` (`run_ffmpeg` already has `timeout`; add `on_cancel` and a `CancelFlag`)
- Modify: `src/omniframe/engines/code_video/backends.py` (frame loop cancel check)
- Test: create `tests/test_render_safety.py`

**Interfaces:**
- Produces: a `CancelFlag` (thread-safe `threading.Event`) accepted by `run_ffmpeg` (poll to terminate early) and by `PlaywrightBackend.render` (check per frame) so an agent can stop a long render.

- [ ] **Step 1: Add `CancelFlag`**

```python
class CancelFlag:
    def __init__(self) -> None: self._event = threading.Event()
    def cancel(self) -> None: self._event.set()
    @property
    def cancelled(self) -> bool: return self._event.is_set()
```

- [ ] **Step 2: Wire into `run_ffmpeg` and the backend**

- `run_ffmpeg(args, *, timeout=1800.0, cancel: CancelFlag | None = None)`: when `cancel and cancel.cancelled` → raise a new `RenderCanceled` (add to `src/omniframe/core/errors.py`, subclassing `RenderError`). After launching with `Popen`, if `cancel` is provided, check a short-interval loop and `proc.kill()` on cancel.
- `PlaywrightBackend.render(...)`: accept optional `cancel: CancelFlag | None = None`; in the per-frame loop, `if cancel and cancel.cancelled: break`. Return `(frames, completed=False)` and emit a single warning issue "render canceled by request".

- [ ] **Step 3: Safety tests**

Create `tests/test_render_safety.py`:
- `CancelFlag` default not cancelled; `.cancel()` → cancelled.
- `run_ffmpeg` with a pre-cancelled flag raises `RenderCanceled` without invoking ffmpeg (monkeypatch `Popen` to a stub or fake binary).
- backend stub render with a pre-cancelled flag returns fewer than `duration_frames` frames and `ok is False`.
- temp-dir cleanup: assert code that uses `tempfile.mkdtemp(...)` in finally blocks removes dirs (unit-test `build_video_from_frames` with a monkeypatched failing `run_ffmpeg` → `tmp_dir` no longer exists).

Run: `python -m pytest -q tests/test_render_safety.py` — expected pass.

---

## Acceptance gate (Phase 1)

Run and record every command:

```powershell
python -m compileall -q src
python -m pytest -q
python -m ruff check src tests
python -m omniframe.cli doctor --json
python -c "from omniframe.engines.compositor.golden import verify_frames; print('GOLDEN_OK')"
```

Gate passes only if:
- full pytest has zero failures (new k-1 safety/golden/artifact/metadata tests included);
- `run_ffmpeg` still uses argument lists (no `shell=True`);
- optional Chromium/stub fallback still works and is truthfully labeled;
- golden, artifact, metadata and cancel/timeout modules import cleanly;
- lint shows no phase-introduced errors (pre-existing debt re-recorded);
- `docs/phase-reports/phase1-rendering.md` written with exact commands, results, skips and remaining unknowns.

When the gate passes, continue to Phase 2 (durable local jobs and safety).