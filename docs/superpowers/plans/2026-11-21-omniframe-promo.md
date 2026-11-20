# OmniFrame Studio Promo Video Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build and render an original 30-second 1920×1080 OmniFrame Studio product promo that turns an AI-agent request into a validated, composed final video without using the supplied copyrighted YouTube video or its audio/assets.

**Architecture:** Create a self-contained `examples/omniframe-promo/` project whose `project.json` follows the existing OmniProject schema. Use deterministic HTML/CSS/JS scene payloads when Playwright/Chromium is available, and a project-local Pillow fallback renderer when it is not; assemble frames with the existing `Compositor`, generate a rights-safe procedural audio bed, then inspect the MP4 with contact-sheet and `ffprobe` checks.

**Tech Stack:** Python 3.10+, Pydantic OmniProject schema, Pillow, existing CodeVideoRenderer/Cartoon2D models, existing FFmpeg Compositor, stdlib `wave`/`math`, pytest.

## Global Constraints

- The final creative must be original and must not download, embed, trace, or frame-match the supplied YouTube video.
- Do not use the reference video's music, voice, footage, brand identity, exact edit, typography, transitions, or extracted frames.
- Use only OmniFrame-authored procedural assets or assets with explicit public-domain, CC0, or commercial-use permission recorded in `ASSET_LICENSES.md`.
- Keep the Python-first architecture and use existing OmniProject, CodeVideoRenderer, Cartoon2D, Compositor, FFmpeg, and inspection interfaces.
- Render at 1920×1080, 30fps, for 900 frames and approximately 30 seconds.
- Keep subprocess execution argument-list based; never use `shell=True`.
- Missing Playwright/Chromium or native acceleration must produce a structured fallback/report instead of preventing the Pillow-based deliverable.
- Generated frames, contact sheets, reports, audio intermediates, and MP4 outputs live under `examples/omniframe-promo/output/` and are not committed.

---

### Task 1: Scaffold the promo project and schema-valid timeline

**Files:**
- Create: `examples/omniframe-promo/project.json`
- Create: `examples/omniframe-promo/script.md`
- Create: `examples/omniframe-promo/captions.srt`
- Create: `examples/omniframe-promo/ASSET_LICENSES.md`
- Create: `tests/test_omniframe_promo_project.py`

**Interfaces:**
- Consumes: `OmniProject`, `Clip`, `CodeSceneSpec`, `CartoonSceneSpec`, `AudioSpec`, and `RenderTarget` from `omniframe.core.timeline_schema.models`.
- Produces: a schema-valid `examples/omniframe-promo/project.json` with six timed code scenes, one cartoon signal accent overlay, one audio track, captions metadata, and a 1920×1080 H.264 target.

- [ ] **Step 1: Write failing project tests**

```python
from pathlib import Path

from omniframe.core.timeline_schema.io import load_project

PROJECT = Path("examples/omniframe-promo/project.json")


def test_promo_project_has_expected_canvas_and_duration():
    project = load_project(PROJECT)
    assert project.meta.width == 1920
    assert project.meta.height == 1080
    assert project.meta.fps == 30
    assert project.meta.duration_frames == 900


def test_promo_project_has_original_storyboard_clip_boundaries():
    project = load_project(PROJECT)
    code_clips = [clip for track in project.tracks for clip in track.clips if track.kind.value == "code_scene"]
    assert [(clip.id, clip.start_frame, clip.duration_frames) for clip in code_clips] == [
        ("hook", 0, 90),
        ("prompt", 90, 150),
        ("structure", 240, 180),
        ("render", 420, 210),
        ("inspect", 630, 150),
        ("cta", 780, 120),
    ]
    accent_clips = [clip for track in project.tracks for clip in track.clips if clip.id == "signal-accent"]
    assert len(accent_clips) == 1
    assert accent_clips[0].start_frame == 420
    assert accent_clips[0].duration_frames == 210


def test_asset_manifest_states_no_reference_downloads():
    manifest = Path("examples/omniframe-promo/ASSET_LICENSES.md").read_text(encoding="utf-8")
    assert "YouTube reference" in manifest
    assert "not used" in manifest
    assert "procedural" in manifest.lower()
```

