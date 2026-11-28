# Kinetic intro template

A 15.5 s kinetic-type title card, decompiled from a reference reel and rebuilt
as a template: the reel is the analysis input, the template is our own scene
code and our own copy.

## What it reproduces

- 1280x720, 24 fps, 373 frames, deterministic: one pure `seek(t)`, no timers, no
  `requestAnimationFrame`, no unseeded randomness.
- The reference structure: a three word stack that arrives line by line with a
  motion blur on the entering line, a script "with", a tag above it, a vertical
  tag with a stacked lead, a disc, a cropped ring, a yellow wash, the
  INTRO/OUTRO stack, a white badge, the contact card and the black end card.
- The measured palette: `#FABB0F` yellow, `#050505` ink, `#FAFAFA` paper with the
  reference radial glow.

## How to use it

```powershell
python examples/kinetic-intro/render_template.py --out out/kinetic-intro --backend playwright
python examples/kinetic-intro/render_template.py --verify   # renders twice, compares bytes
```

Edit `content.json` for a new brief. `scene.html` holds the markup and the
palette; `scene.js` holds the single pure `seek(t)`. The reference frames the
analysis used are not vendored here.

## Known limits

- **Type fidelity.** The reference sets a heavy condensed grotesk; no font files
  are bundled, so the template uses the system stack (Arial Black / Archivo
  Black / Impact). Weight, width and tracking therefore differ, and the
  measured pixel gap at the type frames is dominated by that difference.
- **The glow.** The reference backdrop is a soft radial field with a slightly
  noisy edge; the template uses a clean CSS radial gradient.
- **Geometry of the ring.** The reference ring is cropped by the frame; the
  template ring is a circle with a fixed crop.
