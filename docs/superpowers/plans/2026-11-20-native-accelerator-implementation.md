# Native Accelerator and Zero-Reencode Pipeline Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add opt-in zero-reencode/streaming optimizations and an optional C++17/pybind11 accelerator while preserving the default Python/Pillow/PNG path and automatic fallback behavior.

**Architecture:** Keep Python as the authoritative orchestrator, schema owner, CLI/MCP surface, and fallback implementation. Add a small runtime capability layer under `src/omniframe/_native/`, an optional pybind11 extension under `cpp/`, and conservative FFmpeg auto-copy/streaming APIs. The native path is never mandatory and never changes default PNG/resume semantics.

**Tech Stack:** Python 3.10+, stdlib, Pillow, pydantic, PyYAML, Typer, pytest; optional Playwright; optional pybind11/C++17; FFmpeg/FFprobe subprocesses.

## Global Constraints

- Python-first hybrid; Windows 10/11 and PowerShell remain supported.
- Native extension is optional; missing compiler, pybind11, or built module must select Python fallback.
- Existing PNG rendering, checkpoint/resume, inspection, schemas, MCP actions, and DCC bridges remain compatible.
- Streaming is opt-in; default rendering continues to emit canonical PNG frames.
- No `shell=True`, secrets, DRM circumvention, proprietary binary patching, GitHub push, or release-tag operation.
- Native output must be deterministic for the supported primitive cartoon subset.
- FFmpeg/libav is reused; it is not rewritten in C++.
- Every code change receives the project security scan when the Aikido tool is available; if unavailable, report that limitation.

---

### Task 1: Add runtime native capability and fallback contracts

**Files:**
- Create: `src/omniframe/_native/__init__.py`
- Create: `src/omniframe/_native/loader.py`
- Create: `src/omniframe/_native/fallback.py`
- Modify: `src/omniframe/__init__.py`
- Modify: `src/omniframe/core/config.py`
- Modify: `src/omniframe/cli/main.py`
- Test: `tests/test_native_accelerator.py`

**Interfaces:**
- Produces `native_available() -> bool`, `native_status() -> dict[str, Any]`, and `get_frame_sink(...)`.
- Produces fallback `FramePipeSink` with `write_rgba(frame_bytes: bytes, width: int, height: int) -> None` and `close() -> None`.
- Produces `has_native_accelerator() -> bool` at the top-level package.
- `doctor` reports a `native_accelerator` capability without failing when the module is absent.

- [ ] **Step 1: Write fallback and loader tests**

```python
def test_native_status_is_nonfatal_without_extension():
    from omniframe._native import native_status
    status = native_status()
    assert status["mode"] in {"native", "fallback"}
    assert "available" in status


def test_fallback_frame_sink_writes_rgba_png(tmp_path):
    from omniframe._native.fallback import FramePipeSink
    sink = FramePipeSink(output_dir=tmp_path, fps=24, width=2, height=1)
    sink.write_rgba(bytes([255, 0, 0, 255, 0, 255, 0, 255]), 2, 1)
    sink.close()
    assert list(tmp_path.glob("frame_*.png"))
```

- [ ] **Step 2: Run the focused tests and confirm they fail**

Run: `python -m pytest tests/test_native_accelerator.py -q`

Expected: import/API failures because the native package does not exist yet.

- [ ] **Step 3: Implement safe loader and fallback sink**

`loader.py` must catch `ImportError`, `OSError`, and extension initialization errors. It returns a stable status such as:

```python
{"available": False, "mode": "fallback", "backend": "python", "reason": "native extension not installed"}
```

`fallback.py` uses Pillow only, creates deterministic `frame_%06d.png` output, increments frame number, validates RGBA byte length, and never invokes a shell.

- [ ] **Step 4: Wire top-level export and doctor capability**

Add `has_native_accelerator()` to `omniframe.__init__`. Add a capability entry in `detect_environment()` with `available`, `version`, `path`, `detail`, and `source` fields matching existing capability conventions. Add a JSON-safe doctor assertion.

- [ ] **Step 5: Run focused tests and doctor**

Run: `python -m pytest tests/test_native_accelerator.py -q`

Run: `omniframe doctor --json`

Expected: focused tests pass and the report includes native accelerator fallback status.

- [ ] **Step 6: Commit the isolated runtime-layer change**

```powershell
git add src/omniframe/_native src/omniframe/__init__.py src/omniframe/core/config.py src/omniframe/cli/main.py tests/test_native_accelerator.py
git commit -m "feat: add optional native accelerator capability layer"
```

---

### Task 2: Add optional C++17/pybind11 extension scaffolding

**Files:**
- Create: `cpp/omniframe_native.cpp`
- Create: `cpp/CMakeLists.txt`
- Create: `src/omniframe/_native/native_api.py`
- Modify: `pyproject.toml`
- Modify: `src/omniframe/_native/loader.py`
- Test: `tests/test_native_optional_build.py`

