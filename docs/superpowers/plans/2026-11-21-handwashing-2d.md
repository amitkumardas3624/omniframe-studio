# Bengali Handwashing 2D Video Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Render an original 10-second Bengali educational handwashing animation with generic human-like 2D teacher and child characters.

**Architecture:** Keep the existing OmniFrame release unchanged and add a local demo project under `examples/handwashing-2d/`. Generate a schema-valid 300-frame project, render original Pillow/Cartoon2D-style layers, use the existing FFmpeg compositor for H.264/AAC output, and write contact-sheet/ffprobe evidence. Do not commit or push the demo output.

**Tech Stack:** Python 3.10+, Pydantic OmniProject schema, Pillow, existing Cartoon2D data model, existing FFmpeg Compositor, stdlib `wave`, pytest.

## Global Constraints

- Duration is 10 seconds, canvas is 1920×1080, frame rate is 30fps, and total frames are 300.
- Characters are generic original Bangladeshi teacher/child designs; no real-person likeness, voice, or signature style is copied.
- Bengali captions are required: `১ পানি`, `২ সাবান`, `৩ ২০ সেকেন্ড`, and `পরিষ্কার হাত, সুস্থ জীবন`.
- Audio is original procedural sound/music; no downloaded song or reference audio.
- Generated media stays under `examples/handwashing-2d/output/`, which is ignored and is not committed.
- No `shell=True`, credentials, DRM bypass, or proprietary asset patching.

---

### Task 1: Create the handwashing project contract

**Files:**
- Create: `examples/handwashing-2d/project.json`
- Create: `examples/handwashing-2d/captions.srt`
- Create: `examples/handwashing-2d/ASSET_LICENSES.md`
- Create: `tests/test_handwashing_project.py`

**Interfaces:**
- Consumes: existing `OmniProject`, `CartoonSceneSpec`, `CartoonLayerSpec`, `AudioSpec`, and `RenderTarget` schema.
- Produces: a valid 300-frame project with four timed scenes: problem 0–59, three steps 60–149, handwash action 150–239, reminder 240–299.

- [ ] Write tests asserting canvas, duration, four scene ranges, Bengali captions, and `not used` reference policy.
- [ ] Run `python -m pytest tests/test_handwashing_project.py -q` and observe the expected missing-file failure.
- [ ] Write `project.json` with original vector/solid/text layers for child, teacher, germ icons, faucet, soap, timer and final title.
- [ ] Write four SRT caption blocks matching the storyboard timings.
- [ ] Write `ASSET_LICENSES.md` marking every visual/audio asset procedural and original.
- [ ] Run the focused tests and `python -m omniframe.cli project validate examples/handwashing-2d/project.json`.

---

### Task 2: Implement the local 2D renderer and original audio

**Files:**
- Create: `examples/handwashing-2d/render_handwashing.py`
- Create: `examples/handwashing-2d/generate_audio.py`
- Create: `tests/test_handwashing_render.py`

**Interfaces:**
- Produces `render_handwashing(project_path, output_dir) -> dict[str, object]` and `generate_bed(output_path, duration_seconds=10.0) -> Path`.
- The renderer returns `frame_count`, `width`, `height`, `fps`, `video_path`, `audio_path`, and `fallback_backend`.

- [ ] Write failing tests for deterministic frame dimensions, 300-frame output, non-silent stereo WAV, and Bengali caption text presence in the project.
- [ ] Run the tests and confirm failure because renderer/audio modules do not exist.
- [ ] Implement original Pillow scene functions:
  - `draw_problem`: child, snack, germ icons, and “খাওয়ার আগে?”;
  - `draw_steps`: teacher plus three colored cards for water, soap and timer;
  - `draw_handwash`: faucet, hands, bubbles, timer ring and motion lines;
  - `draw_reminder`: teacher/child smile and final title.
- [ ] Use frame-local easing and original geometric shapes; use no downloaded images or real-person references.
- [ ] Implement a deterministic 10-second stereo WAV bed with light rhythm, water-like filtered tones and a final sparkle using stdlib `wave`/`math`.
- [ ] Assemble frames with `Compositor.frames_to_video()` and audio with `Compositor.mux_audio(..., video_copy=False)`.
- [ ] Run focused render/audio tests and confirm they pass.

---

### Task 3: Render and inspect the demo without committing it

**Files:**
- Create: `examples/handwashing-2d/inspect_handwashing.py`
- Generated: `examples/handwashing-2d/output/handwashing-2d.mp4`
- Generated: `examples/handwashing-2d/output/contact-sheet.png`
- Generated: `examples/handwashing-2d/output/inspection.json`

**Interfaces:**
- `inspect_handwashing(video_path, output_dir) -> dict[str, object]` writes a contact sheet and FFprobe metadata.

- [ ] Implement contact-sheet generation with eight labeled thumbnails and safe argument-list `ffprobe` execution.
- [ ] Run a short smoke render and inspect the contact sheet for four visually distinct scenes.
- [ ] Run the full 300-frame render:

```powershell
$env:PYTHONPATH = (Join-Path (Get-Location) 'src')
python examples/handwashing-2d/render_handwashing.py --project examples/handwashing-2d/project.json --output examples/handwashing-2d/output
```

- [ ] Run inspection and confirm H.264, AAC stereo, 1920×1080, 30fps, 300 frames and approximately 10 seconds.
- [ ] Run focused tests and the complete `python -m pytest -q` suite.
- [ ] Verify the MP4, contact sheet and inspection JSON exist; leave generated output uncommitted and report exact paths.
