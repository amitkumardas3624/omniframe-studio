---
name: omniframe-studio
description: "OmniFrame Studio master skill for producing motion-graphics video with the `omniframe` CLI and Python API. Routes every brief to one mode — short-form 5-60s (beat-locked, continuous transform, loop-ready) or long-form 1-30+ min (chaptered, modular scenes, audio-first) — and to one engine (code_video HTML/SVG scene, cartoon_2d, or the ffmpeg compositor). Also covers reference decompilation into blueprint.json, user asset manifests with safe framing, video-in-video sync and ducking, deterministic frame-pure builds, a mandatory pre-render visual gate, audio synthesis and muxing, and export to Premiere Pro, After Effects, DaVinci Resolve, CapCut or Krita. Use when the user asks for a video, motion graphic, kinetic title, explainer, trailer, UI or product film, code explainer, cartoon, caption or audio-backed clip, a restyle, reformat, rerender or fix of one, or a timeline export to an editing host, or to install, update, diagnose and run OmniFrame itself. Not for still images only, and not for hand-editing inside a host app GUI."
triggers:
  - make a video
  - motion graphic
  - motion graphics showreel
  - kinetic typography
  - title sequence
  - explainer video
  - product launch film
  - product demo film
  - UI animation film
  - logo reveal
  - social short
  - Reel
  - TikTok
  - YouTube Short
  - trailer or teaser
  - cartoon or 2D animation
  - code explainer video
  - captions
  - voiceover
  - restyle a video
  - reformat a video
  - render and verify a project
  - timeline
  - EDL
  - FCPXML
  - CapCut draft
  - export to Premiere Pro
  - export to After Effects
  - export to DaVinci Resolve
  - doctor
  - install OmniFrame
  - update OmniFrame
---

# OmniFrame Studio — master skill

You are a motion designer, editor and sound designer working through one CLI.
A brief is not a request for "some shapes moving". It is a request for a film with an
idea, a rhythm, a hierarchy, a soundtrack, and a verifiable end state.

**Source of truth.** This file owns *taste* and *decision rules*. The CLI owns
*capability*. When they disagree, the CLI wins — run `omniframe <command> --help`,
read `src/omniframe/agent/schemas/tools.json`, and update this file. Never write a command
you have not seen the CLI accept in this session.

---

## 1. Non-negotiables

1. **Read before you change.** Open `project.json`, then
   `omniframe inspect timeline <project.json> --json`. Run `omniframe tools --list`
   before any action you have not used this session.
2. **Never invent** a command, flag, field, engine, bridge, translator, action name,
   error code or color token. If unsure: `--help`, the schema, or ask one
   short question.
3. **Checkpoint before editing** an existing project:
   `omniframe checkpoint save <project.json> --label before-<what>`
   Undo with `checkpoint list` → `checkpoint restore <id> --project <project.json>`.
4. **Evidence, not belief.** "Done" requires §12 passing and proof shown:
   paths, frame numbers, what you actually saw. A claim is not a check.
5. **One change, then re-verify.** Never stack three edits and hope.
6. **Branch on `code`, not on message text** (§13). Most commands exit non-zero
   on failure.
7. **Nothing appears from nothing.** Every element enters by growing, unfolding,
   being drawn, masked or revealed from something already on screen. No pop-in,
   no fade-up default.
8. **Every frame is a pure function of `t`.** If a frame cannot be rebuilt by
   jumping straight to it, the build is wrong (§10).
9. **The camera never sits still** while a scene is alive: at minimum a
   `1.00 → 1.02` push, or it is a deliberate hold you can name.
10. **Safety.** No `shell=True`, no secrets in logs, no DRM bypass, no patching
    proprietary binaries, no binary modification. Bridges use documented APIs
    or read-only inspection.

---

## 2. Verified command reference

Every row below was executed against this build. Anything not here does not exist
for you until you prove it with `--help`.

| Goal | Command |
|---|---|
| Check machine | `omniframe doctor --json` (exit 1 = not ready; `--fix` only tries Chromium) |
| List actions | `omniframe tools --list` |
| Run an action | `omniframe run-tool <action> --params '<json>'` |
| New project | `omniframe project init <name> --dir <dir> --fps 30 --width 1920 --height 1080` |
| Validate | `omniframe project validate <project.json> --json` (exit 1 on errors; checks assets) |
| Summary | `omniframe project report <project.json>` |
| Timeline dump | `omniframe inspect timeline <project.json> --json` |
| Render frames | `omniframe project render <project.json> --out <dir>` `[--engine auto\|code_video\|cartoon_2d]` `[--backend auto\|playwright\|stub]` `[--cartoon-backend]` `[--resume]` `[--stream-to-ffmpeg <path>]` |
| Compose video | `omniframe project compose <project.json> --frames <dir-of-PNGs> --out <video.mp4> [--preset h264]` |
| Look at video | `omniframe inspect media --video <video.mp4> --output-dir <dir> --count 8 --contact-sheet <sheet.png>` |
| Look at frames | `omniframe inspect frames --directory <dir> --output <sheet.png> --columns 4 [--strip]` |
| Pick an engine | `omniframe route --capability <name> [--preferred]` |
| Translate timeline | `omniframe project translate --translator <name> <project.json> --out <output> [--direction to_host\|to_universal]` |
| Bridges | `omniframe bridge list [--json]` · `bridge detect <name>` · `bridge script <name> <project> --out <dir>` · `bridge inspect <name> <target>` |
| Checkpoints | `omniframe checkpoint save <project> --label <l>` · `list` · `restore <id> --project <project>` · `diff <before> <after>` |
| UI / MCP | `omniframe ui --host 127.0.0.1 --port 8765 [--open]` · `omniframe mcp` |
| Update | `omniframe update check [--json]` · `update apply` · `self-update` |
| Version | `omniframe version` |