**Interfaces:**
- Native module exports `native_available()`, `FramePipeSink`, and `CartoonRasterizer`.
- Python loader imports `omniframe._native._omniframe_native` only when installed.
- Normal `pip install -e .` does not require a compiler or pybind11.

- [ ] **Step 1: Add tests that tolerate absent native builds**

```python
def test_native_import_is_optional():
    from omniframe._native import native_status
    status = native_status()
    assert status["mode"] in {"native", "fallback"}


def test_native_api_has_fallback_shape():
    from omniframe._native import native_api
    assert hasattr(native_api, "FramePipeSink")
    assert hasattr(native_api, "CartoonRasterizer")
```

- [ ] **Step 2: Implement the minimal C++ module**

Use C++17 and pybind11. `FramePipeSink` must accept bytes-like RGBA buffers, validate dimensions, and expose a GIL-released `write` operation. `CartoonRasterizer` initially exposes a deterministic `render_rgba(width, height, layers, frame) -> bytes` primitive solid/vector path; unsupported layer kinds return a typed unsupported result instead of corrupt output.

Do not execute commands from C++ and do not own FFmpeg process lifecycle inside the extension.

- [ ] **Step 3: Add optional packaging metadata**

Add a `[native]` extra containing `pybind11`. Keep setuptools build working without an extension. If a local compiler integration is not available through the current build backend, document the CMake/manual build path and keep runtime fallback fully functional rather than making the default build fail.

- [ ] **Step 4: Run fallback tests and optional compile detection**

Run: `python -m pytest tests/test_native_optional_build.py -q`

Run: `python -m pip install -e .`

Expected: package installation succeeds without a native compiler.

- [ ] **Step 5: Commit the optional extension scaffolding**

```powershell
git add cpp src/omniframe/_native/native_api.py pyproject.toml tests/test_native_optional_build.py
git commit -m "feat: add optional pybind11 accelerator scaffolding"
```

---

### Task 3: Implement FFmpeg raw-frame streaming

**Files:**
- Modify: `src/omniframe/engines/compositor/ffmpeg.py`
- Modify: `src/omniframe/engines/compositor/compositor.py`
- Modify: `src/omniframe/engines/code_video/backends.py`
- Modify: `src/omniframe/engines/code_video/renderer.py`
- Test: `tests/test_streaming_pipeline.py`

**Interfaces:**
- Add `stream_rgba_frames(frames: Iterable[bytes], output, width, height, fps, video_codec, ...) -> Path`.
- Add `stream_to_ffmpeg: bool = False` to the render/composition boundary without changing default behavior.
- Streaming rejects `resume=True` with a structured validation error.

- [ ] **Step 1: Write failing FFmpeg stream tests**

```python
def test_stream_rgba_frames_produces_expected_duration(tmp_path):
    frames = [bytes([255, 0, 0, 255]) * 4 for _ in range(4)]
    output = tmp_path / "stream.mp4"
    stream_rgba_frames(frames, output, width=2, height=2, fps=2)
    info = ffprobe_info(output)
    assert float(info["format"]["duration"]) == pytest.approx(2.0, abs=0.1)


def test_streaming_resume_fails_closed():
    with pytest.raises(ValidationError):
        render_scene(scene, tmp_path, stream_to_ffmpeg=True, resume=True)
```

- [ ] **Step 2: Run focused tests to verify failure**

Run: `python -m pytest tests/test_streaming_pipeline.py -q`

Expected: missing stream function/parameter failures.

- [ ] **Step 3: Implement safe stdin FFmpeg process handling**

Create the FFmpeg argv with `-hide_banner -nostdin -y -f rawvideo -pix_fmt rgba -s WIDTHxHEIGHT -r FPS -i pipe:0`. Use `subprocess.Popen` with binary stdin and captured stderr, write each frame with backpressure, close stdin, wait with timeout, and raise `RenderError` containing only bounded stderr tail. Never use `shell=True`.

- [ ] **Step 4: Wire opt-in compositor/backend behavior**

Keep PNG mode as default. For streaming, use the fallback sink or native sink, reject resume/checkpoint/inspection conflicts, and ensure `close()` is called in `finally` blocks. Preserve frame numbering and deterministic payload injection.

- [ ] **Step 5: Run streaming tests and a tiny CLI smoke test**

Run: `python -m pytest tests/test_streaming_pipeline.py -q`

Run: `omniframe project compose <small-project> --stream-to-ffmpeg ...`

Expected: expected duration and frame count; default PNG tests remain unchanged.

- [ ] **Step 6: Commit the streaming implementation**

