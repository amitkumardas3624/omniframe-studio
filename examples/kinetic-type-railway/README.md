# Kinetic type railway template

A 20 s single-word sequence, decompiled from a reference reel and rebuilt as a
template: the reel is the analysis input, the template is our own scene code
and our own copy.

## What it reproduces

- 1280x720, 25 fps, 501 frames, deterministic: one pure `seek(t)`, no timers,
  no `requestAnimationFrame`, no unseeded randomness.
- The reference structure: twenty one-word cards that arrive one after the
  other, the stacked railway name, the underline strokes, the radiating rays,
  the brush arcs, the pink splatter, and the logo lockup with its tagline.
- The measured palette: `#00BD6D` green, `#004A44` ink, `#F6C8D6` pink,
  `#FFFFFF` for the strokes and the mark.
- The dotted halftone fill on the railway name and the word before the ending,
  reproduced with a radial-gradient clipped to the text.

## How to use it

```powershell
python examples/kinetic-type-railway/render_template.py --out out/kinetic-type-railway --backend playwright
python examples/kinetic-type-railway/render_template.py --verify
```

## Known limits

- **Type fidelity.** The reference sets a heavy condensed grotesk; no font
  files are bundled, so the template uses the system stack (Arial Black /
  Archivo Black / Impact). The measured gap at the type frames is dominated
  by that difference.
- **Per-card sizing.** The reference sets each card to its own optical size;
  the template approximates them from the sampled frames.
- **The brush marks.** The reference brush strokes are hand drawn; the
  template uses generated SVG arcs and splats.