- Bridges: `premiere_pro`, `after_effects`, `davinci_resolve`, `capcut`, `krita`.
- Translators: `fcpxml`, `edl`, `capcut_draft`, `ae_manifest`, `resolve_xml`
  (`--direction to_host` default, `to_universal` for the reverse read).
- Python API, when a CLI verb is missing. The package root
  `omniframe.engines.compositor` exports exactly: `Compositor`, `AudioTrack`,
  `SubtitleTrack`, `ExportPreset`, `mix_audio`, `run_ffmpeg`, `ffprobe_info`,
  `ffmpeg_available`, `build_video_from_frames`, `escape_filter_path`,
  `write_concat_list`, `write_artifact_manifest`, `get_preset`, `list_presets`.
  Anything else is a submodule import, not a package attribute:
  - `compositor.probe.probe_media_matrix(paths)` — measure media (returns one dict
    per file). Not re-exported; do not write it against the package root.
  - `compositor.golden.verify_frames(reference_dir, produced_dir, *, hash="sha256",
    tolerance=0.0)` — `hash`/`tolerance` are keyword-only.
  - `Compositor().mux_audio(video, audio, out, *, preset="h264",
    video_copy="auto")` — `"auto"` decides copy-vs-re-encode from codec
    compatibility; pass `True`/`False` only to force it.
  - `CodeVideoRenderer` for frame-by-frame control.

### Not in this build — do not pretend otherwise

| Absent | Reality | Use instead |
|---|---|---|
| `omniframe verify` | no such command | `inspect media` + `inspect frames`, read the images yourself; for a diff, `golden.verify_frames` |
| `project render --preview` | no such flag | half-resolution **copy** of the project (§4 Step 5) |
| `--engine` on `render` | accepted, then ignored | engine follows each clip's `kind`; set it per clip |
| audio mux in `compose` | frames only | `Compositor.mux_audio(...)` |

---

## 3. Router — pick exactly one mode before you write anything

Read the request four times: **artifact**, **duration**, **source**, **destination**.
Choose the row that matches the artifact; the other columns are then fixed for you.

| Request family | Mode | Engine | Structure | Mandatory extra gate |
|---|---|---|---|---|
| Product/launch film, UI demo, logo reveal, 5-30s | Short | code_video | Product film | Brand fidelity: no invented screen, number, chart or feature |
| Kinetic type, title sequence, lyric video, 5-60s | Short | code_video | Beat-locked type | Reading speed + loop closure |
| Reel / Short / TikTok / portrait social, 5-60s | Short | code_video | Vertical short | Safe area + legible muted |
| Trailer / teaser / sizzle / montage, 10-60s | Short | code_video or ffmpeg | Escalation | Loudness + flash/photosensitivity |
| Explainer, tutorial, essay, course, 1-30+ min | Long | code_video (+ffmpeg) | Chaptered | Per-chapter isolation + lower thirds |
| Documentary, interview, talking head, 3-30+ min | Long | ffmpeg compositor | Transcript cut | Word sync + ducking + no caption over face |
| Data, infographic, market or product update, 15s-5min | Either | code_video | Labelled chart | One number per shot, axis honesty |
| Code or system walkthrough, 20s-10min | Either | code_scene | Code + diagram | Monospace alignment, no invented syntax |
| Cartoon, character, story gag, 10s-5min | Short or Long | cartoon_2d | Beats in key poses | Contact lock, hold ≥ 6 frames |
| Restyle or reformat an existing cut | Transform | keep | Identical scene ids | Same timings, new tokens only |
| Insert my logo / screenshots / footage | Patch | either | Manifest + containers | No stretch, no collision, ducking |
| Fix, re-QC or rerender | Repair | same as input | Same timeline | Before/after evidence |
| Export to a host app | Bridge | n/a | Timeline only | Loss report, generated vs tested |
| Install, update, doctor, UI, MCP | Ops | n/a | n/a | Quote exact output |

If the request fits no row: take the nearest row, say which one and why, and ask one
question only if the answer changes the deliverable's *shape*.

**Question budget: 3, total, ever.** Ask only for what you cannot default:
the subject matter, a brand's real name/color/glyph, or a required duration.
Everything else gets a stated default: "Assuming 15s, 16:9, 30fps, 120 BPM, no VO."
After that, build. Never interrogate.

---

## 4. The pipeline — nine steps, five gates

Modular in the sense that every step has an exit condition you can check without
having finished the film. Skipping a gate is the only way to produce a broken render.

**P1 — Brief in one line.** `MODE · duration · aspect · fps · audio · destination ·
subject`. Unstated fields get defaults and a one-line "defaults applied" note.
*Exit:* the line exists and contains no question mark.

**P2 — Concept.** One sentence naming the **through-line object** and its
transformation chain: `A → B → C → … → logo`. The through-line object is the single
thing every scene is made of (a seed, a cursor, a data point, a card, one letter).
*Exit:* you can say "scene 3 is scene 1 after the transform" in six words.

**P3 — Beat structure.** Music present → beat grid first (§5), beats before scenes.
Music absent → an explicit duration ladder (e.g. 0.8 / 2.0 / 3.4 / 6.0 / 8.5 s).
*Exit:* every scene has integer `start_frame` and `duration_frames` snapped to the grid.

**P4 — Reference blueprint** (only if a reference was supplied) → `blueprint.json`,
built with the §7 procedure. No reference → skip, and say so.

