# Motion-reel template

A reusable style template decompiled from the reference 15 s motion reel. It keeps the
reference's **grammar** (HUD frame, palette roles, chapter clock, orange continuity sphere,
beat grid, grain) while making every piece of **content** a parameter.

`blueprint.json` records the measured style contract. `storyboard.md` lists the eight chapters
and separates fixed rules from variable inputs. `content.json` is the only file a new brief
should edit.

## Files

| File | Role |
|---|---|
| `blueprint.json` | `omniframe.blueprint/1` decompilation, grounded in ffprobe + sampled frames + video Q&A |
| `storyboard.md` | chapter frame map, fixed rules, variable inputs, known non-expressible traits |
| `scene.html` | markup, CSS and the `data-composition-variables` / `data-track` declarations |
| `scene.js` | `// === BOOTSTRAP ===` (create nodes) then `// === FRAME ===` (pure `seek(t)`) |
| `content.json` | the brief: brand, copy, kinetic words, dashboard numbers |
| `render_template.py` | driver: build a `CodeScene`, render, and optionally verify determinism |

## Render

```powershell
python examples/motion-reel-template/render_template.py --out out/motion-reel
python examples/motion-reel-template/render_template.py --verify --backend playwright
```

`--verify` renders four frames twice through a real backend and asserts byte-identical PNGs.
The default full render is 900 frames at 1920x1080/60 fps; use `--frames 30` for a quick check.

Inspect the result with the project's own gate before committing to a full render:

```powershell
omniframe inspect frames --directory out/motion-reel --output out/motion-reel-sheet.png --columns 4
```

## How the parameters reach the scene

`scene.html` declares defaults on its root element with `data-composition-variables`.
`content.json` is passed as `CodeScene.params`, which overrides those defaults. The
`code_video` composition runtime publishes them as `window.__OMNIFRAME_COMPOSITION__`, binds
every `[data-var]` node, and exposes `window.__omniframe_track_local_time(id, t)`. Each chapter
is declared with `data-track` / `data-start` / `data-duration`, so `seek(t)` reads timing from
the template instead of hard-coding it.

No line in `scene.js` reads a clock or draws a random value. The sphere, ripples, particles,
bars and ribbons are all closed-form functions of the local chapter time.

## Re-skin checklist

1. Copy this directory.
2. Edit `content.json` only.
3. Render `--frames 30`, inspect the contact sheet, fix contrast or overflow in `scene.html` CSS.
4. Run `--verify`, then the full render.
5. Add audio through the project's audio path; the template renders frames only.
