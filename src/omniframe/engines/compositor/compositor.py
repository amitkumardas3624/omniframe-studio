"""The master compositor: assembly, mixing, subtitles and delivery."""

from __future__ import annotations

import shutil
import tempfile
from collections.abc import Iterable, Sequence
from pathlib import Path
from typing import Any

from ...core.errors import ValidationError
from ...core.logging import get_logger
from .artifact import write_artifact_manifest
from .audio import AudioTrack, SubtitleTrack, mix_audio
from .ffmpeg import (
    build_video_from_frames,
    concat_copy_compatible,
    escape_filter_path,
    run_ffmpeg,
    stream_rgba_frames,
    video_copy_compatible,
    write_concat_list,
)
from .presets import ExportPreset, get_preset

LOG = get_logger("engines.compositor.compositor")


class Compositor:
    """Assemble and deliver the final video.

    Every method returns the path of the produced file.
    """

    def __init__(self, *, ffmpeg: str | None = None, overwrite: bool = True) -> None:
        self.ffmpeg = ffmpeg
        self.overwrite = overwrite

    # -- helpers --------------------------------------------------------
    def _target(self, output: str | Path) -> Path:
        target = Path(output)
        target.parent.mkdir(parents=True, exist_ok=True)
        return target

    def _emit_manifest(
        self,
        output: str | Path,
        *,
        tool: str,
        preset: str | None = None,
        extra_inputs: Sequence[str | Path] = (),
    ) -> None:
        """Write a per-delivery artifact manifest next to ``output``.

        Only regular-file outputs receive a manifest: directory deliveries
        (such as a ``png_sequence`` frame set) have no single artifact to hash
        and are skipped so existing behaviour is preserved.
        """
        target = Path(output)
        if not target.is_file():
            LOG.info(
                "skipping artifact manifest: output is not a file",
                extra={"tool": tool, "output": str(target)},
            )
            return
        write_artifact_manifest(
            target,
            tool=tool,
            preset=preset,
            extra_inputs=extra_inputs,
        )

    # -- video ----------------------------------------------------------
    def frames_to_video(
        self,
        frames: Sequence[str | Path],
        output: str | Path,
        *,
        fps: float = 30.0,
        preset: str = "h264",
        background: str | None = None,
        transparent: bool = False,
        crf: int | None = None,
        bitrate: str | None = None,
    ) -> Path:
        """Assemble PNG frames into a video."""

        if not frames:
            raise ValidationError("frames_to_video requires at least one frame.")

        chosen: ExportPreset = get_preset(preset)
        target = self._target(output)

        if chosen.name == "png_sequence":
            result = self._png_sequence(frames, target, fps=fps)
            self._emit_manifest(
                target,
                tool="frames_to_video",
                preset=chosen.name,
                extra_inputs=frames,
            )
            return result

        result = build_video_from_frames(
            frames,
            target,
            fps=fps,
            video_codec=chosen.video_codec,
            audio_codec=chosen.audio_codec,
            extra_args=chosen.extra_args,
            crf=crf,
            bitrate=bitrate,
            background=background,
            transparent=transparent or chosen.supports_transparency and transparent,
        )
        self._emit_manifest(
            target,
            tool="frames_to_video",
            preset=chosen.name,
            extra_inputs=frames,
        )
        return result

    def raw_frames_to_video(
        self,
        frames: Iterable[bytes],
        output: str | Path,
        *,
        width: int,
        height: int,
        fps: float = 30.0,
        preset: str = "h264",
    ) -> Path:
        """Stream raw RGBA frames directly to FFmpeg."""

        chosen = get_preset(preset)
        if chosen.name == "png_sequence":
            raise ValidationError("png_sequence preset cannot consume a raw RGBA stream")
        target = self._target(output)
        return stream_rgba_frames(
            frames,
            target,
            width=width,
            height=height,
            fps=fps,
            video_codec=chosen.video_codec,
            extra_args=chosen.extra_args,
        )

    def _png_sequence(
        self, frames: Sequence[str | Path], target: Path, *, fps: float
    ) -> Path:
        """Write the frames as a numbered PNG sequence next to ``target``."""

        target.mkdir(parents=True, exist_ok=True)
        tmp_dir = Path(tempfile.mkdtemp(prefix="omniframe-pngseq-"))
        try:
            list_file = tmp_dir / "frames.txt"
            write_concat_list(frames, list_file, fps)
            pattern = str(target / "frame_%06d.png")
            run_ffmpeg(
                ["-f", "concat", "-safe", "0", "-i", str(list_file),
                 "-vsync", "0", pattern]
            )
        finally:
            shutil.rmtree(tmp_dir, ignore_errors=True)
        return target

    def concat_videos(
        self,
        videos: Sequence[str | Path],
        output: str | Path,
        *,
        preset: str = "h264",
        reencode: bool | str = "auto",
    ) -> Path:
        """Concatenate videos in the given order."""

        if not videos:
            raise ValidationError("concat_videos requires at least one video.")

        chosen = get_preset(preset)
        target = self._target(output)
        tmp_dir = Path(tempfile.mkdtemp(prefix="omniframe-concat-"))
        try:
            list_file = tmp_dir / "videos.txt"
            lines: list[str] = []
            for video in videos:
                absolute = Path(video).resolve()
                escaped = str(absolute).replace("\\", "/").replace("'", r"\'")
                lines.append(f"file '{escaped}'")
            list_file.write_text("\n".join(lines) + "\n", encoding="utf-8")

            if reencode not in {True, False, "auto"}:
                raise ValidationError("reencode must be True, False, or 'auto'", reencode=reencode)
            use_copy = reencode is False
            reason = "explicit reencode=False"
            if reencode == "auto":
                use_copy, reason = concat_copy_compatible(videos, chosen)
            LOG.info("concat codec decision", extra={"copy": use_copy, "reason": reason})

            args = ["-f", "concat", "-safe", "0", "-i", str(list_file)]
            if use_copy:
                args += ["-c", "copy"]
            else:
                args += ["-c:v", chosen.video_codec]
                if chosen.audio_codec != "none":
                    args += ["-c:a", chosen.audio_codec]
                args += list(chosen.extra_args)
            args += [str(target)]
            run_ffmpeg(args)
        finally:
            shutil.rmtree(tmp_dir, ignore_errors=True)
        self._emit_manifest(
            target,
            tool="concat_videos",
            preset=chosen.name,
            extra_inputs=list(videos),
        )
        return target

    # -- audio ----------------------------------------------------------
    def mix_audio(
        self,
        tracks: Sequence[AudioTrack],
        output: str | Path,
        *,
        fps: float = 30.0,
        duration: float | None = None,
    ) -> Path:
        """Mix audio tracks into a WAV intermediate."""

        result = mix_audio(tracks, output, fps=fps, duration=duration)
        self._emit_manifest(
            result,
            tool="mix_audio",
            preset=None,
            extra_inputs=[track.path for track in tracks],
        )
        return result

    def mux_audio(
        self,
        video: str | Path,
        audio: str | Path,
        output: str | Path,
        *,
        preset: str = "h264",
        video_copy: bool | str = "auto",
    ) -> Path:
        """Combine a video and an audio file into the delivery format."""

        chosen = get_preset(preset)
        target = self._target(output)
        if video_copy not in {True, False, "auto"}:
            raise ValidationError("video_copy must be True, False, or 'auto'", video_copy=video_copy)
        if video_copy is True:
            use_copy, reason = True, "explicit video_copy=True"
        elif video_copy is False:
            use_copy, reason = False, "explicit video_copy=False"
        else:
            use_copy, reason = video_copy_compatible(video, chosen)
        LOG.info("mux video codec decision", extra={"copy": use_copy, "reason": reason})

        args = ["-i", str(video), "-i", str(audio), "-map", "0:v:0", "-map", "1:a:0"]
        args += ["-c:v", "copy" if use_copy else chosen.video_codec]
        if chosen.audio_codec != "none":
            args += ["-c:a", chosen.audio_codec]
        else:
            args += ["-an"]
        if not use_copy:
            args += list(chosen.extra_args)
        args += ["-shortest", str(target)]
        run_ffmpeg(args)
        self._emit_manifest(
            target,
            tool="mux_audio",
            preset=chosen.name,
            extra_inputs=(video, audio),
        )
        return target

    def extract_audio(self, video: str | Path, output: str | Path) -> Path:
        """Extract the audio stream of a video as WAV."""

        target = self._target(output)
        run_ffmpeg(["-i", str(video), "-vn", "-c:a", "pcm_s16le", str(target)])
        self._emit_manifest(target, tool="extract_audio", preset=None, extra_inputs=(video,))
        return target

    # -- subtitles ------------------------------------------------------
    def burn_subtitles(
        self,
        video: str | Path,
        subtitle: str | Path,
        output: str | Path,
        *,
        preset: str = "h264",
    ) -> Path:
        """Burn a subtitle file into the picture."""

        subtitle_path = Path(subtitle)
        if not subtitle_path.exists():
            raise ValidationError(f"Subtitle file not found: {subtitle_path}")

        chosen = get_preset(preset)
        target = self._target(output)
        escaped = escape_filter_path(subtitle_path.resolve())
        args = [
            "-i", str(video),
            "-vf", f"subtitles=filename='{escaped}'",
            "-c:v", chosen.video_codec,
        ]
        if chosen.audio_codec != "none":
            args += ["-c:a", chosen.audio_codec, "-c:s", "mov_text"]
        args += list(chosen.extra_args)
        args += [str(target)]
        run_ffmpeg(args)
        self._emit_manifest(
            target,
            tool="burn_subtitles",
            preset=chosen.name,
            extra_inputs=(video, subtitle),
        )
        return target

    def export_subtitles(self, subtitle: str | Path, output: str | Path) -> Path:
        """Copy a subtitle file next to the delivery (soft subtitles)."""

        source = Path(subtitle)
        if not source.exists():
            raise ValidationError(f"Subtitle file not found: {source}")
        target = self._target(output)
        shutil.copyfile(source, target)
        return target

    # -- colour ---------------------------------------------------------
    def apply_lut(
        self,
        video: str | Path,
        lut_path: str | Path,
        output: str | Path,
        *,
        preset: str = "h264",
    ) -> Path:
        """Apply a 3D LUT to a video."""

        lut = Path(lut_path)
        if not lut.exists():
            raise ValidationError(f"LUT file not found: {lut}")

        chosen = get_preset(preset)
        target = self._target(output)
        escaped = escape_filter_path(lut.resolve())
        args = [
            "-i", str(video),
            "-vf", f"lut3d=file='{escaped}'",
            "-c:v", chosen.video_codec,
        ]
        if chosen.audio_codec != "none":
            args += ["-c:a", chosen.audio_codec]
        args += list(chosen.extra_args)
        args += [str(target)]
        run_ffmpeg(args)
        self._emit_manifest(
            target,
            tool="apply_lut",
            preset=chosen.name,
            extra_inputs=(video, lut_path),
        )
        return target

    def scale_video(
        self,
        video: str | Path,
        output: str | Path,
        *,
        width: int,
        height: int,
        preset: str = "h264",
    ) -> Path:
        """Rescale a video to an exact frame size."""

        chosen = get_preset(preset)
        target = self._target(output)
        args = [
            "-i", str(video),
            "-vf", f"scale={int(width)}:{int(height)}",
            "-c:v", chosen.video_codec,
        ]
        if chosen.audio_codec != "none":
            args += ["-c:a", chosen.audio_codec]
        args += list(chosen.extra_args)
        args += [str(target)]
        run_ffmpeg(args)
        self._emit_manifest(
            target,
            tool="scale_video",
            preset=chosen.name,
            extra_inputs=(video,),
        )
        return target

    # -- project --------------------------------------------------------
    def render_project(
        self,
        project: Any,
        output: str | Path,
        *,
        preset: str = "h264",
        subtitle_tracks: Sequence[SubtitleTrack] | None = None,
        audio_tracks: Sequence[AudioTrack] | None = None,
    ) -> Path:
        """Render a whole project into a delivery file."""

        target = self._target(output)
        fps = float(project.meta.fps)

        render_target = project.render_targets[0] if project.render_targets else None
        if render_target is not None:
            preset = _preset_for(render_target, preset)

        media = self._collect_media(project)
        tmp_dir = Path(tempfile.mkdtemp(prefix="omniframe-project-"))
        try:
            video_path: Path | None = None
            if media:
                video_path = tmp_dir / "timeline.mp4"
                self.concat_videos(media, video_path, preset="h264")
            elif render_target is not None and Path(render_target.path).exists():
                video_path = Path(render_target.path)

            if video_path is None:
                raise ValidationError(
                    "The project has no media clips to render. Render the code or cartoon "
                    "scenes first, or point the render target at an existing file.",
                    project=project.meta.name,
                )

            current = video_path

            if audio_tracks:
                wav = tmp_dir / "mix.wav"
                mix_audio(list(audio_tracks), wav, fps=fps)
                current = self.mux_audio(current, wav, tmp_dir / "muxed.mp4", preset=preset)

            for subtitle in subtitle_tracks or []:
                if subtitle.burn:
                    current = self.burn_subtitles(
                        current, subtitle.path, tmp_dir / "subbed.mp4", preset=preset
                    )

            if render_target is not None:
                if render_target.width and render_target.height:
                    current = self.scale_video(
                        current,
                        tmp_dir / "scaled.mp4",
                        width=render_target.width,
                        height=render_target.height,
                        preset=preset,
                    )
                if render_target.extra_args:
                    extra = tmp_dir / "extra.mp4"
                    run_ffmpeg(
                        ["-i", str(current), "-c", "copy", *render_target.extra_args, str(extra)]
                    )
                    current = extra

            shutil.copyfile(current, target)
        finally:
            shutil.rmtree(tmp_dir, ignore_errors=True)

        LOG.info("project rendered", extra={"output": str(target)})
        project_inputs: list[str | Path] = list(media)
        if audio_tracks:
            project_inputs += [track.path for track in audio_tracks]
        if subtitle_tracks:
            project_inputs += [track.path for track in subtitle_tracks]
        self._emit_manifest(
            target,
            tool="render_project",
            preset=preset,
            extra_inputs=project_inputs,
        )
        return target

    # -- internals ------------------------------------------------------
    @staticmethod
    def _collect_media(project: Any) -> list[Path]:
        """Every media source referenced by the project, in timeline order."""

        from ...core.timeline_schema.models import TrackKind

        media: list[Path] = []
        for track in project.sorted_tracks():
            if track.kind == TrackKind.AUDIO:
                continue
            for clip in track.sorted_clips():
                if not clip.source:
                    continue
                path = Path(clip.source)
                if path.exists():
                    media.append(path)
        return media


def _preset_for(render_target: Any, fallback: str) -> str:
    """Map a render target onto one of the built-in presets."""

    mapping = {
        ("mp4", "h264"): "h264",
        ("mp4", "hevc"): "h265",
        ("mov", "prores"): "prores",
        ("mov", "prores_ks"): "prores",
        ("webm", "libvpx-vp9"): "webm",
        ("gif", "gif"): "gif",
        ("mov", "qtrle"): "qtrle_alpha",
        ("image2", "png"): "png_sequence",
    }
    key = (str(render_target.container).lower(), str(render_target.video_codec).lower())
    return mapping.get(key, fallback)