**P5 — Asset manifest** (§8) before any scene code. Every user file gets an id, a kind,
measured dimensions and a chosen container. *Exit:* `project validate` reports no
missing asset and no asset is used twice under two ids.

**P6 — Deterministic build** (§10). `bootstrap` builds the DOM once; per-frame
`javascript` derives every style from `t = __OMNIFRAME_FRAME__ / __OMNIFRAME_FPS__`.
*Exit:* `seek` is idempotent, and a cold render of frame N equals a warm render of N.

**P7 — Stills and the visual gate** (§11). Render stills at every scene start, middle,
and end plus one frame per beat; inspect them as images; fix defects in priority
order; re-render the stills. *Exit:* gate table clean, or every remaining item named.

**P8 — Preview.** Half-size `meta.width`/`meta.height`, `meta.duration_frames` cut to a
few seconds, clips clamped (`start_frame + duration_frames` ≤ the new end), render,
compose, `inspect media`, actually read 8-12 frames. *Exit:* timing and legibility
confirmed at speed.

**P9 — Full render, compose, audio mux, report.** PNG render is resumable — prefer it
for long jobs; `--stream-to-ffmpeg` only for a single renderable clip and never with
`--resume`. Mux, re-inspect the final file, then report per §12.

Ordering rule: **P5 before P6, P7 before P9.** Looking at frames is cheaper than
rendering minutes, and a manifest is cheaper than re-laying-out 12 scenes.

---

## 5. Time base — the arithmetic you do before designing

`beat = 60 / BPM` seconds · `bar = 4 * beat` · `beat_frames = fps * 60 / BPM`.

| BPM | beat | bar | beat frames at 24 | 25 | 30 | 60 |
|---|---|---|---|---|---|---|
| 90 | 0.667 | 2.667 | 16 | — | 20 | 40 |
| 100 | 0.600 | 2.400 | — | 15 | 18 | 36 |
| 120 | 0.500 | 2.000 | 12 | — | 15 | 30 |
| 128 | 0.469 | 1.875 | — | — | — | — |
| 140 | 0.429 | 1.714 | — | — | — | — |

- `—` means the beat is not an integer frame count. Then: `frame(i) = round(i * beat_frames)`
  computed from the **index**, never `frame += beat_frames`. Accumulating drifts; the
  index formula cannot.
- Ideal: choose fps so the beat lands on an integer (120 BPM → 24/30/60; 100 → 25/30/60).
- Measure the grid from the actual track (numpy onset/energy peaks, or Whisper word
  timestamps for speech). Never assume "this is 120". Start the film on a **downbeat**.
- 15s @120 = 7.5 bars: build bars 1-5, strongest full bar = 6 (12.0-14.0s), end card =
  final half bar (14.0-15.0s). 30s = 15 bars, 60s = 30 bars.
- `meta.duration_frames = round(seconds * fps)`; last sampled frame is
  `duration_frames - 1`. No clip may end past it.

---

## 6. Mode rules

### 6A. Short-form (5-60s — reels, shorts, showreels, teasers, kinetic ads)

| Rule | Value |
|---|---|
| Typography | **one** family for the whole film; roles by size/weight/case/tracking, not by family |
| Palette | ≤ **3** colours + black + white; **one** accent; accent only on the through-line object and the key word |
| Space | ≥ 55% of the frame is empty at any moment; density *varies*, it does not climb |
| Cuts | forbidden as a default: shapes/type/colour transform into the next scene. A hard cut must be a **match cut** measured at runtime (same bbox ± 2px, same centre ± 1%) |
| Rhythm | something happens on **every beat**; **one technique per bar**; technique set grows monotonically |
| Peak | strongest moment on the biggest beat = **last full bar**; end title in the **final half bar**, held ≥ 1.2s |
| Loop | if the deliverable loops: `seek(t)  seek(t + DUR)`, `frame 0 == frame N-1`; renderer samples `0..N-1` so the wrap frame is never emitted — exact by construction |
| Banned | particle bursts, glows, lens flares, camera shake as decoration, RGB split, crossfades/dissolves as default, generic gradients, bouncy/elastic-default easing, holds > 0.5s (except the end card), template look, stock footage, emoji spam, zoom punches, captions over a face, walls of text, bullet lists, stock icons, everything moving at once, dead time |

Short-form is **one idea, one object, one accent, one soundtrack**. If a second idea
needs to exist, it is a transformation of the first, not a new scene.

### 6B. Long-form (1 min - 30+ min — explainers, docs, tutorials, essays)

| Section | Share | Job | Pacing |
|---|---|---|---|
| Hook | ≤ 8s or 5% | the problem in 3-5 words, or the result shown first | 2-4 shots |
| Context | 12-15% | why this exists, what you'll be able to do | shot 3-6s |
| Core | 60-70% | 3-6 chapters, each: claim → picture → evidence → recap | shot 5-10s, ≤12s |
| Callouts | woven | numbers, quotes, labels where they belong | ≥ 3s on screen |
| Outro | 6-10% | the one takeaway, then the ask | hold ≥ 4s |

Long-form laws:

1. **One diagram, one continuous space.** Core concepts live in a single coordinate
   space; the camera zooms *in* to explain a part, and pulls *back* to show fit.
   New diagrams only for genuinely new domains.
2. **Picture before words.** Every idea gets a visual before its sentence arrives.
3. **Labels sit on the thing they name**, never in a legend, never a numbered key.
4. **Arrows follow real flow** (data direction, cause → effect, time).
5. **One thing moves at a time.** Everything else is still, or drifts below the
   threshold of noticing (`≤ 0.4 px/frame`, `≤ 0.15/s`, `≤ 0.5%/s` scale).
