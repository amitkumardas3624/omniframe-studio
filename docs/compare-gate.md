# Compare gate - motion reel template

Executed record of the `SKILL.md` section 7A reference-to-template verification loop,
run against `examples/motion-reel-template/`. Section 7A is the gate that must be
applied before an OmniFrame editor template may be declared done.

Verdict: **FAIL (not attested)**. Five of five mechanics are `pending`. The cause is
a missing input, not a missing implementation - see section 2. Nothing in this file
should be read as a claim that the template matches the reference reel.

## 1. What the gate requires

`src/omniframe/engines/compositor/compare.py` encodes the five 7A mechanics verbatim
as `CHECKLIST`. Each is a `ChecklistItem(id, label, status, note)` whose status starts
at `unchecked` and may be attested as only one of:

| status | meaning |
|---|---|
| `match` | the mechanic is reproduced, not a thin substitute |
| `gap` | the mechanic is missing or oversimplified - blocks the gate |
| `limit` | the mechanic cannot be pushed further because of an engine or physical limit - **must carry a note** |

`verdict()` passes only when no item is `unchecked`, no item is `gap`, and every
`limit` has a non-empty note. An unnamed engine limit is indistinguishable from a
silent gap, so it fails. Omitting a row cannot smuggle a pass: the function is
computed against `CHECKLIST`, not against the rows supplied.

The five items, in order:

| id | 7A concern |
|---|---|
| `background_shifts` | background shifts and kinetic type layers, not static text on a stuck background |
| `grid_density` | full density and motion of grids, arrays and patterns, not a few sparse outlines |
| `particle_construction` | particle-built typography and forms with colour transitions, not plain solid text |
| `3d_focal_objects` | 3D focal objects, spheres and morphs over perspective and spatial layers, not empty grids or flat rings |
| `outro_hierarchy` | multi-layered curves, waves and transitions with the full outro hierarchy, not stripped-down single lines |

## 2. The reference reel is declared but absent

7A item 1 asks for the same key frames extracted from *both* the original reference
video and the rendered output, inspected side by side. The template names the video
it was decompiled from, in `examples/motion-reel-template/blueprint.json`:

```json
"source": {
  "kind": "video",
  "ref": "video.eb2ddbff.mp4",
  "sha256": "eb2ddbff09563c739d8b9681ddc59dc366cc9c185ec02fad70fb391659ba9397",
  "duration_s": 15.0,
  "fps": 60,
  "size": [1920, 1080]
}
```

That file is not in this repository. `git ls-files "*.mp4"` returns nothing at all,
so no video is tracked anywhere in the tree, and the template directory tracks
exactly eight files - `README.md`, `blueprint.json`, `content.json`,
`content.facebook.json`, `render_template.py`, `scene.html`, `scene.js`,
`storyboard.md` - none of them media. A filesystem search for the recorded basename
also finds nothing.

This is a deliberate licensing and size posture, not an accident, but the
consequence for the gate is the same: **the side-by-side comparison 7A item 1
demands cannot be performed in this checkout.** Comparing output frames against a
reference that is not present is not a thing this gate may pretend to have done.

Because `match` cannot honestly be asserted without the reference, and because 7A
item 2 asks *whether the output reproduces the reference's actual visual behaviour*
rather than whether the template contains plausible code, all five items are left
`unchecked`. `verdict()` consequently reports `ok: false` with `pending: 5`.

The template does ship the next best primary source, and section 4 uses it:
`storyboard.md` states each chapter's visual intent and the palette values measured
from the reference frames, and `blueprint.json` carries the measured style probe
(easing, spring, stagger, camera, pacing, rhythm). Where this document interprets a
frame it says which of those it is interpreting against, because a recorded
specification is weaker evidence than the picture it describes.

## 3. What was executed in place of the comparison

Item 1 could not be run. Items 2 and 3 were, against the template instead of against
the reel, and this section records exactly what was done so the substitution is
visible rather than implied.

Seven frames were rendered, chosen so that every 7A mechanic has at least one frame
whose chapter actually implements it (chapter ranges from `storyboard.md`):

| frame | chapter | 7A concern it exercises |
|---|---|---|
| 60 | 00 INTRO | baseline: orange sphere, ticked baseline, mono subtitle |
| 180 | 01 KINETIC TYPE | `background_shifts` - off-white field, oversized blue word |
| 300 | 02 SYSTEMS | `grid_density` - concentric rounded squares, orbiting crosses |
| 400 | 03 PARTICLES | `particle_construction` - FLOW resolves into a dot cloud |
| 495 | 04 DIMENSION | `3d_focal_objects` - rotating sphere over perspective floor grid |
| 700 | 06 FLOW | `outro_hierarchy` - orange and blue spline ribbons |
| 840 | 07 OUTRO | `outro_hierarchy` - heavy logotype, orange period, status line |

