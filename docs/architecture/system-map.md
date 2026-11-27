# System map

## What OmniFrame Studio is, and is not

A local, agent-first motion graphics tool. One HTML/CSS/JS scene is a deterministic
function of time: every frame is addressable on its own, and an agent drives render,
inspect and compare through a Python API, a CLI, an HTTP backend and an MCP server.

It is not a general NLE and does not aim to be After Effects. There is no compositing of
arbitrary media streams, no plugin SDK, no GPU shader graph, no per-frame random grain.
The value that is actually being built: orchestration (actions, jobs, checkpoints,
bridges), determinism (frame-identical renders, which is the only thing that makes a
compare gate meaningful), composition rules encoded in `SKILL.md`, interchange with
CapCut / Premiere Pro / After Effects / Krita / DaVinci Resolve, and one Python core.

## Repository shape

```
src/omniframe/
  core/            pure Python, pydantic, no web dependency
    config.py  errors.py  logging.py
    timeline_schema/   models.py io.py schema.py validate.py translate.py
    agent_runtime/     actions.py registry.py router.py inspect.py checkpoint.py
  engines/
    code_video/        scene.py renderer.py backends.py composition.py seek_adapter.py
    compositor/        compositor.py ffmpeg.py probe.py presets.py golden.py
                       compare.py artifact.py audio.py raw_stream.py
    cartoon_2d/        scene.py render.py xsheet.py tween.py bridge.py
  bridges/         base.py after_effects.py premiere_pro.py davinci_resolve.py
                   capcut.py krita.py loss.py
  backend/server.py    FastAPI app; also serves the single-page UI
  cli/               main.py (Typer) __main__.py
  jobs/              store.py safety.py manager.py
  migrations/ release/ _native/   versioning, signing, optional native paths
  updater.py  mcp_server.py
  agent/             SKILL.md AGENT_GUIDE.md README.md schemas/tools.json
  ui/index.html      the whole Studio UI: markup, CSS, one inline script
examples/  tests/  docs/
```

Layering as practiced: `core` knows nothing about FastAPI; engines import their heavy
optional dependencies (Pillow, ffmpeg, Chromium) inside the function that needs them and
raise the typed errors from `core/errors.py` when the dependency is missing, so
`omniframe doctor` never dies because of an absent extra; `backend/server.py` is the only
web layer and imports core and engines; `ui/index.html` speaks only HTTP to the backend.
The one place that runs backwards is `core/agent_runtime/actions.py`, which imports a
helper from `backend/server.py` inside a function body (see the handover - it is
deliberate, and it is the weakest design point in this change).

## Data model (`core/timeline_schema`)

`OmniProject` is the document: `meta` (`ProjectMeta`: name, fps, width, height,
duration_frames, background, color_space, created/updated), `render_targets`, `tracks`,
`shots`, `transitions`, `assets`, `scene_graph`, `metadata`, `schema_version`.

A `Track` has an id, a `TrackKind` and `clips`. A `Clip` has an id, a `ClipKind`,
`start_frame`, `duration_frames`, plus the payload for its kind: `code` (`CodeSceneSpec`),
`cartoon` (`CartoonSceneSpec` / `CartoonLayerSpec`), `audio` (`AudioSpec`), `text`
(`TextSpec`), and shared `transform`, keyframes, `easing` (`EasingKind`), `effects`.
`Asset` carries path and metadata; `RenderTarget` names an output; `ValidationSeverity`
grades issues.

`io.py`: `load_document`, `load_project`, `save_project`, `dump_project`. Every consumer
downstream takes a validated `OmniProject`, which is why the HTTP endpoints stay thin -
they load, then hand the object to the engine.

## Render pipeline, and why frame N is addressable

```
clip.code  ->  CodeScene.from_clip(clip, project)  ->  CodeVideoRenderer(backend)
           ->  PNG frame(s)  ->  compositor/ffmpeg  ->  video
```

Scene contract (`examples/motion-reel-template/storyboard.md` states it, the engine
relies on it): one pure `window.seek(t)`; no CSS animation, no `requestAnimationFrame`,
no timer, no unseeded randomness; every node created up front; `seek` writes attributes
only. That is what lets a renderer jump straight to frame N without simulating 0..N-1 -
and therefore what lets the editor scrub and the compare gate sample the same instants
twice.

The one-frame trick is implemented once, in `_render_preview_frame` in
`backend/server.py`, and reused by the compare action: set the scene's `duration_frames`
to 1, prepend `window.__OMNIFRAME_FRAME__ = N` and
`window.__OMNIFRAME_TOTAL_FRAMES__ = total`, render, read `result.frames[0]`. The scene
composes the frame; the renderer only executes one.

