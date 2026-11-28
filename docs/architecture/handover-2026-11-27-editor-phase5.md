# Handover - Studio editor, spec phase 5 (compare gate)

Date: 2026-11-27. Written by the agent that did the work, for the next agent or
human to pick it up, and specifically so that a reviewer can find what is wrong
with it without re-deriving the whole thing.

Status word, used honestly: **the gate itself reports FAIL.** Everything below
describes working machinery around inherited material that has not been compared
to its reference, because the reference is not in the repository. Do not read this
document as "the editor is done".

## State

- Branch `master`, also `omniframe-platform-hardening`; both pushed, both at
  `209a092`; `HEAD` in the hardening worktree is the same commit; working tree
  clean; the two branches are identical right now (the hardening worktree is
  fast-forwarded from `master` after each change).
- CI: `.github/workflows` runs on GitHub Actions, 10 jobs (wheel build, five
  installs across 3.10/3.11/3.12 and the `[dev]` extras, three test matrices).
  Green at `28c9b13`, `8937cd2`, `4dc75f2`, `209a092`
  (runs 46020174150, 46037338726, 46037795225, 46038431267).
- Local: `python -m pytest -q` green with `PYTHONPATH=src`; one skip, which predates
  this change; `ruff check src tests`
  clean.

## What changed in this phase, by file

| file | change |
|---|---|
| `src/omniframe/engines/compositor/compare.py` | new, 486 lines: the five 7A mechanics, `parse_frames`, `reference_frame_index`, `reference_fps`, `extract_reference_frame`, `mean_abs_diff`, `build_compare`, `_find_reference_png`, `verdict`, `render_report_markdown` |
| `src/omniframe/backend/server.py` | new request models `CompareRequest`, `CompareReportRequest`; new routes `POST /api/v1/compare/frames` and `POST /api/v1/compare/report`; both render through `asyncio.to_thread` |
| `src/omniframe/ui/index.html` | new Compare panel: nav link, section, styles, and the compare script block, inserted immediately before `onEditorZoom` |
| `src/omniframe/core/agent_runtime/actions.py` | new `compare.frames` action (catalogue now 20) |
| `src/omniframe/agent/schemas/tools.json` | regenerated snapshot, exactly one tool added |
| `tests/test_compare_gate.py` | new, 22 tests: checklist shape, frame parsing and its rejections, instant mapping, every verdict branch, report text, both endpoints, one real-ffmpeg case |
| `tests/test_ui_compare_math.py` | new, 19 browser tests: the four pure functions, panel wiring, DOM round trip, parity with the backend checklist, parser and verdict |
| `tests/test_ui_a11y.py` | `PANEL_TITLES` gains `"compare": "Compare"`, so the new panel is held to the same naming rules as the others |
| `tests/test_ui_server.py` | expected tool count 19 -> 20 |
| `tests/test_tool_manifest_consistency.py` | the pinned action-name list gains `compare.frames` |
| `docs/compare-gate.md` | new, 333 lines: the executed 7A record, the measurements, the engine limits, and the commands that close the gate |
| `docs/superpowers/specs/2026-11-25-studio-editor-live-preview-design.md` | a Phase 5 section appended (contracts and exit criteria) |

## Decisions, and the alternative each one rejected

1. **All five rows stay unattested.** Rejected: attest from source - `scene.js` has one
   builder per chapter (`intro`, `kinetic`, `systems`, `particles`, `dimension`, `data`,
   `flow`, `outro`), so the mechanics demonstrably exist - and mark them `match`. Reason
   rejected: 7A item 2 asks whether the output reproduces the reference's actual visual
   behaviour, not whether code exists. Source presence is capability; 7A compares
   pictures arrived at independently. Its own opening calls a blueprint a hypothesis
   rather than a finished template. `match` without the reference would be the
   exact dishonesty the gate exists to stop.
   Cost: the gate is red, and a red gate gets ignored. Mitigation: `docs/compare-gate.md`
   says why it is red and what turns it green, in one command.

2. **Attestation by measurement, not by eye.** Rejected: state that I looked at the frames.
   Reason: pixels do not reliably reach my context, so that would have been a claim I could
   not back. What the numbers do buy: proof that the frames are not empty, not identical, and
   that per-chapter structure differs in the direction the storyboard predicts - the type
   chapter inverts to the declared cream `#F1EDE3` within 1 unit per channel, the systems
   chapter carries the orange accent at 2.53 percent distributed rather than pooled, the
   flow chapter produces 2161 distinct colours where a flat composition produces hundreds.
   What they cannot buy: "looks like the reference". The record says exactly that, and
   relabels the whole exercise as a substitute for item 1 rather than a completion of it.