Frame 60 is the control. It is the emptiest frame in the reel, so if any frame
is going to be guilty of the "static text on a stuck background" failure the item
warns about, it is that one.

Rendering route: `render_template.build_scene(content, duration_frames=1)` with
`window.__OMNIFRAME_FRAME__` and `window.__OMNIFRAME_TOTAL_FRAMES__ = 900` prepended to
the scene script, so the single rendered frame is the requested frame of the real
900-frame timeline, and `seek(t)` is the one doing the work. Backend `playwright`
(real Chromium), output 1920x1080. All seven: `ok: true`,
`verification_level: "render_tested"`, `issues: []`.

Measurement route: Pillow over each PNG downsampled to 480x270, so every percentage
below is an area share of the frame.

| name | definition |
|---|---|
| `bg` | modal colour of the frame |
| `ink` | share of pixels whose channel-sum distance from `bg` exceeds 12 |
| `warm` | share of pixels with `R - B > 40`; selects the orange accent `#FF5722` |
| `cool` | share of pixels with `B - R > 40`; selects the blue accent `#155EEF` |
| `colours` | distinct colours in the 480x270 sample |
| `edge` | mean luma of a `FIND_EDGES` pass, 0-255 |

## 4. Measurements

These rows are produced by code, not transcribed by hand: a script opens each PNG,
downsamples it to 480x270 and prints the numbers. Reported digits are therefore the
measurement, not a memory of it.

| frame | chapter | bg | ink % | warm % | cool % | colours | edge |
|---|---|---|---|---|---|---|---|
| 60 | 00 INTRO | 15,14,19 | 1.50 | 0.50 | 0.00 | 486 | 2.45 |
| 180 | 01 KINETIC TYPE | 240,236,226 | 10.37 | 0.00 | 3.50 | 850 | 9.72 |
| 300 | 02 SYSTEMS | 15,14,19 | 7.41 | 2.53 | 0.00 | 955 | 7.07 |
| 400 | 03 PARTICLES | 15,14,19 | 2.61 | 0.06 | 0.00 | 570 | 4.04 |
| 495 | 04 DIMENSION | 15,14,19 | 5.05 | 0.00 | 0.30 | 714 | 3.93 |
| 700 | 06 FLOW | 15,14,19 | 12.43 | 0.17 | 0.61 | 2161 | 8.57 |
| 840 | 07 OUTRO | 15,14,19 | 6.49 | 0.01 | 0.00 | 813 | 5.14 |

Three checks make the table trustworthy before any mechanic is read off it.

**The declared palette reproduces.** `blueprint.json` gives the dark base as
`#0B0A0F` = (11,10,15) and the light base as `#F1EDE3` = (241,237,227). Six of the
seven frames put their modal colour at (15,14,19): a lift of +4 on every channel,
which is what compositing the static grain over a flat field does. Frame 180 puts it
at (240,236,226), within one unit per channel of the declared light base - no lift,
because that chapter paints the cream as page rather than as ink.

**The accent tests are selective by construction.** Orange `#FF5722` = (255,87,34)
has R - B = +221 and blue `#155EEF` = (21,94,239) has R - B = -218, while the
neutral ramp is flat: foreground +14, muted -14, dark base -4. A threshold of 40 sits
between the largest neutral separation (14) and the smallest accent separation (218),
with margin on both sides, so `warm` and `cool` cannot be firing on anti-aliased
neutral edges.

**The frames are not one frame.** Ink runs 1.50 to 12.43, colours 486 to 2161, edge
2.45 to 9.72. Had `duration_frames=1` broken `seek(t)` and every render returned the
same initial state, these seven rows would be identical. They are not.

## 5. The five mechanics, read against the numbers

Each row states what the storyboard claims, what the pixels show, and - the column that
decides the status - what a still frame cannot show. Every status stays `unchecked`.

**`background_shifts` - frames 60 and 180.** Claimed: ch00 is the dark entry on `#0B0A0F`,
ch01 an off-white field carrying an oversized blue word plus outlined ghost rows.
Measured: the modal colour flips (15,14,19) -> (240,236,226); blue coverage goes 0.00 % ->
3.50 % while orange stays 0.00 %; edge energy goes 2.45 -> 9.72, the highest of the seven.
Not shown: that the background *shifts* - a transition needs consecutive frames - or that
the type is *kinetic*, which is motion rather than position. Both halves are temporal, so
one still cannot carry them however clean its numbers are.

