# Motion reel template — storyboard

15 s at 60 fps, 1920x1080, 900 frames, 128.57 BPM grid (beat = 28 frames).
All motion is evaluated from `t = frame / fps` inside one pure `window.seek(t)`.

| Ch | Frames | Seconds | Visual | Continuity device |
|---|---|---|---|---|
| 00 | 000-119 | 0.0-2.0 | Orange sphere drops onto a ticked baseline and settles; mono subtitle enters | The sphere is the through-line object |
| 01 | 120-239 | 2.0-4.0 | Off-white field, oversized blue word cycles SPACING / EASING / RHYTHM, outlined ghost rows | Word scale is a match on the sphere's landing scale |
| 02 | 240-359 | 4.0-6.0 | Concentric rounded squares ripple outward, cross marks orbit | Ripple origin inherits the centre anchor |
| 03 | 360-449 | 6.0-7.5 | Word FLOW resolves into a deterministic dot cloud | Dots are the sphere's particles |
| 04 | 450-539 | 7.5-9.0 | Dot cloud lifts into a rotating sphere over a perspective floor grid | Same dot instances, new projection |
| 05 | 540-659 | 9.0-11.0 | Light dashboard: counters, orange bars, blue ring, LIVE pill | Vertical mask wipe, counters inherit 1/16 beat |
| 06 | 660-779 | 11.0-13.0 | Orange and blue spline ribbons; serif lines `everything` / `moves.` | Ribbons inherit the grid horizon |
| 07 | 780-899 | 13.0-15.0 | Heavy logotype with orange period; status line enters | The orange period is the sphere |

## Fixed rules (do not change for a re-skin)

- Palette roles: dark base, light base, foreground, muted, one orange accent, one blue accent.
  Measured from the reference frames: `#0B0A0F`, `#F1EDE3`, `#8A8F98`, `#FF5722`, `#155EEF`.
- Persistent four-corner bracket HUD, 5% safe margin, mono technical labels in all four corners.
- Chapter clock: 8 chapters on the exact frame starts above. Camera is orthographic 2D except
  chapter 04, which uses a single perspective projection (68 deg -> 63 deg).
- Easing: `outExpo` for entrances, damped sine for the sphere, `clamp` for holds.
- No CSS animation, no `requestAnimationFrame`, no timer, no unseeded randomness. Every node is
  created in `bootstrap`; `seek(t)` only writes attributes.
- Grain is a static SVG turbulence filter with a fixed seed, not a per-frame random overlay.

## Variable inputs (edit `content.json`, never `scene.html` or `scene.js`)

- `brand`, `reel`, `status` — identity copy.
- `words` — three pipe-separated kinetic words (chapter 01).
- `principle`, `note`, `particleWord`, `flowTop`, `flowBottom` — chapter copy.
- `panelTitle`, `m1`/`m1Label`, `m2`/`m2Label`, `m3`/`m3Label`, `ringValue` — dashboard data.
- Palette variables (`accent`, `blue`, `bgDark`, `bgLight`, `fgDark`, `muted`) are declared in
  `scene.html` and may be overridden in `content.json`, but are style rules by default.

## Not expressible in this build

- The reference's native audio track is not part of the template. Add it with the project's
  audio path after rendering the frames; do not fake it with CSS or timers.
- Exact font files are not bundled. The template uses system approximations (Arial, Georgia,
  Courier); load real webfonts in `bootstrap` and gate on `document.fonts.ready` if pixel-exact
  typography is required.
- The reference's bitmap film grain is approximated by a deterministic SVG turbulence filter.
