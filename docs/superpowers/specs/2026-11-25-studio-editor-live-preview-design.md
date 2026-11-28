# Studio editor and frame-accurate live preview - design

Status: draft for user review. Date: 2026-11-25.

## Problem

`omniframe ui` is currently an operations console, not an editor. The user must
leave the browser to change a timeline, a clip boundary, a text/variable value or
an asset, and cannot see what the generated video looks like before paying for a
full render. The goal is a normal-editor experience in the browser plus a
Remotion-style preview that scrubs to an exact frame using the engine's pure
`seek(t)` contract.

## Evidence gathered

### Current UI and API (repository, commit `5c51aaf`)

- `src/omniframe/ui/index.html` is one 60 KB / 1565-line file. Its panels are
  Dashboard, Projects, Render Control, DCC Bridges, Inspection, Actions, Jobs and
  Timeline. `renderTimeline()` at line 1506 only renders a sorted read-only list
  from `/api/v1/projects/timeline`.
- `src/omniframe/backend/server.py` exposes `POST /api/v1/actions/execute`,
  `POST /api/v1/projects/validate`, `POST /api/v1/projects/render`,
  `POST /api/v1/projects/timeline`, bridges/tools/environment, jobs, update and
  a WS activity stream. There is **no project-write endpoint and no preview or
  single-frame endpoint**. `projects/render` calls the CLI with a hard-coded
  `/tmp/omniframe_render` output.
- The engine already has the primitives needed for a preview: `CodeScene`,
  `CodeVideoRenderer`, `build_frame_payload`, and the per-frame injection in
  `src/omniframe/engines/code_video/backends.py` that sets
  `__OMNIFRAME_FRAME__` / `__OMNIFRAME_FPS__` and runs scene JavaScript once per
  frame. The new composition runtime publishes `data-composition-variables` as
  `window.__OMNIFRAME_COMPOSITION__`.

### OpenCut reference (cloned outside the repo)

- `main` is a scaffold: `apps/web/src/routes/editor.tsx` says "Coming soon" and
  `apps/desktop/src/panels/{timeline,preview}.rs` are placeholders. The usable
  source is the `desktop` branch at `8918a87` (954 files).
- Useful patterns there: `apps/web/src/stores/{editor,timeline,preview}-store.ts`
  for split state; `hooks/timeline/use-timeline-{seek,zoom,playhead}.ts` for
  ruler scrubbing, zoom level and snap; `constants/timeline-constants.ts` for
  `PIXELS_PER_SECOND`, track heights and track-type colours;
  `components/editor/panels/timeline/*` for ruler/playhead/track/element; and
  `components/editor/panels/preview/preview-viewport.tsx` for the preview pane.
- Take the topology and interaction model, not the React implementation. We do
  not adopt GPUUI/Rust, and we do not copy OpenCut code.

### Remotion reference (cloned outside the repo)

- `packages/player/src/player-methods.ts` defines `seekTo(frame)` and
  `getCurrentFrame()`; `use-player-methods.ts` clamps the requested frame to the
  composition range and dispatches a seek event; `calculate-next-frame.ts` turns
  elapsed time into whole frames with playback range and loop handling.
- `packages/studio/src/api/seek.ts` is only `seek(frame)` forwarded to
  `Internals.timeValueRef.current.seek(...)` - the exact "editor asks player to
  jump to frame N" bridge we need.
- Adopt the rule: the editor stores an integer frame; time is derived as
  `frame / fps`. Never store a float playhead as the source of truth.

## Goals

1. Edit tracks, clip timing, text/variables and assets in the browser.
2. Scrub or type an exact frame and see that frame rendered before final export.
3. Keep every change on existing engine contracts and project schema.
4. Preserve the current console panels and their tests unchanged.

## Non-goals

- No full NLE feature parity, no proprietary host integration.
- No client-side rendering engine in the browser; preview is rendered by the
  existing Python/Playwright engine and shown as PNG.
- No collaborative editing, undo across sessions, or cloud storage.

## Architecture

Three independent layers, each testable alone:

1. **Backend contracts (additive).**
   - `POST /api/v1/projects/get` - load a project by path (read counterpart of
     the existing timeline endpoint).
   - `POST /api/v1/projects/save` - validate then write a project document back
     to its path. Reuses `validate_project`; rejects invalid documents with the
     existing `E_VALIDATION` code. Writes atomically (temp file + replace).
   - `POST /api/v1/preview/frame` - accepts `{project_path, frame, width?, height?}`
     (width/height default to `project.meta`). It selects the first clip with
     `kind == "code_scene"` in track order, or returns `E_VALIDATION` if none
     exists. It builds a `CodeScene` from that clip, overrides the injected frame
     for exactly one render, and returns a PNG plus metadata (`frame`, `t`,
     `fps`, `verification_level`, `issues`). Each response is a pure function of
     (project bytes, frame); no timer, no accumulated state.
   - Existing `POST /api/v1/projects/render` and the job queue stay unchanged.

2. **Frontend editor shell (additive to `index.html`).**
   - New "Editor" navigation item and panel: preview viewport on the left,
     timeline ruler + tracks at the bottom, inspector on the right (OpenCut
     topology, plain DOM/CSS, no new framework).
   - State: `currentFrame` (integer), `project` (JSON document), `selection`,
     `zoom` (pixels per second), `dirty`. Derived `t = currentFrame / fps`.
   - Preview image is fetched from `/api/v1/preview/frame` with a debounced
     request; in-flight requests are cancelled by request id so scrubbing cannot
     show a stale frame. Cache keyed by a hash of the project JSON + frame.
   - Timeline: zoomable ruler, playhead, draggable clip start/duration, track
     add/remove, snap to frame and to clip edges. Track types reuse project
     `kind` values; no new schema.
   - Inspector: per-clip timing fields and, for `code_scene`, a text area for
     `code.params` (the `content.json` shape) with `data-composition-variables`
     keys. Assets list shows id/kind/path from `project.assets`.

3. **Verification loop (from root `SKILL.md` section 7A).**
   - A "Compare" action renders the same frame numbers from a reference video
     (if supplied) and from the current output side by side; the checklist in
     section 7A applies before declaring the editor done.
   - Full render still goes through the existing job/Render panel.

## Data flow

```
project JSON -> GET /projects/get -> editor state -> edit (frame/clip/params)
             -> POST /projects/save -> validate -> atomic write
             -> POST /preview/frame(project, frame) -> PNG -> viewport
             -> POST /projects/render (existing) -> frames -> MP4
```

## Error handling

- All new endpoints return the existing `ActionOutput` envelope and reuse
  `E_VALIDATION`, `E_PROJECT_LOAD`, `E_RENDER`, `E_ENGINE_UNAVAILABLE`.
- Preview when Chromium is unavailable returns `verification_level =
  "import_tested"` with the stub backend result; the UI labels it as a degraded
  preview, never as a real render.
- Invalid frame (`< 0` or `>= duration_frames`) is rejected before rendering.

## Phased implementation

| Phase | Deliverable | Exit criteria |
|---|---|---|
| 0 | This spec reviewed and approved | User confirmation |
| 1 | Backend get/save/frame-preview endpoints + tests | pytest green; API returns byte-identical PNG for repeated (project, frame) |
| 2 | Editor shell: layout, project load/save, frame scrub + preview | a11y test still green; scrubbing to frame N changes the preview deterministically |
| 3 | Timeline editing: clips, tracks, snap, zoom | round-trip save/load preserves edits; unit tests for timing maths |
| 4 | Inspector: variables/content JSON + assets | params edits visible in preview frame; schema validation errors surfaced |
| 5 | Compare gate + docs | side-by-side checklist executed against the motion-reel template |

Phase 1 is deliberately backend-only: it creates the contracts the UI needs
without touching the 60 KB HTML file, so the existing console and its tests stay
stable while the new surface is built.

## Tests

- `tests/test_backend_editor_api.py`: get/save round trip, invalid project
  rejected, preview frame determinism, out-of-range frame rejected, stub backend
  labels `import_tested`.
- Existing `tests/test_ui_a11y.py` must remain green after each UI phase.
- New UI interactions are exercised with the installed browser automation in
  Phase 2+, never by eyeballing alone.

## Risks and limits

- Single-frame preview through Playwright costs roughly one browser frame;
  debounce and a small LRU cache keep scrubbing usable. It is not real-time
  video playback.
- The current `index.html` is large. Phase 2 adds a self-contained editor block
  and keeps existing IDs/functions untouched rather than rewriting the console.
- No approximate placeholder will be accepted as "preview works"; this follows
  the section 7A loop already added to the root skill.


## Phase 3 - timeline editing (append, approved 2026-11-26)

Deliverable per the phase table plus the user request: clips, tracks, snap,
zoom. Zoom already shipped in Phase 2; this phase adds clip drag/trim, snap to
frame and to clip edges, and track add/remove, all against the existing
schema with no new fields.