3. **Seven sampled frames, not the five I started with.** Rejected: five frames
   (60/180/400/495/840) covering the five mechanics. Reason: 60 is INTRO and 495 is
   DIMENSION; only three of the five sat in a chapter that implements the mechanic they were
   standing for. Added 300 (SYSTEMS) and 700 (FLOW), so now every row has a frame from a
   chapter that actually does the job. A deliberate deviation, recorded in the document.

4. **A `limit` with an empty note fails.** Rejected: treat `limit` as a softened `gap` and
   pass it. Reason: 7A item 3 says "say so explicitly and list what remains"; an unnamed
   limit is operationally identical to a gap nobody noticed. Making the note mandatory turns
   that sentence into a mechanical rule instead of a habit of goodwill.

5. **`mean_abs_diff` returns `None` on a size mismatch.** Rejected: infinity, which is what
   `golden._mean_abs_diff_rgba` does and would have been the consistent choice. Reason: in a
   report a large number reads as a measurement and invites comparisons; `n/a` reads as not
   comparable. The gate is a decision aid, not an optimiser. Recorded here as a
   deliberate divergence, not an oversight.

6. **The panel builds nodes with `document.createElement`.** Rejected: markup strings and
   `innerHTML`, which is what I wrote first and which passed `node --check`. Reason: the a11y
   suite reads the file as text and correctly saw `<input data-note=...>` and `<img src=...>`
   inside the script as unnamed controls. It was right for two reasons - a string-built
   control is still a control a reader never named, and it is also an injection surface. The
   rewrite is longer and the backend contract did not move.

7. **`compare.frames` reuses the private `_render_preview_frame` of the web module.** Rejected:
   copy about 25 lines of frame addressing into `actions.py` (two implementations of the one
   trick that makes a frame addressable - they would drift), and promote the helper to a new
   shared module first (a bigger refactor than this phase should carry, and it would move four
   files this change does not otherwise touch). Reason: one implementation. Cost: a
   function-local import, a dependency on the `ui` optional extra, and `core` knowing a private
   name in `backend`. **This is the weakest point of the change; a reviewer should rule on
   where the helper belongs before it is reused again.**

8. **No `production_candidate` anywhere.** Reason: the full release matrix
   and the acceptance pass did not run here. Claiming the top rung because the tests are green
   is the specific inflation the ladder exists to prevent.

## Evidence, and how much of it survives a fresh clone

**Measured frames.** Seven PNGs at 1920x1080, every one `ok: true`, `issues: []`, through
Playwright Chromium, with the frame and total overrides prepended so `seek(t)` produced the
requested instant. The table (`bg`, `ink`, `warm`, `cool`, `colours`, `edge` per frame, mapped
to the chapter ranges in `storyboard.md`) is in `docs/compare-gate.md` section 4.

**Palette corroboration.** Declared dark base `#0B0A0F` = (11, 10, 15); six frames measure a
modal colour of (15, 14, 19), a uniform +4, which is the static grain filter composited over a
flat field. Declared light base `#F1EDE3` = (241, 237, 227); frame 180 measures (240, 236, 226),
within 1 unit per channel - the type chapter really does invert the field it paints. Accent
separation: orange is +221 on R-B, blue is -218, while the neutral ramp never exceeds 14, so a
threshold of 40 between them cannot be firing on anti-aliasing.

**Honest caveat, and the largest reproducibility gap.** The scripts that produced those
numbers, and the seven PNGs themselves, live in `out/`, which is gitignored. The numbers are
true of the run that produced them and cannot be re-derived from a fresh clone without
rewriting the measurement script. The record says so; it does not present them as CI output.

**What the test suite caught while this phase was being assembled** - five real regressions,
none of which I predicted: the tool-manifest snapshot was stale; the pinned action-name list
did not have the new name; `test_ui_server.py` hard-coded 19 tools; and two a11y structural
tests failed because the compare panel first built its checklist and image pairs with markup
strings inside JavaScript, which the a11y suite reads as real unnamed `<input>` and `<img>`
elements. All five were fixed in the markup and the snapshots, not by loosening a test.

**Commands, and what each one proves.**

```powershell
$env:PYTHONPATH='src'
python -m pytest -q tests/test_compare_gate.py     # the gate contract, 22 tests
python -m pytest -q tests/test_ui_compare_math.py  # panel maths and parity, 19 tests
python -m pytest -q tests/test_ui_a11y.py           # panel naming and icon rules
python -m pytest -q                                # whole suite
python -m ruff check src tests                      # lint gate
```

