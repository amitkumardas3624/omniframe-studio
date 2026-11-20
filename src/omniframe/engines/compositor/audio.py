"""Audio mixing, ducking and normalisation."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Sequence

from ...core.errors import ValidationError
from ...core.logging import get_logger
from .ffmpeg import run_ffmpeg

LOG = get_logger("engines.compositor.audio")

AUDIO_SAMPLE_RATE = 48000


@dataclass
class AudioTrack:
    """One audio source entering the mix."""

    path: str
    volume: float = 1.0
    #: Offset in frames (converted with the project fps).
    start_frame: int = 0
    fade_in_frames: int = 0
    fade_out_frames: int = 0
    #: Names of the tracks this track is ducked *under*.
    duck_under: list[str] = field(default_factory=list)
    #: ``none`` | ``peak`` | ``ebu_r128``
    normalization: str = "none"
    target_lufs: float = -14.0
    name: str = ""

    def resolved_name(self) -> str:
        """The name used to reference this track."""

        return self.name or Path(self.path).stem

    def to_dict(self) -> dict[str, Any]:
        return {
            "path": self.path,
            "name": self.resolved_name(),
            "volume": self.volume,
            "start_frame": self.start_frame,
            "fade_in_frames": self.fade_in_frames,
            "fade_out_frames": self.fade_out_frames,
            "duck_under": list(self.duck_under),
            "normalization": self.normalization,
            "target_lufs": self.target_lufs,
        }


@dataclass
class SubtitleTrack:
    """One subtitle source (SRT or VTT)."""

    path: str
    burn: bool = False
    name: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {"path": self.path, "burn": self.burn, "name": self.name}


def _validate_tracks(tracks: Sequence[AudioTrack]) -> None:
    if not tracks:
        raise ValidationError("mix_audio requires at least one audio track.")
    names = [track.resolved_name() for track in tracks]
    duplicates = {name for name in names if names.count(name) > 1}
    if duplicates:
        raise ValidationError(
            f"Audio track names must be unique; duplicated: {', '.join(sorted(duplicates))}",
            duplicates=sorted(duplicates),
        )
    known = set(names)
    for track in tracks:
        for target in track.duck_under:
            if target not in known:
                raise ValidationError(
                    f"Audio track '{track.resolved_name()}' wants to duck under "
                    f"'{target}', which does not exist.",
                    track=track.resolved_name(),
                    missing=target,
                    available=sorted(known),
                )


def _build_filtergraph(
    tracks: Sequence[AudioTrack], fps: float, duration: float | None
) -> tuple[str, list[str]]:
    """Build the ffmpeg filter graph and the list of output labels."""

    labels: list[str] = []
    chains: list[str] = []

    for index, track in enumerate(tracks):
        label = f"a{index}"
        steps: list[str] = []

        delay_ms = int(round(track.start_frame / fps * 1000)) if fps else 0
        if delay_ms:
            steps.append(f"adelay={delay_ms}|{delay_ms}")
        if abs(track.volume - 1.0) > 1e-6:
            steps.append(f"volume={track.volume}")

        if track.fade_in_frames and fps:
            steps.append(f"afade=in:st=0:d={track.fade_in_frames / fps:.4f}")
        if track.fade_out_frames and fps:
            total = (duration or 0) or (track.start_frame + track.fade_out_frames) / fps
            start = max(0.0, total - track.fade_out_frames / fps)
            steps.append(f"afade=out:st={start:.4f}:d={track.fade_out_frames / fps:.4f}")

        mode = (track.normalization or "none").lower()
        if mode == "ebu_r128":
            steps.append(f"loudnorm=I={track.target_lufs}:TP=-1.5:LRA=11")
        elif mode == "peak":
            steps.append("alimiter=limit=0.95")

        chains.append(f"[{index}:a]{','.join(steps)}[{label}]")
        labels.append(label)

    # Ducking: a track that lists another track in `duck_under` is compressed
    # by that track acting as the sidechain signal.
    index_by_name = {track.resolved_name(): i for i, track in enumerate(tracks)}
    current = list(labels)

    for index, track in enumerate(tracks):
        for target in track.duck_under:
            sidechain_index = index_by_name[target]
            sidechain = current[sidechain_index]
            output_label = f"d{index}_{target}"
            chains.append(
                f"[{current[index]}][{sidechain}]"
                f"sidechaincompress=threshold=0.05:ratio=8:attack=5:release=300"
                f"[{output_label}]"
            )
            current[index] = output_label

    mix_inputs = "".join(f"[{label}]" for label in current)
    mix_duration = "first" if duration else "longest"
    chains.append(
        f"{mix_inputs}amix=inputs={len(current)}:duration={mix_duration}:dropout_transition=0[out]"
    )
    return ";".join(chains), ["out"]


def mix_audio(
    tracks: Sequence[AudioTrack],
    output: str | Path,
    *,
    fps: float = 30.0,
    duration: float | None = None,
    sample_rate: int = AUDIO_SAMPLE_RATE,
) -> Path:
    """Mix audio tracks into a WAV file.

    The mix applies per-track delay, gain, fades, normalisation and
    side-chain ducking, then combines everything with ``amix``.
    """

    _validate_tracks(tracks)

    for track in tracks:
        if not Path(track.path).exists():
            raise ValidationError(
                f"Audio file not found: {track.path}", track=track.resolved_name()
            )

    target = Path(output)
    target.parent.mkdir(parents=True, exist_ok=True)

    graph, out_labels = _build_filtergraph(tracks, fps, duration)

    args: list[str] = []
    for track in tracks:
        args += ["-i", str(track.path)]
    args += ["-filter_complex", graph, "-map", f"[{out_labels[0]}]"]
    args += [
        "-c:a", "pcm_s16le",
        "-ar", str(sample_rate),
        "-ac", "2",
        str(target),
    ]

    run_ffmpeg(args)
    LOG.info(
        "audio mixed",
        extra={"tracks": len(tracks), "output": str(target)},
    )
    return target