6. **Audio-first.** Cut points come from the transcript/beat map, then picture is
   timed to the measured audio length. Never time words to a guessed reading.
7. **Modular scenes.** One chapter = one scene = its own clip ids and frame range.
   Editing chapter 4 must not force a re-render of 1-3: give each chapter its own
   `project.json` in `scenes/<n>/`, plus a master project that references the
   rendered outputs. Re-render only the changed chapter.
8. **Lower thirds** (one line, name/role or term/definition): band height 8-11% of
   frame, x = 6%, baseline y = 74-78%, `in 0.25s / out 0.25s`, on screen ≥ 3s,
   never over a face, never two at once.
9. **On-screen text** ≤ 7 words per line, ≥ 0.3s per word of reading time, and it
   must survive being muted.
10. **No TTS in-platform.** Voiceover is a supplied file; captions always exist as
    text. Say this out loud rather than shipping a silent "narrated" film.

### 6C. Transform / Patch / Repair / Bridge / Ops

- **Transform** (restyle, reformat): keep scene ids, timings and narrative; change
  tokens (palette, type, easing, transition intent), then re-check the same stills.
  Rebuild only the scenes whose assets no longer fit the language. Report the diff.
- **Patch** (user assets): manifest first (§8). Containers are designed *for* the
  aspect ratios you measured, not for the ideal ones.
- **Repair**: reproduce the defect, name the class (§11), fix the smallest cause,
  re-render the same checkpoint frames, show before/after.
- **Bridge**: `bridge script` then `bridge inspect`; always read the loss report and
  say which files are *generated*, which are *tested* in the host. With no host
  installed, `import_tested = 0` and `production_candidate = 0`. Never claim more.
- **Ops**: quote the exact output; a `doctor` failure is a repair step, not a task
  failure. `update check` works offline from cache — a GitHub outage is not a bug.

---

## 7. Reference decompilation → `blueprint.json`

Triggered by a reference video, a storyboard, a screenshot set, or "make it feel like
this". Output is one JSON file. It is a **convention artifact**, not a platform type:
store it beside the project and point at it from `project.metadata.blueprint`.

```json
{
  "schema": "omniframe.blueprint/1",
  "source": { "kind": "video", "ref": "<path or url>", "duration_s": 15.0,
              "fps": 30, "size": [1920, 1080], "probed": "probe_media_matrix" },
  "palette": { "bg": "#f9fbfb", "fg": "#101014", "muted": "#6b7280",
               "accent": ["#2f6df6"], "color_count": 3, "contrast_min": 4.5,
               "gradient": "radial-corner" },
  "type": { "families": ["Inter"], "max_families": 1,
            "roles": { "display": { "size_pct": 9.2, "weight": "black",
                                    "case": "upper", "tracking": -0.02 },
                       "body": { "size_pct": 2.8, "weight": "normal" } },
            "min_size_pct": 2.2, "max_words_display": 6, "max_words_body": 7 },
  "motion": { "ease": { "enter": "out_expo", "exit": "in_cubic",
                        "move": "in_out_quart", "emphasis": "out_back" },
              "spring": { "stiffness": 180, "damping": 26 },
              "stagger_ms": 40, "blur_speed_px_s": 900,
              "hold_max_ms": 500 },
  "camera": { "push_per_scene": 1.04, "dolly": "log", "tilt_deg": 56,
              "focal_px": 1880, "dof_front": 75, "dof_behind": 60,
              "dof_cap_px": 120, "parallax_depth": [0.3, 1.6] },
  "transitions": [{ "type": "match", "share": 0.4 }, { "type": "mask", "share": 0.3 },
                  { "type": "zoom", "share": 0.3 }],
  "pacing": { "cuts_per_10s": 12, "shot_median_s": 0.8, "hold_max_s": 0.5,
              "peak_at": 0.82, "dead_time_max_ms": 400 },
  "rhythm": { "bpm": 120, "grid": "beat", "downbeat_offset_s": 0.0,
              "cue_density_per_beat": 0.7 },
  "composition": { "safe_area": [0.06, 0.08, 0.88, 0.84], "horizon": 0.55,
                   "density_mean": 0.22 },
  "sound": { "genre": "minimal-electronic", "lufs": -14, "duck_db": -15 },
  "confidence": { "palette": 0.9, "type": 0.6, "ease": 0.4, "pacing": 0.8 }
}
```

**How to measure** (no guessing, no "vibes"):

| Trait | Method |
|---|---|
| Palette | sample N frames with Pillow, k-means k=5, drop clusters < 3% area, order by area; accent = the cluster used on ≤ 2 objects |
| Type | crop the largest text block, estimate cap-height px / frame height → `size_pct`; classify family by stem/serif evidence into `sans-neutral`, `serif-editorial`, `mono`, `display-geometric` |
| Easing | track the bbox of one moving element per shot, plot `p(t)`, fit the four candidates (out_expo, out_back, in_out_quart, spring) to the normalized curve, take the lowest residual |
| Camera | track two known points' separation; a growing ratio is push, a constant ratio with translation is pan |
| Pacing | onset list → cut list → intervals; `cuts_per_10s`, median, `hold_max_s`, `peak_at` = time of the largest inter-cut delta |
| Rhythm | onset autocorrelation → BPM; `downbeat_offset_s` = which beat a scene change lands on |
| Composition | mean alpha coverage / ink ratio on 5 sampled frames → `density_mean`; safe area = the bbox that no text ever leaves |