Backends are `stub` (deterministic placeholder, no browser), `playwright` (real
Chromium) and `auto`. The backend chosen is reported back in the result - never
silently upgraded in the claim.

## Verification ladder

`engines/code_video/renderer.py` names five rungs:

`generated` -> `structurally_checked` -> `import_tested` -> `render_tested` -> `production_candidate`

Read them literally:

- `generated`: text exists.
- `structurally_checked`: schema and lint accepted it.
- `import_tested`: it ran in a backend without a browser.
- `render_tested`: real Chromium produced pixels.
- `production_candidate`: the top rung. Nothing here claims it on its own.

A claim may not outrank its rung. "The tests pass" is `structurally_checked` for a test
run; "it looks right" needs `render_tested` plus a reference to look right against.

## Agent runtime (`core/agent_runtime`)

`ActionRegistry` + `register_builtin_actions()`: **20** actions today, each with a JSON
Schema input and output, an engine tag, typed error codes and tags. `omniframe tools`
prints them; `GET /api/v1/tools` serves them; `src/omniframe/agent/schemas/tools.json` is
the committed snapshot; `tests/test_tool_manifest_consistency.py` fails when snapshot and
runtime drift, and also pins the exact ordered list of names so a rename is a deliberate
edit rather than a silent one.

Execution: `POST /api/v1/actions/execute` (name + parameters) or `POST /api/v1/mcp/call`.
Long work goes through `jobs/` - `store` (records), `safety` (resource limits), `manager`
(lifecycle) - exposed at `/api/v1/jobs`.

## HTTP surface (`backend/server.py`)

Every JSON reply is the `ActionOutput` envelope `{success, result, error, error_code}`.

| route | purpose |
|---|---|
| `GET /health` | liveness |
| `GET /ui` | the single-page Studio UI |
| `POST /api/v1/actions/execute` | run a registered action by name and parameters |
| `GET /api/v1/tools` | the action catalogue (the tool manifest) |
| `POST /api/v1/projects/get` | load a project -> `{project, project_path}` |
| `POST /api/v1/projects/save` | write a project back |
| `POST /api/v1/projects/validate` | schema and semantics, optional asset check |
| `POST /api/v1/projects/timeline` | timeline summary for the UI |
| `POST /api/v1/projects/render` | submit a render job |
| `POST /api/v1/inspector/validate` | validate a document, including one sent in-memory (editor phase 4) |
| `POST /api/v1/preview/frame` | one frame of a project, in-memory document accepted (editor phase 2/4) |
| `POST /api/v1/compare/frames` | the 7A gate: render frames, pair against the reference, verdict (editor phase 5) |
| `POST /api/v1/compare/report` | write the gate record as markdown beside the project (editor phase 5) |
| `GET /api/v1/bridges`, `POST /api/v1/bridges/detect` | host applications |
| `GET /api/v1/environment` | runtime probe |
| `GET /api/v1/system/update-status`, `POST /api/v1/system/update`, `POST /api/v1/system/restart` | updater |
| `GET/POST /api/v1/jobs`, `GET /api/v1/jobs/{id}`, `POST /api/v1/jobs/{id}/cancel` | job queue |
| `POST /api/v1/mcp/call` | an action call shaped for MCP |

Line numbers in that file move with every insert; grep the route string, do not trust
a number read from an old note.

## UI surface (`ui/index.html`)

One page, no build step, one inline `<script>`. A panel is
`<section class="panel" id="<slug>-panel" aria-labelledby="<slug>-panel-title">` with an
`<h2 class="panel-title" id="<slug>-panel-title">`; navigation is
`<a class="nav-link" data-panel="<slug>">`. `showPanel()` hides every `.panel` and shows
one, and `bindNavigation()` derives both the panel id and the click action from
`data-panel`, so **adding a panel needs no router code** - a nav link and a section are
enough.

Panels today: `dashboard`, `editor`, `projects`, `render`, `bridges`, `inspection`,
`actions`, `jobs`, `timeline`, `compare`.

The editor script is pure functions plus thin DOM wrappers on purpose: the browser
suites call the pure ones by name through `page.evaluate`, with no DOM mounted -
`editorParseFrameList`, `editorCompareVerdict`, `editorCompareDiffText`,
`editorComparePairModel`, `editorFrameToPx`, `editorPxToFrame`, `editorSnapEdges`,
`editorPlacement`, `editorTrim`, `editorTimingFields`, `editorParseParamsJson`,
`editorAssetsRows`, `editorValidateIssues`, `editorSiblingIntervals`, ... A required name
that is missing fails the suite through `pytest.fail`; only genuinely absent
Playwright/Chromium skips. Keep that rule when adding: a new pure function is not
tested until its name is in the suite `REQUIRED` list.