### Interaction model (OpenCut topology, plain DOM)

- Clip body drag = move: start_frame changes, duration_frames is fixed, both
  edges shift together.
- Clip left-handle drag = trim-in: start_frame moves and duration_frames
  shrinks/grows so the exclusive end_frame stays put.
- Clip right-handle drag = trim-out: only duration_frames changes; the start
  edge is pinned.
- Track add inserts an empty track (kind "video", unique id, index = max+1).
  Track remove deletes the track; if it still holds clips they go with it.

### Snap and collision rules

A valid placement X for a clip of duration D places it at [X, X+D) which must
not overlap any other clip [s, e) on the same track: valid iff X >= e or
X + D <= s. The free positions we ever choose from are the frame-aligned
set generated by the clip edges and the timeline bounds:

    { 0, maxExclusive - D }  :: timeline bounds
    { s - D, s, e }          :: tuned to just touch each sibling's edges

where s - D places the clip flush before a sibling and e places it flush
after; s keeps a gap of zero as a legal snap target too. Before searching the
pool, editorPlacement aims the requested frame at the nearest sibling edge
within a 4-frame pull (editorSnapEdges); timeline bounds are not pull targets
- they are enforced by clamping - so a free move does not stick to the start
or end boundary. From the candidates that pass the no-overlap and
[0, maxExclusive - D] tests we pick the one closest to the aimed frame, ties
to the smaller value. (A px-driven ruler snap beyond the 4-frame edge pull is a
future nicety, not this phase.)

Trims keep the opposite edge pinned and clamp length to >= 1; a trim that
would cross a sibling clamps to the sibling edge instead of overlapping.

### Pure function surface (unit-testable through the browser)

The following are top-level functions in the inline script and are called
directly by the Playwright timing-math tests (no DOM dependency):

- editorFrameToPx(frame) / editorPxToFrame(px)  :: label offset + zoom mapping
- editorSnapEdges(frame, targetFrames)            :: nearest target, else frame
- editorPlacement(requested, duration, siblings, maxExclusive)
- editorTrim(prevStart, prevDuration, edge, requested, siblings, maxExclusive)

DOM wiring uses only these; the drag handlers read px off the timeline rail
and pass them through the pure functions, so the math is exercised in
isolation by tests and the UI by drags.

### Exit criteria

- round-trip: drag then Save posts /projects/save; a fresh /projects/get
  returns the same start_frame/duration_frames, and the saved document
  passes validate_project with no overlap ERROR
- unit tests for the timing maths above run through the installed browser
- tests/test_ui_editor_layout.py and all prior UI suites stay green


## Phase 4 - inspector: variables/content JSON + assets (append)

Deliverable per the phase table plus the user request: per-clip timing fields;
for `code_scene` a text area for `code.params` (the content.json shape) with
`data-composition-variables` keys; and an assets list showing id/kind/path
from `project.assets`. Exit criteria from the phase table: params edits are
visible in the preview frame, and schema validation errors are surfaced.

### Gap the phase closes

The Phase 2 preview endpoint (`POST /api/v1/preview/frame`) loads the project
from disk via `load_project(project_path)`, so an in-memory params edit in the
browser could never reach the rendered PNG. Phase 4 makes the preview request
accept an optional in-memory document and renders from that document when it is
supplied (additive: omitting it keeps current disk-loading behaviour).

### Backend contracts (additive)

- `PreviewFrameRequest` gains `project: dict[str, Any] | None = None`. When
  present, the document is `OmniProject.model_validate`d (schema errors
  surface as `E_VALIDATION`) and used instead of the on-disk file; the frame
  is then a pure function of (in-memory document, frame).
- New `POST /api/v1/inspector/validate` accepting
  `{project: <document>}` and returning
  `summarize(validate_document(document))` - the same struct the existing
  `/api/v1/projects/validate` returns, but for an arbitrary in-memory doc so
  the inspector can surface E_CLIP_OVERLAP and friends before saving.
- The existing save path already returns `E_VALIDATION` on schema rejection.

### Frontend inspector (additive to the editor panel)

- Clicking a clip selects it (`editorSelection`); the inspector then shows its
  start_frame and duration_frames as number inputs. Applying edits mutates the
  in-memory project copy (start via editorPlacement, duration via editorTrim),
  re-renders the timeline, marks dirty, and re-seeks the preview through the new
  in-memory project path.