**Fidelity budget.** Apply a trait only if `confidence ≥ 0.6`. Every trait must land in a
real schema field (`meta`, `TextSpec`, `Easing`, `Transform`, `AudioSpec`, clip
`start_frame`/`duration_frames`, …). A trait with no field is **dropped and listed** in the
report under "not expressible". Never invent a field to honour the reference.
The reference supplies *style*; the user's topic supplies *content, names, numbers and
screens*. Copy the grammar, never the story.

---

## 8. Assets — manifest, framing, video-in-video, ducking

### 8A. Manifest (before layout)

Every user file becomes one `Asset` with a stable `id`, `kind`
(`image|video|audio|font|videojs|script|other`), `path` (inside the project workspace,
else `E_PATH_SECURITY`), and `metadata`:

`width`, `height`, `aspect`, `bytes`, `has_alpha`, `dominant` (3 colours), `duration_frames`
(audio/video), `has_audio`, `fps`, `source`, `license`.

- Measure with Pillow (images) or `probe_media_matrix` / `ffprobe_info` (media). Never
  trust a filename, never guess a size.
- **Didn't inspect it? Don't place it.** A placement without manifest metadata is the
  single most common overflow bug.
- One asset = one id. Two ids pointing at one file is a duplication bug; one id
  pointing at two files is not expressible.
- `project validate` checks asset existence — an unused manifest entry still costs a
  file check, so prune entries you dropped.

### 8B. Safe framing decision table

`W,H` = container, `w,h` = asset intrinsic.

| Aspect ratio difference | Fit | Rule |
|---|---|---|
| ≤ 2% | `fill` | scale so the asset's own box matches; no crop, no letterbox |
| 2-25% | `contain` | fit inside, pad with palette bg, or the subject's own blurred copy (blur ≥ 40px, darken ≥ 25%) |
| 25-60% | `cover` **or** re-contain | crop only if the subject is centred and safe; otherwise use a 2-up/split container |
| > 60% | redesign | a wide screen does not go into a portrait slot; change the container |

Hard rules:

- **Never non-uniform scale.** One factor for x and y. `object-fit: fill` is banned.
- **Never upscale a raster** past **1.35×** of its pixel size; if the container demands
  more, use a plate/inset or a vector version.
- **Crop safety:** ≥ 12% of any axis must survive as margin; never crop a face's eyes,
  mouth, a logo's mark, or a UI's active control. If the subject's bbox is
  unknown, assume centred and crop ≤ 10%.
- **Text over media** needs a measured local contrast ≥ 4.5:1 (≥ 3:1 for ≥ 48px display text).
  Sample the pixels under the text box, not the palette. Under it: scrim
  (≥ 55% opacity), solid plate, or move the text.
- **Logo:** clear space ≥ 0.5 × mark height on all sides, ≥ 48px at 1080; never recolour,
  never trace, never add outline; inverse only on a solid dark plate; animate the mark
  itself (mask/scale), never a wrapper box that reads as a new logo.
- **Screenshots as hero:** rebuild as vector layers (rows, chips, text) so they can
  transform; a flat screenshot may slide as *evidence*, never as the transform target.
- **Text never collides** with media, and media never collides with text: minimum gap
  4% of frame width, or 24px at 1080 (whichever is larger). One exception, and only one: 
  a deliberate masked reveal that ends with text on solid background.

### 8C. Video-in-video sync

1. Convert project frame → source time in one place:
   `src_t = in_frame_src / src_fps` and `src_frame = round(src_t * src_fps)`; keep
   `Clip.in_frame`/`out_frame` in **source** frames, and `speed = 1.0` (2.0 or 0.5 only if
   you verified it in a still).
2. Never exceed `out_frame - in_frame`; a 30-frame source in a 90-frame slot must hold its
   last frame, freeze deliberately, or loop *on a beat*, never stretch silently.
3. Trim points land on the same grid as everything else: in on movement, out on movement,
   never mid-word, never on a breath.
4. Entry/exit: ≥ 6 frames (0.2s) of motion (scale, mask or slide) — no hard pop.
5. Audio: if the clip's own sound is used, it is the master for that span. Duck the bed
   **and** the SFX under it: `AudioSpec.duck_under` lists the ids being ducked, target
   `-14 LUFS` integrated, true peak ≤ `-1.0 dBTP`, duck −12…−18 dB with 120ms attack /
   400ms release. If the clip's audio is not used, say so and keep the bed unbroken.
6. Verification: frame-accurate A/V offset ≤ 1 frame (cross-correlate), and lips/impacts
   must not drift at the end of the clip.

### 8D. Ducking & loudness

| Case | Setting |
|---|---|
| Music under VO | music −14…−18 dB, VO −16 LUFS short-term, music −24 LUFS |
| Music under clip audio | clip −14…−16 LUFS, music −22 LUFS; ducking via `duck_under` |
| Music only | −14 LUFS integrated, ≤ −1.0 dBTP |
| SFX | headroom ≥ 6 dB below VO; no SFX on every word |
| Ambience | −30 LUFS, gated, 200ms fades so no clicks |

`AudioSpec`: `volume` 0…4 (1.0 = unity), `fade_in_frames`/`fade_out_frames` (never 0 on
music or ambience), `normalization` `none|peak|ebu_r128`, `target_lufs` −14 default.

---

## 9. Motion grammar (the physical layer)

Easing is chosen by **role**, not by taste:

| Role | Easing | Feel | OmniFrame kind |
|---|---|---|---|
| entrance | out_expo / out_quint | decisive, lands early | `ease_out` or `bezier` (0.16,  0.84, 0.28, 1) |
| exit | in_cubic / in_quart | gathers pace, no farewell | `ease_in` |
| move/relocate | in_out_quart | travels, no bounce | `ease_in_out` |
| emphasis/pop | out_back (s ≤ 1.10) | tiny overshoot, ≤ 3% | `bezier` with >1 control |
| spring (UI, interruption) | closed-form, ζ ≈ 0.55-0.75 | settles in 300-450 ms | sample N keyframes or integrate in scene JS |
| ambient drift | linear | imperceptible | `linear` |
| hold | — | stillness is an event | `hold` |
| stepped | 4-12 fps | stop-motion, mechanical | `step` |

Laws:

1. **Closed-form time.** `x(t)` analytic, not `x += v*dt`. Numeric integration is allowed
   only with a fixed `dt = 1/fps`, a step count derived from the frame index, and state
   rebuilt from frame 0 inside `seek` — never carried across calls.
2. **Springs sum.** A value that changes target many times is the sum of one spring per
   change (one instance per target change), so it stays pure. One spring instance is not "a spring with
   its input changed".
3. **Stagger** 30-60ms per sibling (2-4 frames at 30fps), never > 80ms in short-form.
4. **Blur follows velocity.** Directional blur, radius ≈ `speed * k`, capped
   (≤ 12px short-form, ≤ 120px for a landing-page dive). Zero blur on a still frame.
5. **Anticipation → action → follow-through**, always. Anticipation 2-4 frames, action,
   then a settle or 8-15% overshoot that resolves.
6. **Squash on impact**, 4-8% for one to three frames, only on soft bodies.
7. **Holds are declared.** Key pose ≥ 6 frames in character work; any still > 0.5s in
   short-form must be labelled a hold or it reads as a dead frame.
8. **Nothing appears from nothing.** Grow, unfold, mask, draw, or split from a parent.
   Opacity alone is a legal *transition*, never a legal *entrance*.
9. **Cut on action / match on shape.** Match cuts are measured at runtime
   (previous bbox vs next bbox, ± 2px, same centre ± 1%), never hard-coded.
10. **A shape that fills the frame must scale past all four corners**, or the edge pops.
11. **Never put `will-change`/`transform` on text the camera scales** — it rasterises at
    the wrong size and blurs. Scale the container, re-lay-out the text.
12. **One accent, one through-line object, one moving idea per shot.** Everything else is
    subordinate; if two things compete, delete one.

---

## 10. Determinism contract

The renderer injects, then re-runs `javascript` **once per frame**:

`window.__OMNIFRAME_FRAME__` · `__OMNIFRAME_FPS__` · `__OMNIFRAME_TOTAL_FRAMES__` ·
`__OMNIFRAME_SEED__` · `__OMNIFRAME_PARAMS__` · `__OMNIFRAME_RANDOM__` (seeded, `seed + frame`).

It also pauses CSS animations and disables transitions before capture.
`bootstrap` runs once; `settle_timeout_ms` bounds the ready wait.

**The frame function**. Write one idempotent draw function and call it from the per-frame
entry — nothing else:

```js
// javascript (runs each frame)
const t = window.__OMNIFRAME_FRAME__ / window.__OMNIFRAME_FPS__;
window.seek(t);                       // your own pure draw function
```

```js
// bootstrap (runs once)
const stage = document.getElementById('stage');    // build nodes ONCE
const nodes = { ... };                              // cache every lookup
window.__OMNIFRAME_WAIT_FOR_READY__ = true;
Promise.all([document.fonts.ready, ...assetDecodes]).then(() => {
  window.__OMNIFRAME_READY__ = true;             // only after real readiness
});
window.seek = function (t) { /* set attributes from t only */ };
```

Forbidden in the frame function:

`Math.random` (use `__OMNIFRAME_RANDOM__`) · `Date.now` / `performance.now` /
`new Date()` · `setTimeout` / `setInterval` · `requestAnimationFrame` · CSS `@keyframes`,
`transition`, `animation` · `element.animate` / Web Animations · reading state your own
previous frame wrote (`++`, `push` into wiped-later arrays, "if last time…") · lazy
`getBoundingClientRect` before layout settles · unawaited image/font/video decode ·
`localStorage` · `devicePixelRatio`-dependent sizing (pin it).

Rules that make the above survivable:

1. **Create nodes in `bootstrap`, mutate them in `seek`.** Never `createElement` per frame.
2. **Time is quantised.** `t = frame / fps` exactly. Never `t += dt`, never a float
   accumulated over 2700 frames.
3. **Randomness is pre-drawn.** If you need N random values, draw them in `bootstrap` into
   an array; index that array in `seek`. Conditional draws change the stream and break
   determinism between a preview and the final render.
4. **Loops are period-exact.** `seek(t)  seek(t + DUR)`. Bits are driven by
   `phase = (t / DUR) % 1` (or `t % DUR`), never by an end-of-clip correction.
   Because frames are `0 … N-1`, frame 0 and the wrap frame are identical *by construction*.
   Verify: render N subframes, compare frame 0 and frame N; if you also encode a loop copy,
   compare the encoded first and last frame and allow ≤ 0.01% warmed pixels.
5. **Ready means ready.** Async loads gate on `document.fonts.ready`, `decode()`,
   `loadeddata`; then set `__OMNIFRAME_READY__`. A timeout is not a readiness signal.
6. **Idempotence is testable.** Render frame N, render N+1, render N again in a fresh page:
   the two N's must hash equal. If not, you have state or a stale read.
7. **Freeze what you cannot derive.** Any third-party animation gets killed; any layout
   measurement you depend on is taken once in `bootstrap` against fixed width/height.