- [ ] **Step 2: Run the tests and confirm they fail**

Run:

```powershell
$env:PYTHONPATH = (Join-Path (Get-Location) 'src')
python -m pytest tests/test_omniframe_promo_project.py -q
```

Expected: FAIL because the promo project files do not yet exist.

- [ ] **Step 3: Write the 900-frame OmniProject document**

Use `schema_version: "1.0"` and `meta` values `{name: "omniframe-signal-to-cinema", version: "1.0", fps: 30, width: 1920, height: 1080, duration_frames: 900, color_space: "Rec.709", audio_sample_rate: 48000, audio_channels: 2, background: "#070B16"}`.

Create six primary video clips with exact frame ranges:

- `hook`: frames 0–89, `code_scene`, hook copy.
- `prompt`: frames 90–239, `code_scene`, terminal prompt.
- `structure`: frames 240–419, `code_scene`, timeline/schema/checkpoint cards.
- `render`: frames 420–629, `code_scene`, split code + motion render.
- `inspect`: frames 630–779, `code_scene`, compose/contact-sheet/final preview.
- `cta`: frames 780–899, `code_scene`, final CTA.

Add a `signal-accent` `cartoon_layer` clip on a `2d_animation` track from frame 420 for 210 frames. Its `CartoonSceneSpec` must contain only original vector/solid layers for the signal pulse, nodes, and sweep.

Each code clip must include a deterministic `CodeSceneSpec` with `seed`, `background`, `params`, and a stable DOM root. Add one `audio` track referencing `output/omniframe-promo-bed.wav` and one `subtitle` track whose metadata points to `captions.srt`. Add a `render_targets` entry with `container: "mp4"`, `video_codec: "libx264"`, `audio_codec: "aac"`, `width: 1920`, `height: 1080`, `fps: 30`, `path: "output/omniframe-promo.mp4"`, and `preset: "medium"`.

- [ ] **Step 4: Write the script, captions, and license manifest**

`script.md` must contain the exact approved storyboard copy and the audio plan: original procedural music bed, no reference music, no downloaded reference video, no unlicensed voice.

`captions.srt` must contain six timed captions matching the storyboard: 00:00–00:03 hook, 00:03–00:08 prompt, 00:08–00:14 structure, 00:14–00:21 render, 00:21–00:26 inspect, and 00:26–00:30 CTA.

`ASSET_LICENSES.md` must explicitly list every local asset as `procedural / OmniFrame-authored`, the generated WAV as `procedural / original`, and the YouTube reference as `not used; no download or extracted frame permitted`.

- [ ] **Step 5: Run project tests and schema validation**

Run:

```powershell
$env:PYTHONPATH = (Join-Path (Get-Location) 'src')
python -m pytest tests/test_omniframe_promo_project.py -q
python -m omniframe.cli project validate examples/omniframe-promo/project.json
```

Expected: all focused tests pass and the CLI reports a valid project.

- [ ] **Step 6: Commit the project contract**

```powershell
git add examples/omniframe-promo/project.json examples/omniframe-promo/script.md examples/omniframe-promo/captions.srt examples/omniframe-promo/ASSET_LICENSES.md tests/test_omniframe_promo_project.py
git commit -m "feat: add OmniFrame promo project contract"
```

---

### Task 2: Implement deterministic scene rendering with a browser-free fallback

**Files:**
- Create: `examples/omniframe-promo/render_promo.py`
- Create: `tests/test_omniframe_promo_renderer.py`

**Interfaces:**
- Consumes: `examples/omniframe-promo/project.json`, `CodeVideoRenderer`, Pillow, and `Compositor`.
- Produces: `render_project(project_path, output_dir, *, backend="auto") -> dict[str, object]`, `render_fallback_frame(scene_id, frame, width, height) -> PIL.Image.Image`, and a JSON-ready render report.

- [ ] **Step 1: Write failing renderer tests**