```powershell
git add src/omniframe/engines/compositor/ffmpeg.py src/omniframe/engines/compositor/compositor.py src/omniframe/engines/code_video/backends.py src/omniframe/engines/code_video/renderer.py tests/test_streaming_pipeline.py
git commit -m "feat: add opt-in raw frame streaming to ffmpeg"
```

---

### Task 4: Add zero-reencode mux and concat selection

**Files:**
- Modify: `src/omniframe/engines/compositor/ffmpeg.py`
- Modify: `src/omniframe/engines/compositor/compositor.py`
- Test: `tests/test_zero_reencode.py`

**Interfaces:**
- Add `video_copy: bool | str = "auto"` to `mux_audio()`.
- Add `reencode: bool | str = "auto"` to `concat_videos()`.
- Add compatibility helpers returning structured reasons, e.g. `video_copy_compatible(video, preset) -> tuple[bool, str]`.

- [ ] **Step 1: Write tests for copy and fallback decisions**

```python
def test_compatible_mux_uses_video_copy(monkeypatch, tmp_path):
    calls = []
    monkeypatch.setattr(ffmpeg_module, "run_ffmpeg", lambda args: calls.append(args) or "")
    compositor.mux_audio("video.mp4", "audio.wav", tmp_path / "out.mp4", video_copy=True)
    assert "-c:v" in calls[0]
    assert calls[0][calls[0].index("-c:v") + 1] == "copy"


def test_auto_copy_falls_back_for_incompatible_stream(monkeypatch, tmp_path):
    monkeypatch.setattr(ffmpeg_module, "ffprobe_info", lambda path: {"streams": [{"codec_type": "video", "codec_name": "prores"}]})
    calls = []
    monkeypatch.setattr(ffmpeg_module, "run_ffmpeg", lambda args: calls.append(args) or "")
    compositor.mux_audio("video.mov", "audio.wav", tmp_path / "out.mp4", video_copy="auto")
    assert calls[0][calls[0].index("-c:v") + 1] != "copy"
```

- [ ] **Step 2: Run focused tests and confirm failures**

Run: `python -m pytest tests/test_zero_reencode.py -q`

Expected: signature/selection failures.

- [ ] **Step 3: Implement compatibility inspection**

Use `ffprobe_info()` stream/container metadata. Only copy when codec, pixel format, dimensions, frame rate, container, and preset are compatible. Return a reason for every false decision so agent logs explain why re-encoding occurred.

- [ ] **Step 4: Implement mux and concat auto-copy**

Build `-map` arguments explicitly. For compatible mux use `-c:v copy`; for concat use `-c copy` only when all segments match. Preserve explicit `True` and `False` overrides. Ensure target directories exist and existing RenderError handling remains active.

- [ ] **Step 5: Run tests and a real media smoke check**

Run: `python -m pytest tests/test_zero_reencode.py -q`

Run: `ffprobe` on a copied mux output and assert video duration, codec, and audio stream.

- [ ] **Step 6: Commit zero-reencode changes**

```powershell
git add src/omniframe/engines/compositor/ffmpeg.py src/omniframe/engines/compositor/compositor.py tests/test_zero_reencode.py
git commit -m "perf: avoid compatible video re-encoding"
```

---

### Task 5: Integrate native cartoon rasterizer with fallback

**Files:**
- Modify: `src/omniframe/engines/cartoon_2d/render.py`
- Modify: `src/omniframe/engines/cartoon_2d/scene.py`
- Modify: `src/omniframe/_native/native_api.py`
- Test: `tests/test_cartoon_native_parity.py`

**Interfaces:**
- Add `backend: str = "auto"` to `render_frame()` and `render_frames()`.
- `backend="native"` fails with a structured capability error if unsupported; `backend="auto"` falls back.
- Primitive scene lowering returns a stable list/dict representation used by both native and fallback tests.

- [ ] **Step 1: Write parity tests for solid/vector layers**

```python
def test_auto_backend_matches_python_for_supported_scene(tmp_path):
    python_path = render_frame(scene, 12, tmp_path / "python.png", backend="python")
    auto_path = render_frame(scene, 12, tmp_path / "auto.png", backend="auto")
    assert Image.open(python_path).size == Image.open(auto_path).size


def test_native_request_is_actionable_without_extension(tmp_path):
    with pytest.raises((EngineUnavailable, ValidationError)):
        render_frame(scene, 0, tmp_path / "native.png", backend="native")
```

- [ ] **Step 2: Run parity tests to establish the expected failure**

Run: `python -m pytest tests/test_cartoon_native_parity.py -q`

Expected: backend argument/API failures until integration is added.

- [ ] **Step 3: Implement scene lowering and supported-feature gate**

Lower only solid/vector/transform/opacity/keyframe primitives. Return `None` for image/text or unsupported effects so `auto` uses existing Pillow code. Keep Python easing as the reference for parity.