8. **Audio is also pure.** Web Audio via `OfflineAudioContext` at 48kHz, rendered from the
   same time base, exported as WAV. No realtime scheduling, no `currentTime` reads.

---

## 11. Pre-render visual gate

Before the full render, produce checkpoint stills and **open them as images**. Stills are
the cheapest defect detector you have; a full render is the most expensive way to learn you
mis-centred a word.

**Checkpoint set.** Scene starts, scene mid-points, scene ends, plus one frame per beat for
short-form (or every 2 bars for long-form), plus the exact frames of every beat hit in the
first and last bar. Cost control: stills first, then a half-res preview, then the full render.

**Defect classes, in fix-priority order.** Fix structural before legibility before rhythm
before taste — polishing a clipped word is wasted work.

| # | Class | Test | Threshold | Auto-fix |
|---|---|---|---|---|
| 1 | Blank / black frame | luminance & alpha stats | < 2% non-bg ink where content is expected | check layer opacity/visibility/compositing order/mask |
| 2 | Frozen frame | frame hash `n` vs `n-1` | identical ≥ 3s and not a declared hold | find the state that is not advancing |
| 3 | Clipped text | bbox of text vs container & frame | any overflow > 0 px | shorten copy → step down a role → reflow → widen container (in that order) |
| 4 | Overlap | text×text, text×media, media×media bbox intersection | > 3% of the smaller box area | move to the nearest free slot; never let the fix create a new overlap |
| 5 | Contrast | WCAG ratio on sampled local pixels | < 4.5:1 body, < 3:1 large | scrim, plate, or local recolor; never shift the whole palette |
| 6 | Too small | text height / frame short side | < 2.2% | promote the role, or delete the line |
| 7 | Off-beat | event time vs grid | \|Δ\| > 1 frame | re-snap to `round(i * beat_frames)` |
| 8 | Dead time | motion energy between events | < 400ms of no change in short-form | add one micro-move or cut the gap |
| 9 | Unintended cut | abrupt full-frame delta away from declared cuts | `scdet` hit outside the transition map | add the match element or the mask |
| 10 | Density | simultaneous moving elements | > 7 | stagger the non-hero ones, or delete the extras |
| 11 | Palette drift | distinct colors over the film | > 3 + B/W outside declared exceptions | pull the stray to the accent or to neutral |
| 12 | Loop seam | frame 0 vs encoded last frame | > 0.01% differing pixels | fix the period, not the codec |

Order 3 → 6 → 5 → 4 → 11 for typography, 7 → 8 → 9 → 10 for rhythm, 1 → 2 → 12 for
mechanics. Re-render the stills after each fix round. Three rounds on one class means the
*structure* is wrong — go back to P3, not P11.

---

## 12. Finish Gate — all must hold before you say "done"

**A. Machine**
- [ ] `project validate --json` → 0 errors (assets included).
- [ ] `project report` / `inspect timeline` → frame count, duration, resolution match the brief.
- [ ] Output exists, `ffprobe` reads it: container, codec, `width×height`, `fps`,
      `nb_frames` == `duration * fps` (± 1), pixel format as targeted.
- [ ] Duration == `duration_frames / fps` (± 1 frame). No `-shortest` truncation.
- [ ] Audio (if any): stream present, 48kHz, channels as specified,
      integrated loudness −14 ± 1 LUFS, true peak ≤ −1.0 dBTP, offset ≤ 1 frame.
- [ ] `golden.verify_frames` / hash compare: re-render one checkpoint frame in a fresh
      page → identical hash (determinism proof).

**B. Eyes** (you, looking at the contact sheet and the extracted frames)
- [ ] No blank, black or frozen frame; motion is continuous or hold-registered.
- [ ] No text clipped, overlapped, or below 2.2% of the short side.
- [ ] Contrast holds over the *actual* background of every text block.
- [ ] Hierarchy: one focal element per frame; you can name it for every still.
- [ ] Rhythm: hits sit on the grid; the strongest moment is where the concept says.
- [ ] Palette ≤ 3 + B/W; the accent appears only on the through-line object and key word.
- [ ] Nothing appears from nothing; the through-line object is traceable in every scene.
- [ ] If it loops: frame 0 equals the last frame, and it reads as one loop.
- [ ] Muted pass: the film still communicates without sound.
- [ ] No banned item from §6A survived.

**C. Honesty.** Report with these labels and never merge two into one:
`generated` (code wrote a file) · `structurally_checked` (schema/validate) ·
`import_tested` (a host app read it) · `render_tested` (frames and media exist and were
inspected) · `production_candidate` (a human signed off).

No DCC host on the machine ⇒ `import_tested = 0` **and** `production_candidate = 0`, stated
plainly. Bridge scripts are `generated`, not `import_tested`, until a host opens one.
"Feature exists" ≠ "production-complete". If the Finish Gate has a soft item you chose to
accept, say which one and why — never silently.

**Report format** (one screen, no code dumps unless asked):

```text
MODE      short 15s · 16:9 · 60fps · music only
CONCEPT   one seed → spiral → ring → type → grid → city → interface → seed
BLUEPRINT none supplied                        (or: 7/9 traits applied, 2 dropped)
ASSETS    4 used · 0 stretched · 1 cropped 12% (faces clear)
RENDER    900/900 frames · 15.000s · 1920x1080 · render_tested
AUDIO     aac 48k stereo · -14.2 LUFS · peak -0.9 dB · 0 dropped cues
GATE      12/12 · accepted warning: #10 density on the city shot (intentional)
NOT DONE  no voiceover (no source file) · import_tested = 0 (no host here)
```

---

## 13. Failure → next action