```python
import sys
from pathlib import Path

from PIL import Image

PROMO_DIR = Path("examples/omniframe-promo").resolve()
sys.path.insert(0, str(PROMO_DIR))
from render_promo import render_fallback_frame, render_project


def test_fallback_frame_has_delivery_dimensions():
    image = render_fallback_frame("hook", 45, 1920, 1080)
    assert image.size == (1920, 1080)
    assert image.mode == "RGBA"


def test_fallback_scene_is_deterministic():
    first = render_fallback_frame("structure", 300, 1920, 1080)
    second = render_fallback_frame("structure", 300, 1920, 1080)
    assert first.tobytes() == second.tobytes()


def test_render_report_contains_backend_and_frame_count(tmp_path: Path):
    report = render_project(
        Path("examples/omniframe-promo/project.json"),
        tmp_path,
        backend="fallback",
        frame_step=30,
    )
    assert report["backend"] == "fallback"
    assert report["frame_count"] == 30
```

- [ ] **Step 2: Run the tests and confirm they fail**

Run:

```powershell
$env:PYTHONPATH = (Join-Path (Get-Location) 'src')
python -m pytest tests/test_omniframe_promo_renderer.py -q
```

Expected: FAIL because `render_promo.py` does not exist.

- [ ] **Step 3: Implement the deterministic Pillow fallback**

Implement `render_fallback_frame()` with only Pillow drawing primitives:

- background `#070B16`, radial-looking layered circles, and thin grid lines;
- cyan/violet signal pulse for `hook`;
- terminal card with a blinking cursor and request text for `prompt`;
- timeline, schema, checkmark, and checkpoint cards for `structure`;
- split code panel and abstract vector-motion panel for `render`;
- progress bar, thumbnail grid, and final preview panel for `inspect`;
- centered CTA and signal sweep for `cta`.

Use the absolute frame number and scene-local progress to calculate opacity, positions, and easing. Use stable fonts available through Pillow’s default font fallback; do not depend on a downloaded proprietary font.

- [ ] **Step 4: Add optional CodeVideoRenderer execution**

In `render_project()`, load the project with `load_project()`. If `backend == "browser"` or `backend == "auto"` and `CodeVideoRenderer(backend="auto").available()` is true, render each code clip through `CodeScene.from_clip()` and `CodeVideoRenderer.render()` into scene frame directories. If browser rendering is unavailable or returns an error, record the reason in the report and render the complete frame sequence with `render_fallback_frame()` instead. Never hide the fallback reason.

- [ ] **Step 5: Assemble frames using the existing Compositor**

Write the complete 900-frame PNG sequence to `output/frames/` unless `--stream` is selected. Call `Compositor.frames_to_video()` with `fps=30`, `preset="h264"`, and output `output/omniframe-promo-video-only.mp4`. Return a report with `backend`, `frame_count`, `width`, `height`, `fps`, `duration_seconds`, `video_path`, and `fallback_reason`.

- [ ] **Step 6: Run renderer tests**

Run:

```powershell
$env:PYTHONPATH = (Join-Path (Get-Location) 'src')
python -m pytest tests/test_omniframe_promo_renderer.py -q
```

Expected: all focused renderer tests pass without requiring Chromium.

- [ ] **Step 7: Commit the renderer**

```powershell
git add examples/omniframe-promo/render_promo.py tests/test_omniframe_promo_renderer.py
git commit -m "feat: add deterministic OmniFrame promo renderer"
```

---

### Task 3: Generate rights-safe original audio and captions

**Files:**
- Create: `examples/omniframe-promo/generate_audio.py`
- Create: `tests/test_omniframe_promo_audio.py`

**Interfaces:**
- Consumes: duration, sample rate, and deterministic musical seed.
- Produces: `generate_bed(output_path, duration_seconds=30.0, sample_rate=48000) -> Path`, an original WAV with no reference recording or downloaded music.

- [ ] **Step 1: Write failing audio tests**

```python
import sys
import wave
from pathlib import Path

PROMO_DIR = Path("examples/omniframe-promo").resolve()
sys.path.insert(0, str(PROMO_DIR))
from generate_audio import generate_bed


def test_generated_bed_is_stereo_48khz_and_30_seconds(tmp_path):
    output = generate_bed(tmp_path / "bed.wav")
    with wave.open(str(output), "rb") as audio:
        assert audio.getnchannels() == 2
        assert audio.getframerate() == 48000
        assert audio.getnframes() == 48000 * 30


def test_generated_bed_is_not_silent(tmp_path):
    output = generate_bed(tmp_path / "bed.wav")
    with wave.open(str(output), "rb") as audio:
        payload = audio.readframes(audio.getnframes())
    assert any(byte != 0 for byte in payload)
```

