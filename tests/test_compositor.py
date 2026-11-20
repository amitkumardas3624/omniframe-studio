"""Tests for the FFmpeg compositor."""

from __future__ import annotations

import wave

import pytest

from omniframe.core.errors import ValidationError
from omniframe.engines.compositor import (
    AudioTrack,
    Compositor,
    ffmpeg_available,
    get_preset,
    list_presets,
)

pytestmark = pytest.mark.skipif(not ffmpeg_available(), reason="ffmpeg is not installed")


def make_frames(tmp_path, count: int = 6, size=(64, 36)):
    from PIL import Image

    frames = []
    for index in range(count):
        path = tmp_path / f"frame_{index:06d}.png"
        Image.new("RGBA", size, (index * 20 % 255, 60, 120, 255)).save(path)
        frames.append(path)
    return frames


def make_wav(path, seconds: float = 0.5, rate: int = 48000):
    import struct

    frames = int(rate * seconds)
    with wave.open(str(path), "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(rate)
        handle.writeframes(
            b"".join(struct.pack("<h", (i * 100) % 20000) for i in range(frames))
        )
    return path


class TestPresets:
    def test_expected_presets_exist(self):
        names = {preset["name"] for preset in list_presets()}
        assert {"h264", "h265", "prores", "webm", "png_sequence"} <= names

    def test_unknown_preset_raises(self):
        with pytest.raises(ValidationError):
            get_preset("does-not-exist")

    def test_preset_details(self):
        preset = get_preset("h264")
        assert preset.container == "mp4"
        assert preset.video_codec == "libx264"


class TestVideo:
    def test_frames_to_video(self, tmp_path):
        frames = make_frames(tmp_path)
        out = Compositor().frames_to_video(frames, tmp_path / "out.mp4", fps=6)
        assert out.exists() and out.stat().st_size > 0

    def test_probe_reports_codec_and_duration(self, tmp_path):
        from omniframe.engines.compositor import ffprobe_info

        frames = make_frames(tmp_path)
        out = Compositor().frames_to_video(frames, tmp_path / "out.mp4", fps=6)
        info = ffprobe_info(out)
        streams = info["streams"]
        assert any(s.get("codec_name") == "h264" for s in streams)
        duration = float(info["format"]["duration"])
        assert duration == pytest.approx(1.0, abs=0.35)

    def test_empty_frames_raise(self, tmp_path):
        with pytest.raises(ValidationError):
            Compositor().frames_to_video([], tmp_path / "out.mp4")

    def test_concat_videos(self, tmp_path):
        frames = make_frames(tmp_path)
        compositor = Compositor()
        first = compositor.frames_to_video(frames, tmp_path / "a.mp4", fps=6)
        second = compositor.frames_to_video(frames, tmp_path / "b.mp4", fps=6)
        joined = compositor.concat_videos([first, second], tmp_path / "joined.mp4")
        from omniframe.engines.compositor import ffprobe_info

        duration = float(ffprobe_info(joined)["format"]["duration"])
        assert duration == pytest.approx(2.0, abs=0.6)


class TestAudio:
    def test_mix_audio(self, tmp_path):
        a = make_wav(tmp_path / "a.wav")
        b = make_wav(tmp_path / "b.wav", seconds=0.25)
        tracks = [
            AudioTrack(path=str(a), name="voice", volume=0.8),
            AudioTrack(path=str(b), name="bgm", volume=0.4),
        ]
        out = Compositor().mix_audio(tracks, tmp_path / "mix.wav", fps=30)
        assert out.exists() and out.stat().st_size > 0

    def test_ducking_builds_a_filter_graph(self, tmp_path):
        from omniframe.engines.compositor.audio import _build_filtergraph

        a = make_wav(tmp_path / "a.wav")
        b = make_wav(tmp_path / "b.wav", seconds=0.25)
        tracks = [
            AudioTrack(path=str(a), name="voice"),
            AudioTrack(path=str(b), name="bgm", duck_under=["voice"]),
        ]
        graph, labels = _build_filtergraph(tracks, 30, None)
        assert "sidechaincompress" in graph
        assert "amix" in graph
        assert labels == ["out"]

    def test_ducking_with_unknown_target_raises(self, tmp_path):
        a = make_wav(tmp_path / "a.wav")
        tracks = [AudioTrack(path=str(a), name="bgm", duck_under=["ghost"])]
        with pytest.raises(ValidationError):
            Compositor().mix_audio(tracks, tmp_path / "mix.wav", fps=30)

    def test_missing_audio_file_raises(self, tmp_path):
        with pytest.raises(ValidationError):
            Compositor().mix_audio(
                [AudioTrack(path=str(tmp_path / "nope.wav"), name="x")],
                tmp_path / "mix.wav",
            )

    def test_normalisation_is_applied(self, tmp_path):
        from omniframe.engines.compositor.audio import _build_filtergraph

        a = make_wav(tmp_path / "a.wav")
        graph, _ = _build_filtergraph(
            [AudioTrack(path=str(a), name="v", normalization="ebu_r128")], 30, None
        )
        assert "loudnorm" in graph


class TestSubtitlesAndLut:
    def test_burn_subtitles(self, tmp_path):
        frames = make_frames(tmp_path)
        video = Compositor().frames_to_video(frames, tmp_path / "v.mp4", fps=6)
        srt = tmp_path / "subs.srt"
        srt.write_text(
            "1\n00:00:00,000 --> 00:00:00,500\nHello\n", encoding="utf-8"
        )
        out = Compositor().burn_subtitles(video, srt, tmp_path / "burned.mp4")
        assert out.exists() and out.stat().st_size > 0

    def test_missing_subtitle_raises(self, tmp_path):
        with pytest.raises(ValidationError):
            Compositor().burn_subtitles(tmp_path / "v.mp4", tmp_path / "no.srt", tmp_path / "o.mp4")

    def test_scale_video(self, tmp_path):
        frames = make_frames(tmp_path)
        video = Compositor().frames_to_video(frames, tmp_path / "v.mp4", fps=6)
        out = Compositor().scale_video(video, tmp_path / "scaled.mp4", width=128, height=72)
        from omniframe.engines.compositor import ffprobe_info

        stream = ffprobe_info(out)["streams"][0]
        assert stream["width"] == 128 and stream["height"] == 72


class TestProjectRender:
    def test_render_project(self, tmp_path):
        from omniframe.core.timeline_schema.models import (
            Clip,
            ClipKind,
            OmniProject,
            ProjectMeta,
            Track,
            TrackKind,
        )

        frames = make_frames(tmp_path)
        video = Compositor().frames_to_video(frames, tmp_path / "src.mp4", fps=6)

        project = OmniProject(meta=ProjectMeta(name="demo", fps=6))
        project.tracks.append(
            Track(
                id="v1",
                kind=TrackKind.VIDEO,
                clips=[
                    Clip(
                        id="c1",
                        kind=ClipKind.VIDEO,
                        start_frame=0,
                        duration_frames=6,
                        source=str(video),
                    )
                ],
            )
        )

        out = Compositor().render_project(project, tmp_path / "final.mp4")
        assert out.exists() and out.stat().st_size > 0
