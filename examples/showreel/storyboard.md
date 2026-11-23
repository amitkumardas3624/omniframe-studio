# OmniFrame Studio — 15s Motion Showreel

## Concept

**One seed becomes a spiral, the spiral becomes a ring, the ring becomes type, the type becomes a
grid, the grid becomes a city, the city becomes an interface, and the interface hands the piece
back to the seed it came from.**

Every shot is made out of the previous one. There is one object in this film — a field of 65
square cells — and it never gets replaced, cut to, or faded in from elsewhere:

| The cells are… | …and they become |
|---|---|
| 16 squares in a ring | the letter **O** |
| 65 squares | the wordmark **OMNI** |
| 65 squares | a **13 x 5 grid** (16 + 17 + 17 + 15 = 65) |
| 65 squares | **65 blocks** standing on a floor |
| 65 squares | **UI panels**, a timeline, a waveform, a layer list |
| 32 of them | the **frame** around the end title |

The final frame is the first frame: a single 8px dot at the centre of the screen. The title
collapses into it, so the film loops without a seam.

## Rules the piece holds itself to

- **One typeface.** Archivo Black (Google Fonts), embedded in the HTML as base64 so the render is
  byte-identical everywhere. No second family, no weights other than the one.
- **Three colours plus black and white.** Ink `#F5F2EA`, vermilion `#FF4B26`, cobalt `#2F4BFF`,
  sand `#C9C2B4`, on black `#0C0C0D`. Every 3D face is the accent colour at a different opacity
  over black — same hue, flat, no gradients.
- **One camera language.** Slow eased pushes and pulls, never a cut. The camera pulls back as the
  floor tilts, so the city stays inside the frame.
- **Nothing decorative.** No particles, glows, flares, camera shake, RGB split, crossfades,
  bouncy easing, or holds longer than half a second.
- **Everything is a function of time.** `window.seek(t)` redraws the whole frame from `t`. No CSS
  animation, no timers, no state carried between frames.

## Beat sheet — 120 BPM, one beat = 0.5s, 30 beats

| Beat | Time | What happens |
|---|---|---|
| 1 | 0.00 | The seed: one 8px ink dot at the centre of black. |
| 2 | 0.50 | The dot draws a spiral — one full turn, opening outward to r=200. |
| 3 | 1.00 | The spiral's stroke resolves into 16 square cells arranged in a ring. |
| 4 | 1.50 | The ring rearranges into the letter **O** (pixel 5x7). |
| 5 | 2.00 | **M** flies in from the right and lands with a spring overshoot. |
| 6 | 2.50 | **N** lands, **I** lands — the wordmark **OMNI** is complete at 2.2s and holds. |
| 7 | 3.00 | The letters break: every cell leaves its letter position and finds a grid slot (staggered by column). |
| 8 | 3.50 | The 13 x 5 grid is assembled as a wireframe. A cobalt wave crosses it, one column at a time. |
| 9 | 4.00 | The wave runs back. The camera starts a slow push. |
| 10 | 4.50 | Wave again. The grid grows 5.5% — the camera push. |
| 11 | 5.00 | Last wave pass. |
| 12 | 5.50 | The floor tips: the grid becomes a floor plane and the cells begin to stand up. |
| 13 | 6.00 | The city extrudes. The camera has pulled back; the floor is at 46 degrees. |
| 14 | 6.50 | Yaw begins; the blocks' side faces come into view. |
| 15 | 7.00 | The camera pushes in 250 units. The skyline wave travels along the columns. |
| 16 | 7.50 | Full yaw to the right; the far columns compress in perspective. |
| 17 | 8.00 | The camera starts pulling back; the floor begins to level out. |
| 18 | 8.50 | The city flattens toward the screen. |
| 19 | 9.00 | The blocks lie down and become UI: 13 thumbnails, 13 timeline cells, 13 bars, 26 layer cells. |
| 20 | 9.50 | The timecode types in character by character; the labels appear. |
| 21 | 10.00 | The red playhead sweeps across the timeline and stops at 10.6s. |
| 22 | 10.50 | The frame counter and the progress rule fill. |
| 23 | 11.00 | The interface dissolves: every cell converges on the frame positions. |
| 24 | 11.50 | The 32 perimeter cells form the frame; the other 33 shrink away. |
| 25 | 12.00 | **OMNIFRAME** — the letters arrive one at a time on a spring, rising into place. |
| 26 | 12.50 | **STUDIO** is wiped in below it, letter-spaced. The vermilion rule draws. |
| 27 | 13.00 | The footer line types in. The frame starts to open outward. |
| 28 | 13.50 | The accent sweep crosses the wordmark. The frame has opened to its widest. |
| 29 | 14.00 | The strongest moment: the whole title card is clean and centred. |
| 30 | 14.50 | Everything contracts to the centre and the seed dot is back. Frame 900 = frame 0. |

## Sound — Web Audio API, rendered offline

Built in the scene's own `window.renderSoundtrack()` with an `OfflineAudioContext` at 48 kHz
stereo, then handed to the platform's compositor for the mux. No audio files.

- **Kick on every beat** (30 of them): a 148 Hz sine falling to 46 Hz over 110 ms, plus a
  high-passed noise click for the transient.
- **A scene hit on every section change** (0s, 3s, 6s, 9s, 12s): a 210 Hz triangle dropping to
  58 Hz with a band-passed noise sweep, so every cut in the picture has a sound.
- **A riser into the last full bar** (12.0s → 14.0s): band-passed noise sweeping 340 Hz → 6.2 kHz
  under a sawtooth climbing 180 Hz → 940 Hz.
- **A reverse swell** into the 14.0s downbeat, then the hit and kick that carry the end title.
- **Bass** two notes per bar (A1, A1, D2, C2), triangle wave, 0.82s each.
- **Hats** on the off-beats, alternating levels, to keep the grid audible.
- Everything is summed through a compressor and normalised to 0.92 peak.

## Build — all of it through the platform

`build_showreel.py` uses the platform's own engines:

1. `omniframe.engines.code_video` renders the scene in headless Chromium through Playwright, one
   PNG per frame. The beat pass renders 30 frames at 2 fps (one per beat) for inspection; the
   full pass renders **2700 frames at 180 fps** — three subframes for every output frame.
2. `omniframe.engines.compositor.ffmpeg.build_video_from_frames` blends the subframes with
   `tmix=frames=3:weights='1 2 1'`, keeps every third blended frame and rewrites the timestamps
   to a 60 fps grid: motion blur with the centre subframe weighted double.
3. `omniframe.engines.compositor.compositor.Compositor.mux_audio` muxes the Web Audio WAV onto
   the H.264 video.

```powershell
python examples/showreel/build_showreel.py --stage beats   # 30 beat frames + contact sheet
python examples/showreel/build_showreel.py --stage full    # the delivery
```

The scene file is standalone: open `showreel.html?play` in a browser to watch it live.
