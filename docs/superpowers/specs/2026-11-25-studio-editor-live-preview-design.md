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
