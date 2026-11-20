from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import Any, Callable

import psutil

from omniframe._native import native_status
from omniframe.core.timeline_schema.io import load_project
from omniframe.engines.cartoon_2d import CartoonScene, render_frames
from omniframe.engines.code_video import CodeScene, CodeVideoRenderer
from omniframe.engines.compositor import AudioTrack, Compositor
from omniframe.engines.compositor.ffmpeg import concat_copy_compatible, ffprobe_info, video_copy_compatible

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).resolve().parent
PROJECT = OUT / "project.json"
FPS = 24
WIDTH = 1280
HEIGHT = 720
DURATION_FRAMES = 60 * FPS


def descendants(proc: psutil.Process) -> list[psutil.Process]:
    try:
        return [proc, *proc.children(recursive=True)]
    except (psutil.NoSuchProcess, psutil.AccessDenied):
        return [proc]


def proc_snapshot(proc: psutil.Process) -> dict[str, float]:
    rss = cpu = read_bytes = write_bytes = 0.0
    for child in descendants(proc):
        try:
            mem = child.memory_info()
            rss += float(mem.rss)
            times = child.cpu_times()
            cpu += float(times.user + times.system)
            io = child.io_counters()
            read_bytes += float(io.read_bytes)
            write_bytes += float(io.write_bytes)
        except (psutil.NoSuchProcess, psutil.AccessDenied, AttributeError):
            continue
    return {"rss": rss, "cpu": cpu, "read_bytes": read_bytes, "write_bytes": write_bytes}


class Sampler:
    def __init__(self) -> None:
        self.proc = psutil.Process(os.getpid())
        self.started = proc_snapshot(self.proc)
        self.peak_rss = self.started["rss"]
        self.max_cpu = self.started["cpu"]
        self.samples = 0
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._run, daemon=True)

    def _run(self) -> None:
        while not self._stop.is_set():
            snap = proc_snapshot(self.proc)
            self.peak_rss = max(self.peak_rss, snap["rss"])
            self.max_cpu = max(self.max_cpu, snap["cpu"])
            self.samples += 1
            self._stop.wait(0.1)

    def __enter__(self) -> "Sampler":
        self._thread.start()
        return self

    def __exit__(self, *_: object) -> None:
        self._stop.set()
        self._thread.join(timeout=2)
        snap = proc_snapshot(self.proc)
        self.peak_rss = max(self.peak_rss, snap["rss"])
        self.max_cpu = max(self.max_cpu, snap["cpu"])
        self.ended = snap

    def metrics(self, elapsed: float) -> dict[str, Any]:
        ended = getattr(self, "ended", proc_snapshot(self.proc))
        return {
            "wall_seconds": round(elapsed, 3),
            "cpu_seconds": round(max(0.0, self.max_cpu - self.started["cpu"]), 3),
            "cpu_pct_one_core": round(max(0.0, self.max_cpu - self.started["cpu"]) / elapsed * 100, 1) if elapsed else 0.0,
            "peak_rss_mb": round(self.peak_rss / 1024 / 1024, 1),
            "io_read_mb": round(max(0.0, ended["read_bytes"] - self.started["read_bytes"]) / 1024 / 1024, 1),
            "io_write_mb": round(max(0.0, ended["write_bytes"] - self.started["write_bytes"]) / 1024 / 1024, 1),
            "samples": self.samples,
        }


def run_command(name: str, args: list[str], *, timeout: int = 3600) -> dict[str, Any]:
    log_dir = OUT / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    stdout_path = log_dir / f"{name}.stdout.log"
    stderr_path = log_dir / f"{name}.stderr.log"
    start = time.perf_counter()
    with stdout_path.open("w", encoding="utf-8") as stdout, stderr_path.open("w", encoding="utf-8") as stderr:
        with Sampler() as sampler:
            proc = subprocess.Popen(args, cwd=ROOT, stdout=stdout, stderr=stderr)
            try:
                returncode = proc.wait(timeout=timeout)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait()
                returncode = 124
    elapsed = time.perf_counter() - start
    result = {"name": name, "command": args, "returncode": returncode, **sampler.metrics(elapsed)}
    result["stdout_log"] = str(stdout_path.relative_to(ROOT))
    result["stderr_log"] = str(stderr_path.relative_to(ROOT))
    if returncode != 0:
        result["stderr_tail"] = stderr_path.read_text(encoding="utf-8", errors="replace")[-4000:]
        raise RuntimeError(json.dumps(result, indent=2))
    return result


def run_direct(name: str, operation: Callable[[], Any]) -> tuple[dict[str, Any], Any]:
    start = time.perf_counter()
    value: Any = None
    error: BaseException | None = None
    with Sampler() as sampler:
        try:
            value = operation()
        except BaseException as exc:  # preserve benchmark failure details
            error = exc
    elapsed = time.perf_counter() - start
    result = {"name": name, **sampler.metrics(elapsed)}
    if error is not None:
        result["error"] = repr(error)
        raise error
    return result, value


