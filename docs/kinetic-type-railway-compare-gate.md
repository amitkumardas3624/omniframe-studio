# Compare gate - kinetic type railway template against its reference

Date: 2026-11-28. The second template measured against a reference that
actually exists.

## The comparison

- Reference: a 20.04 s, 1280x720, 25 fps kinetic-type reel, downloaded for
  analysis only. No frame of the reference is vendored into this repository.
- Output: `examples/kinetic-type-railway`, 501 frames at 25 fps,
  `render_tested` through Playwright Chromium, `issues: []`.
- Sampled instants: 14 frames across the 20 s, each compared against the
  reference frame at the same instant.

## The measured gap (mean absolute RGBA difference, 0 to 255)

| frame | instant | first pass | second pass |
|---|---|---|---|
| 12 | 0.5 s | 119.40 | 4.22 |
| 37 | 1.5 s | 126.65 | 15.47 |
| 62 | 2.5 s | 118.49 | 3.21 |
| 87 | 3.5 s | 118.64 | 3.58 |
| 112 | 4.5 s | 113.34 | 7.59 |
| 137 | 5.5 s | 113.68 | 4.91 |
| 212 | 8.5 s | 117.15 | 1.95 |
| 262 | 10.5 s | 119.70 | 4.63 |
| 312 | 12.5 s | 111.05 | 11.06 |
| 337 | 13.5 s | 119.32 | 8.95 |
| 387 | 15.5 s | 118.30 | 2.80 |
| 437 | 17.5 s | 118.11 | 3.05 |
| 462 | 18.5 s | 112.86 | 6.04 |
| 487 | 19.5 s | 113.41 | 7.69 |

The first pass was wrong in one specific, diagnosable way: the scene ran on a
white background. The renderer base stylesheet wins over the scene stylesheet,
so the background has to be declared on the scene itself, and the harness was
reading the wrong key. Fixing that key moved every frame by more than a hundred
points of difference.

The second pass fixed the two layout faults the side-by-side sheet showed:
the word sat at the top of the stage instead of the middle, and the type was
about 45 percent too small.

## What the checklist says for this reference

| mechanic | status | note |
|---|---|---|
| `background_shifts` | match | one flat field for the whole reel, and the field matches the reference exactly |
| `grid_density` | match | the reference carries no grid; none is invented here |
| `particle_construction` | match | the reference carries no particles; none is invented here |
| `3d_focal_objects` | match | the reference is flat 2D type; no perspective is invented here |
| `outro_hierarchy` | match | the logo lockup and its tagline close the reel in the same order |

## Residual gaps, in order of size

1. **Type face and weight.** The single largest term on every type frame. The
   system stack stands in for the reference condensed grotesk.
2. **The 1.5 s frame** (15.47) and the 12.5 s frame (11.06): the stacked
   railway name and the splatter card are the least faithful frames.
3. **Per-card optical size.** The reference sizes each card by eye; the
   template approximates from the sampled frames.
4. **The brush marks** are generated arcs, not the reference hand strokes.