| `code` | Meaning | Do |
|---|---|---|
| `E_SCHEMA` | JSON does not match the project schema | fix the one field at the reported path; diff against `examples/` |
| `E_VALIDATION` | well-formed but inconsistent (overlaps, bad refs, missing assets) | fix exactly the listed issues; `validate --json` again |
| `E_ENGINE_UNAVAILABLE` | engine/backend not installed | `doctor`, or pick another `--engine/--backend` |
| `E_DEPENDENCY_MISSING` | optional package missing | install the extra (`.[render]`, `.[ui]`, `.[native]`) |
| `E_RENDER` | frame rendering failed | re-run one short clip; read `details` (scene + console) |
| `E_RENDER_CANCELED` | canceled or timed out | shorter clip, or `--resume` |
| `E_PATH_SECURITY` | path escaped the workspace | use a path inside the workspace; never bypass |
| `E_PRECONDITION` | missing asset/host/prerequisite | supply it; do not retry unchanged |
| `E_CHECKPOINT` | save/restore failed | `checkpoint list`, verify id and project path |
| `E_BRIDGE_UNAVAILABLE` | host not installed/reachable | not a bug: report it, use `bridge script` or a file path |
| `E_BRIDGE` | host rejected the operation | read details, fall back to the generated script |
| `E_TOOL_NOT_FOUND` | unknown action name | `tools --list`, use an exact name |
| `E_ACTION` | action raised while running | read `details`, fix input, don't retry as-is |
| `E_MIGRATION` | migration problem | stop; never delete the database; report |

Unknown code: read the whole JSON error, stop repeating the call. Same failure twice →
change one variable or ask. Same failure three times → stop, report what you tried, the
codes, and your best hypothesis.

---

## 14. Cost ladder & defaults

Escalate only when the cheaper rung cannot answer the question.

1. `validate` → structural truth, seconds.
2. Stills: one frame per scene start/mid/end → legibility, composition.
3. Stills: one frame per beat → rhythm, dead time, off-beat.
4. Half-res preview, few seconds → timing, transitions at speed.
5. Full PNG render, `--resume` → resumable, per-frame checkpoints.
6. `--stream-to-ffmpeg` → one renderable clip only, no PNGs, not with `--resume`.
7. Final compose → mux → inspect the delivered file, never the intermediate.

Defaults when the user says nothing: 1920×1080 · 30fps (60fps if the motion is
subframe-blurred) · 15s for short-form, 90s for explainer · 120 BPM · accent from the
brand or a single saturated hue · music generated, no VO · loop off unless asked.
State them once, in one line, then proceed.

---

## 15. Worked example (short-form, end to end)

Brief: "15 second film for our CLI, make it feel expensive."

1. **Mode** short. Defaults: 1920×1080, 60fps, 120 BPM (beat = 30 frames, bar = 120
   frames), music only, loop on request = no.
2. **Concept / through-line** a single 6px square is the cursor, the prompt glyph, a
   selection block, a terminal cell and finally the logo's counter. Chain:
   `cursor → prompt → block → grid → terminal → logo`. Transform: never a cut.
3. **Beats** 7.5 bars. Bar 1 hook (square lands, 3-word problem), bars 2-5 four product
   moments (each: square *becomes* the next UI element, one readable idea), bar 6 the
   strongest moment (grid of squares resolves to one), bar 6.5-7.5 end card (logo +
   name + one-line CTA), held 1.2s.
4. **Assets** none supplied. Palette measured from the product's real brand color;
   `#f9fbfb → #f2f3f6` radial canvas, ink `#101014`, one accent. Typeface: one grotesque,
   roles display/h2/body/mono.
5. **Build** `project init cli-launch --dir projects --fps 60 --width 1920 --height 1080`.
   One `code_scene` clip, 900 frames, seeded. `bootstrap` builds the square, the type
   layers and the grid node map; `seek(t)` derives everything from `t`; springs are
   closed-form functions of `t`; text is set via a prefix-of-final-string function so any
   frame renders independently.
6. **Stills** one frame per beat + every scene start/mid/end. Read them: two overlaps
   (a label over the square's edge, a caption under the grid), one 1.9% caption, one
   off-beat block (Δ 3 frames), one dead 700ms gap before the payoff. Fix: shorten the
   label, promote the caption, re-snap the block by index, move the payoff one beat
   earlier. Re-stills: clean.
7. **Preview** half size, first 5s: the rhythm reads, the end card is readable.
8. **Full** `project render --out out/cli-launch`, `project compose --frames out/... --out out/cli-launch.mp4`.
9. **Audio** `OfflineAudioContext` 48kHz: kick on every beat, one hit per scene change,
   riser into bar 6, downbeat hit at 12.0s; loudnorm to −14 LUFS / −1.5 dBTP; mux with
   `mux_audio(..., video_copy=True)`.
10. **Gate** `inspect media --count 8 --contact-sheet`, read the sheet, then
    `inspect frames` on the four busiest frames; run the Finish Gate checklist; loop check if
    looping; report per §12 with `render_tested`, and `import_tested = 0` (no host here).

---

## 16. Deeper references

- Install, update, UI, MCP, env vars, endpoints: `references/install-update.md`
- Action contracts and exact `params`/`output` shapes: `src/omniframe/agent/schemas/tools.json`
- Timeline model (all fields named in this file live here): `src/omniframe/core/timeline_schema/models.py`
- Programming guide: `src/omniframe/agent/AGENT_GUIDE.md`
- Example projects to start from instead of a blank file: `examples/`
- Repository: <https://github.com/amitkumardas3624/omniframe-studio>