**What was exercised live, on the running server.** `GET /ui` 200; `GET /api/v1/tools` 20
actions including `compare.frames`; `POST /api/v1/preview/frame` frame 120 of
`examples/omniframe-promo/project.json` with the stub backend -> `import_tested`, 1920x1080,
image bytes present; `POST /api/v1/compare/frames` frames 0, 120, 450 ->
`reference_supplied: false`, `diff: null` on every row, verdict `pending: 5`.


## 9. Review findings and what changed after them

A review pass (a static read plus live probes against the running server, and
an independent second pass) found nine issues. All are fixed; the record above
was written before the fixes and has been corrected where it described the old
behaviour.

1. **The Compare panel never ran.** `compareStatus` and `compareError` were
   called but never defined, so every click threw a `ReferenceError` before a
   request was sent. The helpers are back, and two new browser tests drive
   `runCompare` and `writeCompareReport` against the real server, which is
   what the first version of this suite should have done.
2. **A PASS could be forged.** The report endpoint rendered the verdict sent by
   the client. It now recomputes the verdict from the checklist rows it was
   given and ignores the client value.
3. **An unreadable reference was reported as compared.** A missing video, a
   missing or empty frame directory, an unprobeable frame rate and a missing
   ffmpeg all produced `success: true` with `reference_supplied: true` and no
   reference images. These are errors now, and the payload carries
   `reference_frames_extracted`, `reference_frames_requested` and
   `reference_problems` so a partial comparison says so.
4. **The written record claimed comparisons that did not happen.** It said
   `Reference: <path> (video)` and listed a reference frame per row even when
   nothing was extracted. It now states how many of the requested frames were
   actually read, names the file used for each row, and lists the problems.
5. **The wrong reference image could be compared.** The old positional fallback
   mapped frame N to the Nth PNG in the folder, so a folder of `f060`, `f180`
   and `f400` matched frame 0 to reference frame 60 - with a real diff number.
   Matching is by frame number now, and position is never guessed.
6. **The two parsers disagreed.** The backend accepted `+3`, `1_0` and
   non-ASCII digits; the browser rejected them. The backend is strict now and
   the parity test covers twenty-one tokens instead of six.
7. **A malformed report payload returned HTTP 500.** The render happened
   outside the error handling. It is inside it now, and a non-numeric frame
   returns `E_VALIDATION`.
8. **The report could be written anywhere.** `output_path` was unconstrained.
   The record is now kept inside the project folder, and a path outside it
   returns `E_PATH_SECURITY`.
9. **Two smaller ones.** The frame index rounded half to even, so a boundary
   case could pick the earlier reference frame; it rounds half up now. And the
   pixel diff looped over two million pixels in Python (1.65 s per HD pair),
   so it now uses the same metric through Pillow in C.

## Known gaps, ranked by how much they would mislead you

1. **The panel fetch path was never end-to-end tested - now it is.** The review
   found that it could not have been: `runCompare` threw a `ReferenceError` on every
   click. Two browser tests now drive `runCompare` and `writeCompareReport` against
   the real server and assert on what the panel painted. It was exercised once by hand against the running server in this session,
   with a direct HTTP call for frames 0, 120 and 450 of the promo project, and it answered
   `reference_supplied: false`, `diff: null`, `pending: 5` - which is the honest answer for a run
   with no reference - but that was a probe script, not a click. **Treat a click-through as the
   first thing to do.**
2. **The measurements cannot be re-derived from a clean clone.** The generator scripts and the
   seven PNGs live under `out/`, which is gitignored. The numbers are true of the run that
   produced them; they are not CI output and they are not reproducible without the script.
   Either commit the script plus small fixtures, or drop the numbers from the record.
3. **The verdict exists twice**, as `COMPARE_MECHANICS` + `editorCompareVerdict` in the page and
   `CHECKLIST` + `verdict` in Python. A parity test pulls the Python list into the browser and
   compares, so drift fails the suite at the next run - but it fails late, and only if the suite
   runs. A `GET /api/v1/compare/checklist` return would remove the duplicate; see question 3.
4. **The compare panel does not follow the panel system.** Every other panel is docked
   `position: fixed; right: 0; width: 400px`, and the editor is anchored to the console grid
   areas. Compare is an absolute overlay from `left: 260px` to `right: 0`. It works, and the
   layout tests only constrain the editor, but a reviewer interested in visual consistency will
   object, correctly.