- [ ] **Step 2: Run the tests and confirm they fail**

Run:

```powershell
$env:PYTHONPATH = (Join-Path (Get-Location) 'src')
python -m pytest tests/test_omniframe_promo_audio.py -q
```

Expected: FAIL because `generate_audio.py` does not exist.

- [ ] **Step 3: Implement the procedural music bed**

Use stdlib `math`, `random.Random(17)`, and `wave` to synthesize a stereo 48kHz 16-bit bed: a quiet sub pulse, a four-note minor arpeggio, filtered noise swells at scene boundaries, and a short final tone. Apply a 30ms fade-in, 250ms fade-out, and peak normalization below -1dBFS. Do not use any sample, melody, or stem from the reference.

- [ ] **Step 4: Add audio muxing to the renderer**

After video-only rendering, call `generate_bed(output/omniframe-promo-bed.wav)` and `Compositor.mux_audio(video_only, bed, output/omniframe-promo.mp4, preset="h264", video_copy=False)`. Include the audio path and mux result in the JSON report. Keep captions as both `captions.srt` and an optional burned-in review output.

- [ ] **Step 5: Run audio tests**

Run:

```powershell
$env:PYTHONPATH = (Join-Path (Get-Location) 'src')
python -m pytest tests/test_omniframe_promo_audio.py -q
```

Expected: all audio tests pass.

- [ ] **Step 6: Commit audio support**

```powershell
git add examples/omniframe-promo/generate_audio.py tests/test_omniframe_promo_audio.py examples/omniframe-promo/captions.srt
git commit -m "feat: add original promo audio bed"
```

---

### Task 4: Add the production command and inspection artifacts

**Files:**
- Modify: `examples/omniframe-promo/render_promo.py`
- Create: `examples/omniframe-promo/inspect_promo.py`
- Create: `tests/test_omniframe_promo_inspection.py`

**Interfaces:**
- Consumes: the project JSON and rendered MP4.
- Produces: `inspect_delivery(video_path, output_dir) -> dict[str, object]`, contact sheet PNG, `inspection.json`, and final media metadata.

- [ ] **Step 1: Write failing inspection tests**

```python
import sys
from pathlib import Path

from PIL import Image

PROMO_DIR = Path("examples/omniframe-promo").resolve()
sys.path.insert(0, str(PROMO_DIR))
from inspect_promo import build_contact_sheet


def test_contact_sheet_has_expected_grid(tmp_path: Path):
    frame_dir = tmp_path / "frames"
    frame_dir.mkdir()
    for index in range(8):
        Image.new("RGBA", (320, 180), (index * 20, 30, 80, 255)).save(frame_dir / f"frame_{index:06d}.png")
    sheet = build_contact_sheet(frame_dir, tmp_path / "contact-sheet.png", columns=4)
    assert sheet.exists()
    assert Image.open(sheet).size == (1280, 400)
```

- [ ] **Step 2: Run the test and confirm it fails**

Run:

```powershell
$env:PYTHONPATH = (Join-Path (Get-Location) 'src')
python -m pytest tests/test_omniframe_promo_inspection.py -q
```

Expected: FAIL because `inspect_promo.py` does not exist.

- [ ] **Step 3: Implement contact-sheet generation**

Select eight evenly distributed PNG frames from the rendered sequence, create a 4×2 sheet with 320×180 thumbnails, draw frame/time labels, and save `output/contact-sheet.png`. Do not delete the source frames.

- [ ] **Step 4: Implement FFprobe-backed inspection**

Call the existing FFmpeg helper or `subprocess.run(["ffprobe", "-v", "error", "-show_streams", "-show_format", "-of", "json", str(video_path)], check=True, capture_output=True, text=True)` with no shell. Parse JSON and write `output/inspection.json` containing duration, width, height, frame rate, video codec, audio codec, frame count if available, and any warning/error.

- [ ] **Step 5: Add the production CLI entry point**