**`grid_density` - frame 300.** Claimed: concentric rounded squares rippling outward with
cross marks orbiting them. Measured: ink 7.41 %, 955 colours, edge 7.07, and orange at
2.53 % - a third of all non-background area is accent colour, so the accent is distributed
across the structure rather than pooled in one shape. Not shown: that the marks form a grid
or array at all, its periodicity, its element count, or that any element moves. High edge
energy at moderate ink does rule out the failure the item names - a few sparse outlines
would meter low on both - but a scattered field of small unrelated marks meters the same.

**`particle_construction` - frame 400.** Claimed: the word FLOW resolves into a
deterministic dot cloud that is the sphere population under a second projection. Measured:
ink 2.61 %, 570 colours, edge 4.04, orange 0.06 %, blue 0.00 % - sparse, near-neutral marks.
Not shown: that the marks are *dots*, how many there are, or that they compose a glyph. A
solid display word at a transitional opacity would leave a comparable non-modal residue,
and the dot-vs-glyph distinction lives at the dot-count and dot-position level that no
coverage statistic reaches. This is the weakest row of the five and it is not attestation.

**`3d_focal_objects` - frame 495.** Claimed: the dot cloud lifts into a rotating sphere over
a perspective floor grid, the one chapter with a perspective projection (68 deg -> 63 deg).
Measured: ink 5.05 % at edge 3.93, the lowest edge energy among the loaded frames, plus blue
0.30 % and no orange. Not shown: *rotation*, or *perspective*. Both are properties of a
sequence - recovering them needs at least two frames and tracked features between them - and
an orthographic still of a sphere over a grid is indistinguishable by these statistics from a
genuinely projected one. Perspective is the single mechanic here that cannot be inferred from
coverage at any resolution, so the number is reported and not leaned on.

**`outro_hierarchy` - frames 700 and 840.** Claimed: ch06 carries orange and blue spline
ribbons with the serif lines `everything` and `moves.`; ch07 is a heavy logotype with an orange
period and an entering status line, and the orange period *is* the sphere. Measured: 700 holds
the highest ink of the set (12.43 %) and by far the most distinct colours (2161, 2.3 times the
next frame), with both accent families present at once (orange 0.17 %, blue 0.61 %); 840
collapses to 813 colours and 6.49 % ink with orange at 0.01 %, which is roughly 13 pixels of
the 480x270 sample - the size a period glyph would have, and not the size a ball would have.
Not shown: hierarchy, which is a rank ordering of elements and not an area. A collapse from
2161 colours to 813 has the shape a switch from a layered field to a flat logotype composition
would have, but shape is inference. An orange count of 0.01 % is equally consistent with the
declared period, with remnant anti-aliasing from an earlier sphere, or with a clipped decal.

Taken together: the source demonstrably implements all five - `scene.js` carries one builder
per chapter (`intro`, `kinetic`, `systems`, `particles`, `dimension`, `data`, `flow`, `outro`),
creates every node inside `bootstrap`, and has `seek(t)` write attributes only - while the
renders measure consistent with each. Implementation present plus output consistent is not
the thing 7A asks for either. It asks whether the output reproduces the reference, and that
question remains unanswered until the reel is in hand, which is why it is not quoted in
mitigation here.

## 6. Engine limits

`storyboard.md` carries the template's own list under the heading Not expressible in this
build. These are the answers available when a mechanic must be attested `limit` rather
than `match`:

- **Native audio.** The template carries no audio track and adds none. The instruction is
  to attach the reel audio through the project audio path after the frames are rendered,
  never to fake it with CSS, a timer or a frame loop.
- **Pixel-exact type.** No font files are bundled. The template approximates with system
  Arial, Georgia and Courier. Closing this means loading real webfonts in `bootstrap` and
  gating the first frame on `document.fonts.ready`. Until then glyph shape and advance
  width are approximations, and no pixel diff against the reel can be expected to reach
  zero on a text frame.
- **Film grain.** The reel bitmap grain is approximated by a deterministic SVG turbulence
  filter, not sampled per frame. Grain therefore matches in character and not in value.
  The uniform +4 lift measured in section 4 is this filter, and any pixel-diff threshold
  must be loose enough to absorb it.

Distinct from those limits, the storyboard fixes invariants that anything closing this
gate must keep: palette roles, the four-corner bracket HUD at a 5 percent safe margin, the
chapter clock, the easing set, no CSS animation, no `requestAnimationFrame`, no timer, no
unseeded randomness, every node created in `bootstrap`, `seek(t)` writing attributes only,
and a grain filter with a fixed seed. A re-skin may edit `content.json` and the palette
variables and nothing else. One of these invariants doubles as a capability: because all
motion is authored as a function of `t`, any frame is addressable on its own, with no
playhead to reach first - which is what makes this gate cheap enough to run at all.