- For a `code_scene` clip a `<textarea>` edits `code.params` as pretty JSON,
  with a hint listing the `data-composition-variables` keys declared in
  `code.html`. Apply parses the JSON (invalid JSON or a non-object is shown as
  an inline error, never applied), writes `code.params`, re-renders, and
  re-seeks so the params change appears in the frame.
- An assets list underneath renders id/kind/path for each `project.assets`
  entry, and a validation area shows issues returned by the preview/validate
  calls.

### Pure function surface (unit-tested through the browser)

- editorSelectedClip(trackId, clipId)          :: in-memory selection -> clip|null
- editorTimingFields(clip)                     :: {start_frame, duration_frames}
- editorParseParamsJson(text)                  :: {ok, params} | {ok:false, error}
- editorApplyParams(clip, text)                :: surfaces parse/type errors
- editorCompositionKeys(html)                  :: keys from data-composition-variables
- editorAssetsRows(project)                    :: [{id, kind, path}] from project.assets
- editorValidateIssues(issues)                 :: schema-error lines, errors only

### Exit criteria

- backend: preview with an in-memory doc whose code.params.text differs from
  the on-disk doc yields a different PNG vs the disk-loaded preview; an invalid
  in-memory doc is rejected with E_VALIDATION
- backend: /api/v1/inspector/validate reports structured issues (E_CLIP_OVERLAP)
  for an overlapping in-memory doc and ok for a clean one
- frontend: params edits and timing edits round-trip through the in-memory
  project into the preview frame; schema/parse errors are rendered inline
- tests/test_ui_a11y.py and all prior UI suites stay green

### Verification (what was actually run)

- `tests/test_ui_inspector_api.py` (4 tests) - the preview request with an
  in-memory document whose `code.params.text` differs from disk returns a
  different PNG than the disk-loaded preview; a malformed in-memory document
  returns `E_VALIDATION`; `/api/v1/inspector/validate` reports `E_CLIP_OVERLAP`
  as an `error` for an overlapping document and `ok: true` for a clean one.
- `tests/test_ui_inspector_math.py` (9 tests) - the pure helpers, called
  inside the installed Chromium through the served page: selection resolution,
  timing fields, params JSON parse/apply (including rejection of bad JSON and of
  a non-object), composition keys, assets rows, issue filtering.
- All prior suites stay green (timeline math, round-trip, editor layout, editor,
  a11y, server); full repo suite exits 0 with the one Chromium-marked skip.
- Live check in the user's own Chromium against the served `/ui`: loading
  `examples/code-explainer/project.json` reaches `render_tested`, selecting the
  `intro` clip populates timing + the params text area (seeded `{}`) +
  `Composition keys (data-composition-variables): none declared`, applying
  `{"text": "PHASE4-VISIBLE"}` makes the next preview request carry that document
  (`sentProjectParams`), and the same request with the stub backend returns a
  byte-different PNG (`pngsDiffer: true`). An overlapping sibling surfaces
  `E_CLIP_OVERLAP` in the inspector panel, not only in the API.
- Level: `render_tested` for the preview frame; the params-to-PNG effect is
  `import_tested` on the stub backend, by design - the code-explainer template
  does not read `params`, so a real Chromium frame is pixel-identical until a
  template consumes `window.__OMNIFRAME_PARAMS__`.



## Phase 5 - compare gate + docs (append)

Deliverable per the phase table: a Compare action that renders the same frame
numbers from a reference and from the current output side by side, with the
root SKILL.md section 7A checklist executed against the motion-reel template,
plus the docs that make the gate repeatable.

### Why the gate is code and not a habit

Section 7A exists because a template once passed JSON, lint and render checks
while its kinetic layers, grid density, particle construction, 3D sphere and
outro hierarchy were missing. A checklist that lives only in a document can be
skipped silently. So the checklist becomes data with a verdict function, and
the comparison produces a record carrying exact frame numbers.

### Backend contracts (additive)

