# Seek-adapter example

A minimal, renderable demonstration of the two optional `code_video` helpers:

- `data-composition-variables` declares template defaults (`title`, `accent`);
  `scene.params.title = "SEEK"` overrides the declared `TEMPLATE` default.
  The resolved variables are applied to `[data-var]` nodes and published as CSS
  custom properties, so layout code needs no template-specific branching.
- `data-track="intro" data-start="0.5" data-duration="1"` declares a timing
  window. The scene registers a GSAP-style timeline in `bootstrap` with
  `{ kind: 'gsap', track: 'intro' }` and scrubs it from `seek(t)` via
  `window.__omniframe_seek_adapter.seek(t, frame)`.

The timeline used here is a three-line fake object, so the example runs with no
third-party library and no network access. A real GSAP timeline, Lottie instance
or Three.js scene can be registered the same way.

## Render

```powershell
omniframe project validate examples/seek-adapter/project.json
omniframe project render examples/seek-adapter/project.json --out out/seek-adapter
omniframe inspect frames --directory out/seek-adapter --output out/seek-adapter-sheet.png --columns 4
```

At 10 fps, 20 frames: before `t = 0.5` the adapter holds local time at `0`;
between `0.5` and `1.5` it scrubs `0 -> 1`; after `1.5` it holds at `1`.
Because every value is derived from `frame / fps`, rendering the scene twice
produces byte-identical frames. The fake driver has no render loop, no
`requestAnimationFrame`, no timers and no unseeded randomness.