Make `python examples/omniframe-promo/render_promo.py --project examples/omniframe-promo/project.json --output examples/omniframe-promo/output --backend auto` generate the audio, render all 900 frames, encode/mux the MP4, create the contact sheet, run inspection, and print the final JSON report. Add `--frame-step` for quick smoke runs and reject `--frame-step` values below 1.

- [ ] **Step 6: Run inspection tests**

Run:

```powershell
$env:PYTHONPATH = (Join-Path (Get-Location) 'src')
python -m pytest tests/test_omniframe_promo_inspection.py -q
```

Expected: all inspection tests pass.

- [ ] **Step 7: Commit production inspection support**

```powershell
git add examples/omniframe-promo/render_promo.py examples/omniframe-promo/inspect_promo.py tests/test_omniframe_promo_inspection.py
git commit -m "feat: add promo delivery inspection"
```

---

### Task 5: Render, inspect, and verify the complete film

**Files:**
- Generated locally: `examples/omniframe-promo/output/omniframe-promo.mp4`
- Generated locally: `examples/omniframe-promo/output/contact-sheet.png`
- Generated locally: `examples/omniframe-promo/output/inspection.json`
- Generated locally: `examples/omniframe-promo/output/render-report.json`

**Interfaces:**
- Consumes: all committed project, renderer, audio, caption, and inspection files.
- Produces: final MP4 plus verified inspection artifacts.

- [ ] **Step 1: Run a smoke render**

Run:

```powershell
$env:PYTHONPATH = (Join-Path (Get-Location) 'src')
python examples/omniframe-promo/render_promo.py --project examples/omniframe-promo/project.json --output examples/omniframe-promo/output-smoke --backend fallback --frame-step 30
```

Expected: 30 deterministic sample frames, a video-only smoke MP4, and a JSON report with no fatal errors.

- [ ] **Step 2: Run the focused promo tests**

Run:

```powershell
$env:PYTHONPATH = (Join-Path (Get-Location) 'src')
python -m pytest tests/test_omniframe_promo_project.py tests/test_omniframe_promo_renderer.py tests/test_omniframe_promo_audio.py tests/test_omniframe_promo_inspection.py -q
```

Expected: all promo tests pass.

- [ ] **Step 3: Render the complete 30-second delivery**

Run:

```powershell
$env:PYTHONPATH = (Join-Path (Get-Location) 'src')
python examples/omniframe-promo/render_promo.py --project examples/omniframe-promo/project.json --output examples/omniframe-promo/output --backend auto
```

Expected: the command selects browser rendering only if it is available; otherwise it explicitly reports the fallback and produces the complete Pillow-based original video. The final file is `examples/omniframe-promo/output/omniframe-promo.mp4`.

- [ ] **Step 4: Check delivery metadata**

Run:

```powershell
$env:PYTHONPATH = (Join-Path (Get-Location) 'src')
python examples/omniframe-promo/inspect_promo.py --video examples/omniframe-promo/output/omniframe-promo.mp4 --output-dir examples/omniframe-promo/output
```

Confirm `inspection.json` reports 1920×1080, 30fps, approximately 30 seconds, H.264 video, AAC audio, and no probe errors.

- [ ] **Step 5: Review the contact sheet and output files**

Open `examples/omniframe-promo/output/contact-sheet.png` and verify that hook, prompt, structure, render, inspect, and CTA are visually distinct, legible, and free of reference-video frames or branding. Confirm `ASSET_LICENSES.md` covers every non-generated file.

- [ ] **Step 6: Run the complete repository suite**

Run:

```powershell
$env:PYTHONPATH = (Join-Path (Get-Location) 'src')
python -m pytest -q
```

Expected: the existing repository tests and the new promo tests pass.

- [ ] **Step 7: Verify generated artifacts and worktree**

Run:

```powershell
Get-Item examples/omniframe-promo/output/omniframe-promo.mp4, examples/omniframe-promo/output/contact-sheet.png, examples/omniframe-promo/output/inspection.json
git diff --check
git status --short
```

Generated output remains uncommitted unless the user explicitly requests committing or publishing the media. Report the exact local paths and any optional-tool fallback used.