Limits of the gate itself, so that a pass is not over-read:

- One still per mechanic can attest presence and rough density. It cannot attest motion,
  layering or construction, and items 1, 2, 4 and 5 are half temporal by construction.
- A video reference cannot be sampled without ffmpeg on PATH. `extract_reference_frame`
  raises `EngineUnavailable` (`E_ENGINE_UNAVAILABLE`) rather than guessing a frame.
  `reference_frames_dir` is the ffmpeg-free path, and it is why a hand-made contact sheet
  is enough to close the gate.
- Pixel diffs need Pillow. Without it `mean_abs_diff` returns `None` and the report prints
  `n/a` instead of a number: the gate then records structure and never invents a diff.
- Frames are mapped by instant, not by index - 10 at 30 fps is 20 at 60 fps - because
  integer indices across different rates compare different moments.

## 7. Verdict, and what would change it

`verdict` over these rows returns `ok: false`, `pending: 5`, `gaps: []`,
`limits_without_note: []`. Nothing is attested. The gate withholds the pass rather than
ranking a guess.

It can clear two ways:

- **With the reel.** Render the seven frames above, sample the same instants from the
  reference, and pair them. Sampling maps by instant, so a 60 fps reel lines up frame for
  frame, and a reel at any other rate lines up in time without a resampling decision to
  defend.
- **With a contact sheet.** Export those instants by hand to PNGs named `frame_%05d.png`,
  `%05d.png`, `frame_%d.png`, `%d.png`, or merely in positional order in a sorted listing,
  and pass the directory as `reference_frames_dir`. No ffmpeg needed.

Either way every row must then move to `match`, or to `limit` **with a note that names the
limit**. A `limit` row without a note fails, on the reading of 7A item 3 that an unnamed
engine limit is indistinguishable from a silent gap. Re-running the gate is the only thing
that changes the verdict: this document records why it currently reads FAIL, and it is not
itself evidence of a pass.

## 8. Reproducing this record

Module API:

```python
from omniframe.engines.compositor.compare import build_compare, render_report_markdown

report = build_compare(
    [60, 180, 300, 400, 495, 700, 840],
    render_frame=render,                    # callable frame -> image or path
    project_path="examples/motion-reel-template",
    project_fps=60,
    total_frames=900,
    reference_video="reels/motion-reel.mp4",  # optional
    reference_frames_dir=None,               # optional, ffmpeg-free
    backend="playwright",
)
print(render_report_markdown(report))
```

Over HTTP, from the Studio UI or any client:

```
POST /api/v1/compare/frames
{"project_path": "examples/motion-reel-template",
 "frames": [60, 180, 300, 400, 495, 700, 840],
 "reference_video": "reels/motion-reel.mp4", "backend": "playwright"}

POST /api/v1/compare/report
{"project_path": "examples/motion-reel-template",
 "compare": <the result above>,
 "output_path": "docs/motion-reel-compare.md"}
```

## 9. Verification ledger

- **generated**: `compare.py`, the two endpoints, `tests/test_compare_gate.py`, this document,
  and the Phase 5 note appended to the editor spec.
- **import_tested**: the module imports and wires into `server.py`; `ruff check src tests`
  passes across the repository. The endpoints call the renderer through `asyncio.to_thread`,
  so a Chromium render cannot block the event loop.
- **structurally_checked**: 22 tests in `tests/test_compare_gate.py` - checklist identity and
  start state, frame-list parsing and its rejections (empty string, blanks, `abc`, `1,,2`),
  out-of-range rejection, instant mapping across 30 and 60 fps, every verdict branch
  (unattested row, attestation without gaps, note-less limit, gap), report text, both endpoints,
  the no-reference case, and the report path.
- **render_tested**: the seven frames in section 4 - 1920x1080, `ok: true`, `issues: []`,
  through Playwright Chromium, with the frame and total-frame overrides applied so `seek(t)`
  produced each requested instant.
- **not tested, not claimed**: equality with the reference reel, which is absent; motion,
  transitions or layering, which one still per mechanic cannot show; the render-compare path
  end to end against a real reel; and the Studio UI Compare panel, which is not part of this
  change.
- **not claimed**: that the editor is done. By the opening of 7A - decompiling into JSON,
  passing lint and rendering a frame sequence prove only that the pipeline runs - the pass
  this document would need to grant has not been earned, so it reports FAIL.
