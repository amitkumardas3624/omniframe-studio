# Compare gate - kinetic intro template against its reference

Date: 2026-11-28. This is the first time the 7A gate ran against a reference
that actually exists, so it is also the first real measurement of the gate
rather than a record of a substitute.

## The comparison

- Reference: a 15.557 s, 1280x720, 23.976 fps kinetic-type reel, downloaded for
  analysis only. The template is our own scene code and copy; no frame of the
  reference is vendored into this repository.
- Output: `examples/kinetic-intro`, 373 frames at 24 fps, `render_tested` through
  Playwright Chromium, `issues: []`.
- Sampled instants: frames 24, 72, 120, 168, 216, 264, 312 and 360 (1 s to 15 s),
  each compared against the reference frame at the same instant (the gate maps
  by time, so the 23.976 fps reference and the 24 fps output line up).

## The measured gap (mean absolute RGBA difference, 0 to 255)

| frame | instant | first pass | second pass |
|---|---|---|---|
| 24 | 1 s | - | 18.17 |
| 72 | 3 s | - | 16.52 |
| 120 | 5 s | - | 30.26 |
| 168 | 7 s | - | 31.57 |
| 216 | 9 s | - | 13.08 |
| 264 | 11 s | - | 18.83 |
| 312 | 13 s | 3.79 | 4.57 |
| 360 | 15 s | 110.68 | 9.08 |

The second pass fixed four real gaps the first pass had: the script word was
black instead of yellow, every chapter ran one to two seconds early, the lead
type survived inside the ring, and the end card arrived while the reference was
still on the contact card. The end frame moved from 110.68 to 9.08 because of
those two timing errors.

## What the checklist says for this reference

| mechanic | status | note |
|---|---|---|
| `background_shifts` | limit | the reference backdrop is a soft radial field with a noisy edge; a CSS radial gradient cannot reproduce that edge |
| `grid_density` | match | the reference carries no grid or array; none is invented here |
| `particle_construction` | match | the reference carries no particles; none is invented here |
| `3d_focal_objects` | match | the reference is flat 2D type; no perspective is invented here |
| `outro_hierarchy` | match | the contact card, the site line and the black end card are all reproduced in order |

## The finding that matters more than the numbers

This reference is mostly **typography**, and the five mechanics of 7A do not
measure typography at all. Nothing in the checklist asks whether the face, the
weight, the tracking or the stack rhythm match. The measured gap at the type
frames (30.26 and 31.57, the two worst) is almost entirely that difference,
and the checklist reports those frames as fine.

So the honest reading is: the gate works, it is measurable, and for this
reference it is measuring the wrong thing. A kinetic-type reference needs a
sixth mechanic - type fidelity: face, weight, tracking, stack rhythm - or the
gate will pass a template whose lettering is visibly not the same.

## Residual gaps, in order of size

1. **Type face.** No font files are bundled, so the heavy condensed grotesk is
   approximated by the system stack. This is the dominant term in the diff at
   every frame that carries a headline.
2. **Ring crop and the vertical tag.** The reference ring and the rotated tag
   sit at a slightly different radius and weight.
3. **Glow edge.** The reference backdrop has a soft noisy edge.
4. **The entering-word blur.** Reproduced as a CSS blur on the entering line; the
   reference uses a directional smear that a scalar blur cannot match exactly.

None of these are gaps in the machinery: they are gaps in what this engine can
express, and they are named rather than averaged away.