def write_project() -> None:
    source = ROOT / "examples" / "full-studio-demo" / "project.json"
    doc = json.loads(source.read_text(encoding="utf-8"))
    doc["meta"].update({"name": "stress-test-60s", "fps": FPS, "width": WIDTH, "height": HEIGHT, "duration_frames": DURATION_FRAMES})
    for track in doc["tracks"]:
        if track["id"] == "code-1":
            clip = track["clips"][0]
            clip["id"] = "code-30s"
            clip["name"] = "30-second code-driven scene"
            clip["start_frame"] = 0
            clip["duration_frames"] = 30 * FPS
            clip["code"]["params"] = {"stress_profile": True, "segment": "code"}
        elif track["id"] == "cartoon-1":
            clip = track["clips"][0]
            clip["id"] = "cartoon-30s"
            clip["name"] = "30-second 2D cartoon scene"
            # Cartoon keyframes are local to the clip; keep the clip at frame 0
            # so the semantic validator accepts the existing 0..47 keyframes.
            clip["start_frame"] = 0
            clip["duration_frames"] = 30 * FPS
            clip["cartoon"]["width"] = WIDTH
            clip["cartoon"]["height"] = HEIGHT
        elif track["id"] == "audio-1":
            track["clips"] = []
    doc["shots"][0].update({"end_frame": DURATION_FRAMES, "description": "60-second code-video plus cartoon stress test"})
    doc["render_targets"][0].update({"path": str(OUT / "final-stress-test.mp4"), "fps": FPS, "width": WIDTH, "height": HEIGHT})
    PROJECT.write_text(json.dumps(doc, indent=2), encoding="utf-8")


def _find_clip(project: Any, clip_id: str) -> Any:
    for track in project.sorted_tracks():
        for clip in track.sorted_clips():
            if clip.id == clip_id:
                return clip
    raise ValueError(f"benchmark clip not found: {clip_id}")


def render_streaming_segments(project: Any, code_video: Path, cartoon_video: Path, backend: str) -> list[dict[str, Any]]:
    """Render both 30-second clips directly into FFmpeg raw-video pipes."""

    stages: list[dict[str, Any]] = []
    code_clip = _find_clip(project, "code-30s")
    if code_clip.code is None:
        raise ValueError("code benchmark clip has no code payload")
    code_scene = CodeScene(
        html=code_clip.code.html,
        css=code_clip.code.css,
        javascript=code_clip.code.javascript,
        bootstrap=code_clip.code.bootstrap,
        width=WIDTH,
        height=HEIGHT,
        fps=FPS,
        duration_frames=code_clip.duration_frames,
        seed=code_clip.code.seed,
        transparent=code_clip.code.transparent,
        background=code_clip.code.background,
        params=code_clip.code.params,
        settle_timeout_ms=code_clip.code.settle_timeout_ms,
    )
    metric, result = run_direct(
        "render_code_stream",
        lambda: CodeVideoRenderer(backend=backend).render(
            code_scene,
            OUT / "stream-frames" / "code-30s",
            stream_to_ffmpeg=code_video,
        ),
    )
    metric["backend"] = result.backend
    metric["stream_output"] = result.stream_output
    stages.append(metric)

    cartoon_clip = _find_clip(project, "cartoon-30s")
    cartoon = CartoonScene.from_spec(cartoon_clip.cartoon)
    cartoon.fps = FPS
    cartoon.duration_frames = cartoon_clip.duration_frames
    metric, paths = run_direct(
        "render_cartoon_stream",
        lambda: render_frames(
            cartoon,
            OUT / "stream-frames" / "cartoon-30s",
            backend="auto",
            stream_to_ffmpeg=cartoon_video,
        ),
    )
    metric["backend"] = "native" if native_status().get("available") else "python-fallback"
    metric["stream_output"] = str(cartoon_video)
    metric["rendered_png_frames"] = len(paths)
    stages.append(metric)
    return stages


