# OmniFrame Studio “Signal to Cinema” Promo — Design Specification

**Date:** 2026-11-21
**Status:** Design approved by user; implementation not started

## Scope and rights

Create a new, original 30-second, 16:9 product advertisement for OmniFrame Studio using the existing Python-first rendering and compositing platform.

The supplied YouTube reference is **“Video Ad for AI / SaaS Product | Doks.AI”** by Zelios. The user confirmed they do not have permission to download or reproduce it. The reference may inform only high-level, non-protectable qualities such as concise SaaS storytelling, clean motion-graphics pacing, UI-led product explanation, and polished transitions. No reference frames, script, edit decision list, music, voice, brand assets, or downloaded video content will be used.

## Goal

Communicate one promise clearly:

> **OmniFrame Studio takes an AI-agent request to a validated, rendered, composed final video.**

The result should feel more useful and technically credible than a generic SaaS montage while remaining visually clean and understandable to a first-time viewer.

## Approved creative direction

**Signal to Cinema**: a dark studio environment with restrained cyan/violet accents. A visual signal begins as an agent request, becomes structured production data, turns into rendered frames, and resolves into a finished video preview.

The visual language must be original:

- dark navy/charcoal base with a distinct OmniFrame palette;
- abstract pulses, grids, timelines, and cards built from original SVG/CSS/Pillow primitives;
- original UI mockups based on OmniFrame’s own interface and action names;
- no imitation of the reference’s exact composition, typography, transitions, characters, or shot order;
- no copyrighted reference music; use an original or properly licensed music bed and an original/synthetic or user-supplied voice track.

## Storyboard and timing

| Time | Scene | Visual action | On-screen copy |
|---|---|---|---|
| 0–3s | Hook | A signal pulse forms the OmniFrame mark and expands across the canvas. | `What if your AI agent could ship the video?` |
| 3–8s | Prompt | An original terminal/UI card receives an agent request and confirms the job. | `Create a polished product scene from this idea.` |
| 8–14s | Structure | The request resolves into a typed timeline, tool schema, validation checks, and checkpoint marker. | `Validate · Plan · Checkpoint` |
| 14–21s | Render | Code-video and cartoon-2D visuals run in a split-screen frame stream. | `Render code + motion` |
| 21–26s | Compose and inspect | FFmpeg assembly, contact-sheet inspection, and a clean final preview. | `Compose · Inspect · Deliver` |
| 26–30s | CTA | Final video card locks into place with a subtle signal sweep. | `Describe it. Render it. Ship it.` / `OmniFrame Studio` |

The exact copy can be refined during implementation only if it preserves this promise and timing.

## System design

### Project package

Create a self-contained example under:

```text
examples/omniframe-promo/
  project.json
  script.md
  captions.srt
  ASSET_LICENSES.md
  assets/
  scenes/
  output/           # generated locally; ignored or kept outside the committed source
```

`project.json` is the source of truth for dimensions, frame rate, clips, timings, assets, and audio tracks. Generated frames, contact sheets, reports, and encoded video should not be committed unless explicitly requested as deliverables.

### Rendering stages

1. **Code-video scenes**
   - Build the terminal card, timeline card, tool-schema card, progress state, and final UI preview as deterministic HTML/CSS/JS scenes.
   - Use `CodeVideoRenderer` so browser-backed rendering can report structured issues.
   - Keep all scene text and layout authored in the project; do not scrape the reference video.

2. **Cartoon-2D accents**
   - Build the signal pulse, logo reveal, nodes, and abstract motion accents using `CartoonScene` primitives.
   - Prefer the Python fallback so the example remains runnable without the optional native accelerator.

3. **Composition**
   - Use the existing `Compositor` and FFmpeg helpers to assemble scene segments at 30fps.
   - Use the H.264 export preset at 1920×1080.
   - Add the cleared/original audio bed and voice track with explicit duration and fade handling.
   - Keep subtitles/captions as an optional soft-subtitle output and a burned-in review variant.

4. **Inspection**
   - Generate a numbered PNG sequence or stream frames to FFmpeg depending on available capabilities.
   - Produce a contact sheet and structured inspection report.
   - Probe the final MP4 with `ffprobe` and assert resolution, frame rate, duration, video stream, and audio stream expectations.

## Asset policy

- Use OmniFrame-authored SVG/CSS/Pillow shapes and UI mockups by default.
- If an online asset is necessary, download only from a source with explicit public-domain, CC0, or commercial-use permission.
- Record source URL, author, license, and local filename in `ASSET_LICENSES.md`.
- Do not download or embed the supplied YouTube video, its extracted frames, its audio, Digitalism’s “One Wave,” or any other unlicensed reference material.
- Do not request or store credentials, cookies, or private downloads.
- If an asset source is ambiguous, replace it with an original procedural asset rather than guessing.

## Error handling and portability

- Missing FFmpeg, Playwright/Chromium, or native acceleration must produce a structured doctor/render report and an actionable fallback path.
- The Python fallback must remain usable for cartoon-2D primitives.
- Browser-backed scenes should fail with source/frame/line diagnostics through the existing renderer result instead of silently producing corrupt frames.
- Audio and external asset failures must stop final delivery with a clear report; they must not silently substitute copyrighted material.
- All subprocess execution must remain argument-list based; no `shell=True`.

## Tests and acceptance criteria

Add focused tests for:

- project schema validation and clip timing;
- license manifest presence and required fields for external assets;
- deterministic scene generation and expected frame dimensions;
- composition command construction without shell execution;
- caption timing and final duration bounds;
- graceful fallback/reporting when optional tools are unavailable.

Acceptance requires:

- `omniframe project validate examples/omniframe-promo/project.json` succeeds;
- the project renders a representative smoke subset without reference-video inputs;
- final output is 1920×1080, 30fps, approximately 30 seconds, with expected audio/video streams when the selected audio assets are available;
- contact sheet and inspection report are generated;
- no reference frames, reference audio, secrets, or unlicensed downloaded assets are present;
- the design remains compatible with the current CLI, REST/MCP action registry, and Web UI workflows.

## Explicit non-goals

- Downloading or frame-by-frame reproducing the supplied YouTube video.
- Reusing the reference’s music, voice, footage, brand identity, or exact edit.
- Building a general-purpose AI video generator.
- Adding a new rendering backend when the existing code-video, cartoon-2D, and compositor engines are sufficient.
- Publishing the finished video to YouTube or another external service without a separate user request and confirmation.