5. **`tests/test_ui_server.py` hard-codes 20.** Every new action now needs an edit to an
   unrelated test. Asserting against `len(registry.names())` would carry the same meaning and
   never go stale.
6. **Two documents describe the gate.** `docs/compare-gate.md` is the executed record and is
   authoritative for the numbers; this handover is context. They can drift. When they disagree,
   the record wins.
7. **The gate cannot find the reference even knowing its hash.** `blueprint.json` carries the
   sha256 of `video.eb2ddbff.mp4` but no location. Closing 7A item 1 needs the file supplied
   out of band; the record says what to do with it once it exists.

## Open questions, with the answer I would argue for

1. **Where should the frame-addressing helper live?** My answer: a new
   `engines/code_video/preview.py` (it does not exist yet). The trick is renderer knowledge - `duration_frames = 1`,
   the two injected globals, `result.frames[0]` - and `core` should not know about renderers at
   all. Both `backend` and `core/agent_runtime` already import engines, so moving it there
   removes the one backwards import instead of legalising it. Counter-argument: `preview.py`
   would be a module with one function, and a reviewer may prefer it to live beside
   `CodeScene.from_clip` as a classmethod. Either is defensible; the private cross-layer import
   is not.
2. **Should the compare panel become a console grid region?** My answer: not while it
   duplicates the editor preview at full width. It compares images at two columns, which the
   400px dock cannot do. If it ever shrinks to a result list, it should be docked like
   `timeline` and `jobs`. Until then, gap 4 stands and the layout tests are right to ignore it.
3. **Expose `GET /api/v1/compare/checklist`?** My answer: yes. It would delete
   `COMPARE_MECHANICS` from the page and make the parity test unnecessary, because there
   would be one source. The cost is one route and one fetch on panel open. I did not add it in
   this phase because the phase was already two commits wide.
4. **Should `docs/compare-gate.md` be generated?** My answer: eventually, by the same script
   that renders the frames, so CI can diff it. Right now a generated record would need ffmpeg
   and the absent reel; hand-written is honest about that, generated would not be.
5. **Is the absent reel a licensing decision?** I cannot tell from the repository. If the reel
   can be shared, add `source.url` beside the sha256 and have the gate fetch and verify the
   hash before comparing; that turns item 1 from impossible into one command. If it cannot,
   the gate stays FAIL by design and that should be stated in `README.md`, not only in a
   phase record.
6. **Should `compare.frames` write the report?** My answer: no, not by default. An action that
   renders eight Chromium frames already has a cost; writing a file is a side effect a caller
   should ask for. A `write_report: bool = False` plus `output_path` is the shape I would add
   if a flag is wanted, matching the HTTP endpoint instead of duplicating it.

## Suggested next steps, in order

1. Click through the panel once (10 minutes) with `examples/omniframe-promo/project.json`;
   confirm the checklist paints five rows and the verdict repaints on a status change.
2. Move the frame helper out of `backend` (question 1) and delete the private import. It is
   the only structural debt this phase added.
3. Replace the hard-coded `20` in `tests/test_ui_server.py` with `len(registry.names())`.
4. Decide the fate of the numbers in `docs/compare-gate.md`: commit the generator, or remove
   them. Leaving unreproducible numbers in a document about honesty is the weakest option.
5. When a reel is shareable, close 7A item 1 for real: render the seven frames, extract the
   matching instants, attest each row, and let the gate pass only if the mechanics actually
   match. If they do not, that is the useful outcome and the record already has a place for
   it (`gap`, with the frame numbers).

## Where to pick this up

Read in this order: `tests/test_compare_gate.py` (the contract, as behaviour), then
`src/omniframe/engines/compositor/compare.py`, then the two routes in
`src/omniframe/backend/server.py`, then the compare block in `src/omniframe/ui/index.html`
between `editorParseFrameList` and `onEditorZoom`, then `tests/test_ui_compare_math.py`.

Run:

```powershell
$env:PYTHONPATH='src'
python -m pytest -q
python -m ruff check src tests
python -m omniframe.cli.main ui --port 8765
```

Then load `examples/omniframe-promo/project.json` in the editor and in Compare.

One thing to know before editing the checklist: the five ids are written in three code places,
not one - `CHECKLIST` in `compare.py`, `COMPARE_MECHANICS` in the page, and `MECHANICS` in
`tests/test_ui_compare_math.py`. The parity tests compare the first two; the third is a copy that
the same test could import instead. Adding a sixth mechanic means three edits today, and a test
that derives its list from the backend would make it one.