- [ ] **Step 4: Integrate native rasterizer and preserve PNG output**

Use native bytes only when the extension reports availability and the scene is supported. Convert native RGBA bytes to Pillow image for the existing sink, or pass them to the stream sink. Any native exception triggers fallback in `auto` and a typed error in `native` mode.

- [ ] **Step 5: Run parity and full cartoon tests**

Run: `python -m pytest tests/test_cartoon_native_parity.py tests/test_cartoon_2d.py -q`

Expected: fallback parity passes on machines without the extension.

- [ ] **Step 6: Commit native cartoon integration**

```powershell
git add src/omniframe/engines/cartoon_2d src/omniframe/_native/native_api.py tests/test_cartoon_native_parity.py
git commit -m "perf: add optional native cartoon rasterizer path"
```

---

### Task 6: Update CLI, docs, and benchmark harness

**Files:**
- Modify: `src/omniframe/cli/main.py`
- Modify: `README.md`
- Modify: `src/omniframe/agent/SKILL.md`
- Modify: `src/omniframe/agent/AGENT_GUIDE.md`
- Modify: `out/stress-test-60s/benchmark.py`
- Test: `tests/test_cli_optimizations.py`

**Interfaces:**
- CLI exposes `--stream-to-ffmpeg` only where frame output can be streamed.
- CLI exposes native backend/status without changing existing action names.
- Benchmark report records `native_mode`, `stream_mode`, copy/reencode decisions, and disk footprint.

- [ ] **Step 1: Add CLI contract tests**

```python
def test_project_render_help_mentions_streaming():
    result = runner.invoke(app, ["project", "render", "--help"])
    assert "stream" in result.stdout.lower()


def test_doctor_json_contains_native_capability():
    result = runner.invoke(app, ["doctor", "--json"])
    assert "native_accelerator" in result.stdout
```

- [ ] **Step 2: Implement CLI options and documentation**

Add opt-in flags with explicit help text explaining that resume/inspection requires PNG frames. Update README and agent docs with native installation, fallback behavior, and streaming examples.

- [ ] **Step 3: Extend benchmark harness**

Record baseline-compatible fields plus native/fallback mode, `stream_mode`, output stream metadata, and file sizes. Keep all generated outputs inside `out/`.

- [ ] **Step 4: Run CLI/docs tests**

Run: `python -m pytest tests/test_cli_optimizations.py -q`

- [ ] **Step 5: Commit CLI/docs changes**

```powershell
git add src/omniframe/cli/main.py README.md src/omniframe/agent/SKILL.md src/omniframe/agent/AGENT_GUIDE.md out/stress-test-60s/benchmark.py tests/test_cli_optimizations.py
git commit -m "docs: expose native and streaming optimization controls"
```

---

### Task 7: Full verification and before/after benchmark

**Files:**
- Modify: `out/stress-test-60s/benchmark-report.json`
- Create: `out/stress-test-60s/benchmark-report-optimized.json`
- Create: `out/stress-test-60s/before-after.json`

**Interfaces:**
- Produces a machine-readable before/after comparison without modifying tracked source outputs.
- Confirms native mode or fallback mode explicitly.

- [ ] **Step 1: Run the complete test suite**

Run: `python -m pytest -q`

Expected: all existing and new tests pass; native-only tests skip cleanly if no compiler/module is installed.

- [ ] **Step 2: Run fallback benchmark**

Run: `python out/stress-test-60s/benchmark.py --backend python --stream false`

Expected: valid 60-second output and report with fallback mode.

- [ ] **Step 3: Run optimized streaming benchmark**

Run: `python out/stress-test-60s/benchmark.py --backend auto --stream true`

Expected: valid 60-second output, copy/reencode decisions, native/fallback mode, and reduced PNG footprint when streaming is active.

- [ ] **Step 4: Probe final media**

Run: `ffprobe -v error -show_entries stream=codec_type,codec_name,width,height,r_frame_rate,duration -of json out/stress-test-60s/final-stress-test.mp4`

Expected: 1280x720 H.264 video, AAC audio, 24 fps, 60-second duration.

- [ ] **Step 5: Compare metrics**

Compute per-stage wall delta, CPU delta, peak RSS delta, frame count, and disk delta. If native compiler is absent, report the optimized Python fallback separately and do not claim native speedup.

- [ ] **Step 6: Run whitespace and repository checks**

Run: `git diff --check`

Run: `git status --short`

Confirm no GitHub push or release-tag operation occurred and all generated media remains under ignored `out/`.

- [ ] **Step 7: Commit only source/test/report changes if requested**

Do not push. Do not create release tags. Keep generated media under `out/`; only commit the benchmark comparison JSON if it is intentionally part of the repository deliverable.