- src/omniframe/engines/compositor/compare.py
  - CHECKLIST: the five 7A mechanics as ChecklistItem(id, label, status, note),
    with status starting at unchecked.
  - parse_frames(text, total): "0, 120,240" to sorted unique frame integers. An
    empty list, an empty field, a non-integer and an out-of-range frame are
    E_VALIDATION rather than a silent substitute.
  - reference_frame_index(frame, project_fps, reference_fps): the reference
    frame at the same instant, so a 60 fps reference is sampled at twice the
    project frame instead of comparing the wrong moments.
  - reference_fps(video) and extract_reference_frame(video, index, dir):
    ffprobe rate and exact-frame PNG through ffmpeg; E_ENGINE_UNAVAILABLE when
    ffmpeg is missing, never a fabricated frame.
  - mean_abs_diff(first, second): mean absolute RGBA difference 0..255, and
    None when Pillow is missing, unreadable, or the sizes disagree (no number
    is better than a wrong number).
  - verdict(rows): ok only when every 7A mechanic is attested match or limit,
    no gap remains, and every limit carries a note naming what remains. An
    unattested row is pending, never a pass.
  - render_report_markdown(payload): the markdown record of a run, with the
    frames inspected, the per-mechanic status and the stated engine limits.
- POST /api/v1/compare/frames accepts project_path, frames, optional
  reference_video, optional reference_frames_dir, width, height and backend. It
  renders each project frame and, when a reference is supplied, the reference
  frame at the same instant, returning per-frame
  {frame, t, current, reference, reference_frame, diff} plus the checklist and
  verdict. Exactly one reference source may be given.
- POST /api/v1/compare/report accepts project_path, compare and an optional
  output_path, and writes the markdown gate. The default path is
  <project stem>-compare-gate.md beside the project.

### Frontend (new Compare panel)

- A Compare navigation entry and panel: project path, optional reference video,
  optional reference PNG directory, frame list, backend and a Compare button.
- Each returned frame renders as a labelled pair - current output beside the
  reference at the same instant - with the frame numbers and the pixel gap,
  never as summary statistics alone.
- The five 7A mechanics render as rows with a status select (unchecked, match,
  gap, limit) and a note field; the verdict line states PASS or FAIL, the
  pending and gap counts, and any limit left without a note.
- Write report posts the attested run and shows the path it wrote.

### Pure functions (unit-tested through the served page)

- editorParseFrameList(text, total): sorted unique frames, or an error object
- editorCompareVerdict(rows): ok, pending, gaps, limits_without_note
- editorComparePairHtml(row): labelled pair markup with frame numbers visible

### Exit criteria

- the gate runs from the editor against a project and returns paired frames for
  the exact frame numbers asked for, with the pixel gap per pair
- a reference video is sampled by instant, not by ordinal
- no pass verdict without all five 7A mechanics attested, and a limit needs a
  stated note
- the checklist is executed against the motion-reel template at real frame
  numbers, and the result - including what could not be attested without the
  reference reel, and the engine limits - is recorded in docs/compare-gate.md
- tests/test_ui_a11y.py and all prior suites stay green

## Phase 6 - Remotion-like studio UI (append)

### Frontend

- The editor panel now reads like a Remotion studio: a canvas in the middle, a
  transport under it, a tabbed inspector on the right, and the timeline along
  the bottom. The three grid regions (`preview-left`, `timeline-bottom`,
  `inspector-right`) and their names are unchanged, so the layout contract and
  its tests still hold.
- The transport carries: jump to first, step one frame back, play/pause, step one
  frame forward, jump to last, a frame field with a Go button, a timecode, the
  in/out readout, a zoom mode (Fit, 50, 100, 200 percent), a playback rate
  (0.25x to 2x) and a loop toggle. Keyboard: Space plays, the arrow keys step a
  frame, G focuses the frame field. Playback advances the integer frame as fast
  as the frames render - there is no client-side player, because every frame
  is an HTTP render of the project.
- The inspector is tabbed: **Props** (the selected clip `code.params` as
  name/value rows, with the raw JSON still available underneath), **Variables**
  (project level key/value rows), and **Project** (validation and assets). The
  project path, Load and Save moved to a toolbar above the regions so they are
  always reachable, the way Remotion keeps the composition picker visible.
- Project variables are real: they live in `metadata.variables` on the project
  document and are injected into every rendered frame as
  `window.__OMNIFRAME_VARIABLES__`, so a scene can read them without knowing
  anything about the editor.

### Backend

- No new endpoint. The existing ones serve the new workflow unchanged:
  `projects/get` and `projects/save` carry the variables, `preview/frame` renders
  the frame the transport asks for, `inspector/validate` backs the Project tab,
  and `compare/frames` and `compare/report` are unchanged.
- `preview/frame` now injects the variables global next to the frame globals.

### Exit criteria

- The player, the tabs and the variables round trip are covered by
  `tests/test_ui_studio.py` in a real browser.
- `tests/test_ui_editor.py`, `tests/test_ui_editor_layout.py`,
  `tests/test_ui_a11y.py` and every other suite stay green.