Constraint that will bite anyone adding UI: the a11y suite reads `index.html` **as
text** and treats `<input`, `<select`, `<img`, `<svg` found anywhere - including inside
JavaScript string literals - as real controls that need accessible names. Build nodes
with `document.createElement` instead of markup strings.

## The 7A compare gate (`engines/compositor/compare.py`)

This is the part worth reading carefully, because its failure is a feature.

- `CHECKLIST` holds the five mechanics of `SKILL.md` section 7A as frozen
  `ChecklistItem(id, label, status, note)` records, status starting `unchecked`:
  `background_shifts`, `grid_density`, `particle_construction`, `3d_focal_objects`,
  `outro_hierarchy`. Each label is the section's own wording, including what the
  failure looks like ("not a few sparse outlines").
- `ATTESTED` is `{match, gap, limit}`. Anything else - including a typo and including
  an absent row - is `pending`, never a pass.
- `verdict(rows)` computes against `CHECKLIST`, not against the supplied rows, so
  omitting an item cannot smuggle a pass. It passes only when nothing is pending,
  nothing is `gap`, and every `limit` carries a non-empty note. An unnamed engine
  limit is indistinguishable from a silent gap, so it fails.
- `parse_frames(text, total)` is comma-aware on purpose: a plain split on commas or
  whitespace turns `"1,,2"` into `[1, 2]` silently, and a gate that quietly compares a
  different frame than the one asked for is worth nothing. Empty token, non-integer
  and out-of-range all raise `ValidationError`. Duplicates dedupe, order sorts.
- `reference_frame_index(frame, project_fps=..., reference_fps=...)` maps **by
  instant**, not by index: 10 at 30 fps is 1/3 s is 20 at 60 fps. Index mapping would
  compare different moments and call the difference a defect.
- `extract_reference_frame` needs ffmpeg and raises `EngineUnavailable`
  (`E_ENGINE_UNAVAILABLE`) rather than guessing an index. `reference_frames_dir` is the
  ffmpeg-free path and is found leniently (`frame_%05d.png`, `%05d.png`, `frame_%d.png`,
  `%d.png`, then positional order in a sorted listing), so a hand-made contact sheet
  still compares while the primary convention matches the engine's own filename.
- `mean_abs_diff` needs Pillow and returns `None` when it is missing, unreadable, or the
  two images differ in size. `None` renders as `n/a`; a fabricated number would be
  worse than no number.
- `render_report_markdown` writes the record: a pair table, the checklist table, the
  engine limits, PASS or FAIL, and the unattested and gap lines.

Consequence worth stating plainly: **without a reference the gate reports FAIL.**
That is not a bug to fix by relaxing the rule; it is the rule. The executed record and
its reasons live in `docs/compare-gate.md`.

## Conventions

- Line endings matter: `ui/index.html`, `backend/server.py` and `engines/compositor/*.py`
  are CRLF; newly written tests and docs are LF. Edit `index.html` through a script that
  reads and writes with `newline=""`, or a patch can silently convert one region.
- Lint gate: `python -m ruff check src tests`. Test gate: `python -m pytest -q`. Both
  need `PYTHONPATH=src` when run as modules from the repository root.
- Optional dependencies stay optional: Pillow, Playwright, ffmpeg, and the host
  applications. Missing ones surface as a typed error at the call site, never as an
  import failure at module load - `omniframe doctor` has to survive a bare machine.
- Engine imports inside action handlers, not at module import.
- Claims use the ladder words literally: `generated`, `structurally_checked`,
  `import_tested`, `render_tested`, `production_candidate`.

## Commands that prove each layer

```powershell
$env:PYTHONPATH='src'
python -m pytest -q                       # whole suite
python -m pytest -q tests/test_compare_gate.py   # the 7A gate alone
python -m ruff check src tests            # lint gate
python -m omniframe.cli.main doctor       # environment and optional runtimes
python -m omniframe.cli.main tools        # action catalogue (expects 20)
python -m omniframe.cli.main ui --port 8765
```

The UI then lives at `http://127.0.0.1:8765/ui`. To exercise the editor and the compare
panel without authoring a project, load `examples/omniframe-promo/project.json`
(900 frames, 30 fps, 4 tracks, six `code_scene` clips).

## Where to look first

| question | file |
|---|---|
| what a project may contain | `core/timeline_schema/models.py` |
| how a scene becomes frames | `engines/code_video/renderer.py`, `scene.py` |
| how a scene must be written | `examples/motion-reel-template/storyboard.md`, `scene.js` |
| what the 7A gate enforces | `engines/compositor/compare.py` |
| what was actually attested | `docs/compare-gate.md` |
| what the UI can do | `ui/index.html` (panels) plus `backend/server.py` (routes) |
| what an agent may call | `core/agent_runtime/actions.py`, `agent/schemas/tools.json` |
| how error codes are organised | `core/errors.py` |