def disk_footprint() -> dict[str, Any]:
    png_bytes = sum(path.stat().st_size for path in OUT.rglob("*.png") if path.is_file())
    frame_count = sum(1 for path in OUT.rglob("frame_*.png") if path.is_file())
    return {"png_bytes": png_bytes, "png_mib": round(png_bytes / 1024 / 1024, 3), "png_frame_count": frame_count}


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the exact OmniFrame 60-second stress benchmark.")
    parser.add_argument("--backend", choices=["auto", "python", "playwright", "stub"], default="auto")
    parser.add_argument("--stream", choices=["true", "false"], default="false")
    args = parser.parse_args()
    stream_mode = args.stream.lower() == "true"
    render_backend = "stub" if args.backend == "python" else args.backend
    OUT.mkdir(parents=True, exist_ok=True)
    for directory in [OUT / "frames", OUT / "segments", OUT / "inspect", OUT / "logs"]:
        if directory.exists():
            shutil.rmtree(directory)
        directory.mkdir(parents=True, exist_ok=True)
    write_project()

    stages: list[dict[str, Any]] = []
    stages.append(run_command("validate", ["omniframe", "project", "validate", str(PROJECT)]))

    compositor = Compositor()
    code_video = OUT / "segments" / "code-30s.mp4"
    cartoon_video = OUT / "segments" / "cartoon-30s.mp4"
    project = load_project(PROJECT)
    if stream_mode:
        stages.extend(render_streaming_segments(project, code_video, cartoon_video, render_backend))
    else:
        stages.append(run_command("render", ["omniframe", "project", "render", str(PROJECT), "--out", str(OUT / "frames"), "--backend", render_backend], timeout=3600))
        stages.append(run_command("compose_code", ["omniframe", "project", "compose", str(PROJECT), "--frames", str(OUT / "frames" / "code-30s"), "--out", str(code_video)], timeout=900))
        stages.append(run_command("compose_cartoon", ["omniframe", "project", "compose", str(PROJECT), "--frames", str(OUT / "frames" / "cartoon-30s"), "--out", str(cartoon_video)], timeout=900))

    concat_path = OUT / "segments" / "video-no-audio.mp4"
    concat_ok, concat_reason = concat_copy_compatible([code_video, cartoon_video], "h264")
    metric, _ = run_direct("concat_segments", lambda: compositor.concat_videos([code_video, cartoon_video], concat_path, preset="h264", reencode="auto"))
    metric.update({"video_copy": concat_ok, "video_copy_reason": concat_reason})
    stages.append(metric)

    # Generate deterministic local audio with FFmpeg, then exercise the compositor's
    # mix/ducking and mux APIs without relying on external assets.
    music = OUT / "music.wav"
    sfx = OUT / "sfx.wav"
    stages.append(run_command("generate_music", ["ffmpeg", "-y", "-f", "lavfi", "-i", "sine=frequency=220:duration=60", "-c:a", "pcm_s16le", str(music)], timeout=300))
    stages.append(run_command("generate_sfx", ["ffmpeg", "-y", "-f", "lavfi", "-i", "sine=frequency=880:duration=1", "-af", "apad=pad_dur=59", "-t", "60", "-c:a", "pcm_s16le", str(sfx)], timeout=300))

    mixed_audio = OUT / "mixed-audio.wav"
    metric, _ = run_direct(
        "mix_audio",
        lambda: compositor.mix_audio(
            [
                AudioTrack(str(music), volume=0.22, fade_in_frames=24, fade_out_frames=24, duck_under=["sfx"], normalization="peak", name="music"),
                AudioTrack(str(sfx), volume=0.85, start_frame=30 * FPS, name="sfx"),
            ],
            mixed_audio,
            fps=FPS,
            duration=60.0,
        ),
    )
    stages.append(metric)

    final_video = OUT / "final-stress-test.mp4"
    mux_ok, mux_reason = video_copy_compatible(concat_path, "h264")
    metric, _ = run_direct(
        "mux_audio",
        lambda: compositor.mux_audio(concat_path, mixed_audio, final_video, preset="h264", video_copy="auto"),
    )
    metric.update({"video_copy": mux_ok, "video_copy_reason": mux_reason})
    stages.append(metric)

    stages.append(run_command("inspect_media", ["omniframe", "inspect", "media", "--video", str(final_video), "--output-dir", str(OUT / "inspect"), "--count", "12", "--contact-sheet", str(OUT / "inspect" / "contact-sheet.png")], timeout=900))
    stages.append(run_command("ffprobe", ["ffprobe", "-v", "error", "-show_entries", "format=duration,size", "-of", "json", str(final_video)], timeout=60))

    frame_files = list((OUT / "frames").rglob("*.png"))
    report = {
        "project": str(PROJECT.relative_to(ROOT)),
        "duration_seconds": 60,
        "fps": FPS,
        "resolution": [WIDTH, HEIGHT],
        "total_timeline_frames": DURATION_FRAMES,
        "rendered_png_frames": len(frame_files),
        "final_video": str(final_video.relative_to(ROOT)),
        "final_video_bytes": final_video.stat().st_size,
        "contact_sheet": str((OUT / "inspect" / "contact-sheet.png").relative_to(ROOT)),
        "native_mode": native_status(),
        "stream_mode": stream_mode,
        "requested_backend": args.backend,
        "resolved_code_backend": render_backend,
        "concat_copy": {"compatible": concat_ok, "reason": concat_reason},
        "mux_copy": {"compatible": mux_ok, "reason": mux_reason},
        "disk_footprint": disk_footprint(),
        "output_streams": ffprobe_info(final_video).get("streams", []),
        "stages": stages,
        "notes": [
            "PNG mode is the baseline-compatible default; stream=true skips frame PNG files.",
            "Native acceleration is optional and the report records fallback mode explicitly.",
            "Compatible segments/mux inputs use FFmpeg stream copy; incompatible inputs re-encode.",
            "Audio mixed with peak normalization and side-chain ducking, then muxed.",
            "Resource metrics are process-plus-descendant RSS/CPU/I/O samples at 100ms intervals.",
        ],
    }
    (OUT / "benchmark-report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
