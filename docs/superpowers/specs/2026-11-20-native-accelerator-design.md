# OmniFrame Native Accelerator and Zero-Reencode Pipeline Design

**Date:** 2026-11-20  
**Status:** Design approved in conversation; implementation pending written-spec review

## Goal

Reduce the measured 60-second stress workload cost without breaking the default Python installation or deterministic output contract.

Baseline workload:

- 1,440 frames
- 1280x720
- 24 fps
- 60 seconds
- Playwright code scene + Pillow cartoon scene
- FFmpeg segment composition, concat, audio mix/mux, and contact-sheet inspection

Observed baseline:

- 151.2 seconds sequential stage wall time
- 100.13 seconds render stage
- 706.4 MB peak RSS during audio mux
- 19.14 MiB PNG frame storage

## Scope and compatibility

The optimization is opt-in where output semantics or recovery behavior changes. Existing PNG rendering, checkpoint/resume, inspection, CLI contracts, timeline schemas, MCP actions, and DCC bridges remain available unchanged.

The native accelerator is optional. A missing C++ compiler, missing pybind11, failed native import, or unsupported scene feature must select the Python fallback rather than break package installation or normal execution.

No GitHub push or release-tag operation is part of this work.

## Architecture

### Runtime capability layer

Add `src/omniframe/_native/` with:

- `loader.py`: safe import and capability reporting
- `fallback.py`: pure-Python protocol-compatible implementations
- package exports for `native_available()` and accelerator status

Expose native status through `omniframe.has_native_accelerator()` and the `doctor` report. The status must distinguish `native`, `fallback`, and `unavailable` without exposing compiler paths or secrets.

### Optional C++ extension

Add a C++17/pybind11 extension under `cpp/` that can be built through an optional package extra. The extension must not be required by the normal dependency set.

Initial native surface:

- `FramePipeSink`: bounded frame buffer/pipe writer for RGBA/BGRA bytes
- `CartoonRasterizer`: deterministic primitive-layer compositing and keyframe evaluation
- `native_available()`: capability check

The extension releases the Python GIL around buffer writes and native rasterization. It does not execute shell commands, patch binaries, or replace Chromium's DOM engine.

### Frame transport

Define a Python-level frame sink contract with `write_rgba(frame_bytes, width, height)` and `close()`.

- Existing renderers keep writing canonical PNG frames by default.
- Explicit streaming mode sends raw RGBA frames to an FFmpeg stdin pipeline.
- Streaming is rejected or falls back to PNG when `resume=True`, checkpoint/recovery requires individual frames, or inspection explicitly requests PNG artifacts.
- Frame numbering, seeded randomness, CSS freeze behavior, and `__OMNIFRAME_*` payloads remain unchanged.

## FFmpeg pipeline

### Muxing

Extend `Compositor.mux_audio()` with an automatic video-copy mode:

- Probe video stream/container compatibility.
- Use `-map 0:v:0 -map 1:a:0 -c:v copy` when the existing video is compatible with the requested delivery preset.
- Encode only audio when possible.
- Fall back to the current video re-encode path for codec, container, pixel-format, or preset mismatches.
- Preserve `-shortest` and validate final duration/streams.

### Concatenation

Extend `concat_videos()` with `reencode="auto"` semantics:

- Use stream copy for compatible segments.
- Re-encode only when stream metadata differs.
- Keep explicit `reencode=True/False` escape hatches for agents.

### Raw frame streaming

Add a streaming path to `build_video_from_frames()` and the compositor API:

- raw input: `-f rawvideo -pix_fmt rgba -s WIDTHxHEIGHT -r FPS -i pipe:0`
- output codec and preset remain controlled by the existing export preset registry
- FFmpeg diagnostics stay on stderr
- Python fallback may write PNG frames if native pipe support is absent

The CLI exposes this only through an explicit `--stream-to-ffmpeg` option. Default behavior remains PNG-based.

## Cartoon native rasterization

The Python scene model remains authoritative. Before native execution, validated scene data is lowered to primitive arrays:

- canvas dimensions/background
- layer order, visibility, RGBA color/source classification
- position, scale, rotation, anchor, opacity
- keyframe values and easing
- frame range

The native implementation handles solid/vector layers, alpha blending, transforms, and supported keyframe interpolation. Unsupported image/text features or native errors use the Python/Pillow renderer for that frame or whole scene, with a structured warning.

Output must be deterministic against the Python fallback for the supported subset. Native image buffers must be consumable by the Python frame sink and optional FFmpeg pipe.

## Error and fallback behavior

- Native import errors are non-fatal and logged at debug/info level.
- Unsupported native inputs return a typed capability/fallback result, not a partial corrupted frame.
- FFmpeg stream failures close stdin, collect stderr, and raise the existing structured `RenderError` hierarchy.
- If streaming cannot preserve requested resume/checkpoint semantics, the operation fails closed with an actionable validation error rather than silently losing recovery artifacts.

## Testing

Add tests for:

1. native module unavailable: fallback imports and renders
2. native module available: capability and smoke test
3. native/fallback deterministic parity for supported cartoon primitives
4. raw RGBA stream produces expected frame count, dimensions, and duration
5. compatible mux uses video copy
6. incompatible mux uses the existing re-encode fallback
7. concat auto-copy and mismatch fallback
8. stream mode rejects or falls back for resume/inspection requirements
9. existing full suite remains green

Native tests must be skippable when no compiler or built extension is present; fallback tests must always run.

## Benchmark comparison

Re-run the exact `out/stress-test-60s/benchmark.py` workload after implementation and report:

- per-stage wall time and CPU time
- peak RSS per stage and maximum overall RSS
- frame count, output duration, codec streams
- PNG/intermediate disk footprint
- native vs fallback mode
- before/after deltas and any changed failure behavior

The benchmark harness and outputs remain under `out/`, which is ignored by Git.

## Non-goals

- Rewriting FFmpeg/libav in C++
- Replacing Chromium DOM execution for arbitrary HTML/CSS/JS
- Removing PNG output, resume, checkpoint, or inspection workflows
- Changing the OmniProject schema or agent action names
- Adding mandatory compiler/toolchain dependencies
- Pushing to GitHub or creating release tags
