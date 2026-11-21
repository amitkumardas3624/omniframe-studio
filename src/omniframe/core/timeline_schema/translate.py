"""Bidirectional translators between the universal timeline and host formats.

Every translator implements the same contract:

``to_universal(document) -> OmniProject``
    Parse a host format into the canonical model.
``from_universal(project) -> dict``
    Serialise the canonical model into the host format.

The registry lets the agent runtime pick a translator by name
(``omniframe translate --from fcpxml --to universal``) without knowing which
module implements it.
"""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from abc import ABC, abstractmethod
from collections.abc import Callable
from typing import Any

from .models import (
    Asset,
    Clip,
    ClipKind,
    Keyframe,
    OmniProject,
    ProjectMeta,
    Shot,
    Track,
    TrackKind,
)

# ---------------------------------------------------------------------------
# Time helpers
# ---------------------------------------------------------------------------

_TIMECODE_RE = re.compile(r"^(\d+):(\d{2}):(\d{2}):(\d{2})$")
_DURATION_RE = re.compile(r"^(\d+(?:\.\d+)?)(h|m|s|ms|f)$")


def parse_time_to_frames(value: str | int | float, fps: float = 30.0) -> int:
    """Parse ``HH:MM:SS:FF``, ``1m30s``, ``12.5s``, ``100f`` or a raw number."""

    if isinstance(value, (int, float)):
        return int(round(float(value) * fps)) if fps and value < 1000 else int(value)
    text = str(value).strip()
    if not text:
        return 0

    match = _TIMECODE_RE.match(text)
    if match:
        hh, mm, ss, ff = (int(g) for g in match.groups())
        total = ((hh * 60 + mm) * 60 + ss) * fps + ff
        return int(round(total))

    match = _DURATION_RE.match(text)
    if match:
        amount, unit = match.groups()
        amount_f = float(amount)
        if unit == "h":
            return int(round(amount_f * 3600 * fps))
        if unit == "m":
            return int(round(amount_f * 60 * fps))
        if unit == "s":
            return int(round(amount_f * fps))
        if unit == "ms":
            return int(round(amount_f / 1000 * fps))
        if unit == "f":
            return int(round(amount_f))

    rational = re.match(r"^(\d+)/(\d+)s$", text)
    if rational:
        numerator, denominator = (float(g) for g in rational.groups())
        if denominator:
            return int(round(numerator / denominator * fps))

    try:
        return int(round(float(text) * fps))
    except ValueError as exc:
        raise ValueError(f"Cannot parse time value: {value!r}") from exc


def frames_to_timecode(frames: int, fps: float = 30.0) -> str:
    """Render frames as ``HH:MM:SS:FF``."""

    fps_i = max(1, int(round(fps)))
    frames = max(0, int(frames))
    ff = frames % fps_i
    total_seconds = frames // fps_i
    ss = total_seconds % 60
    mm = (total_seconds // 60) % 60
    hh = (total_seconds // 3600) % 24
    return f"{hh:02d}:{mm:02d}:{ss:02d}:{ff:02d}"


def frames_to_fcpxml_time(frames: int, fps: float = 30.0) -> str:
    """Render frames as an FCPXML rational time, e.g. ``0s`` or ``10/30s``."""

    if fps <= 0:
        fps = 30.0
    if frames == 0:
        return "0s"
    if abs(frames - round(frames)) < 1e-9 and abs(frames / fps - round(frames / fps)) < 1e-9:
        return f"{int(round(frames / fps))}s"
    return f"{int(frames)}/{int(round(fps))}s"


# ---------------------------------------------------------------------------
# Translator contract
# ---------------------------------------------------------------------------

class TimelineTranslator(ABC):
    """Base class for all host-format translators."""

    #: Stable identifier used in the CLI and the tool registry.
    name: str = "base"
    #: Human readable description surfaced to agents.
    description: str = ""
    #: MIME-ish label of the source format.
    source_format: str = "unknown"

    @abstractmethod
    def to_universal(self, document: Any) -> OmniProject:
        """Convert a host document into an :class:`OmniProject`."""

    @abstractmethod
    def from_universal(self, project: OmniProject) -> Any:
        """Convert an :class:`OmniProject` into the host format."""

    def describe(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "source_format": self.source_format,
            "direction": "bidirectional",
        }


_REGISTRY: dict[str, Callable[[], TimelineTranslator]] = {}


def register_translator(name: str, factory: Callable[[], TimelineTranslator]) -> None:
    """Register a translator factory under ``name`` (idempotent)."""

    _REGISTRY[name] = factory


def get_translator(name: str) -> TimelineTranslator:
    """Instantiate the translator registered as ``name``."""

    try:
        factory = _REGISTRY[name]
    except KeyError as exc:
        raise KeyError(
            f"Unknown translator '{name}'. Available: {', '.join(sorted(_REGISTRY))}"
        ) from exc
    return factory()


def available_translators() -> list[dict[str, Any]]:
    """Describe every registered translator."""

    out = []
    for name in sorted(_REGISTRY):
        try:
            out.append(_REGISTRY[name]().describe())
        except Exception:  # pragma: no cover - defensive
            out.append({"name": name, "description": "(failed to instantiate)"})
    return out


# ---------------------------------------------------------------------------
# FCPXML (Premiere Pro / DaVinci Resolve interchange)
# ---------------------------------------------------------------------------

class FCPXMLTranslator(TimelineTranslator):
    """FCPXML 1.9 (and Resolve's XML variant) import/export."""

    name = "fcpxml"
    description = "Final Cut Pro XML interchange format (Premiere Pro, DaVinci Resolve)."
    source_format = "application/vnd.apple.fcpxml+xml"

    def to_universal(self, document: Any) -> OmniProject:
        if isinstance(document, str):
            root = ET.fromstring(document)
        elif isinstance(document, bytes):
            root = ET.fromstring(document.decode("utf-8"))
        elif isinstance(document, ET.Element):
            root = document
        else:
            raise TypeError("FCPXML translator expects a string, bytes or ElementTree root")

        resources = root.find("resources")
        fps = self._detect_fps(root)
        meta = ProjectMeta(name=root.get("name", "imported"), fps=fps)

        assets: list[Asset] = []
        formats: dict[str, dict[str, Any]] = {}
        if resources is not None:
            for fmt in resources.findall("format"):
                fid = fmt.get("id", "")
                frame_duration = self._parse_fraction(fmt.get("frameDuration", "1/30s"))
                formats[fid] = {
                    "width": int(float(fmt.get("width", 1920))),
                    "height": int(float(fmt.get("height", 1080))),
                    "fps": (1.0 / frame_duration) if frame_duration > 0 else 30.0,
                }
                if formats[fid]["width"] and formats[fid]["height"]:
                    meta.width = max(meta.width, formats[fid]["width"])
                    meta.height = max(meta.height, formats[fid]["height"])

            for asset in resources.findall("asset"):
                aid = asset.get("id", f"asset-{len(assets) + 1}")
                name = asset.get("name", aid)
                src = self._asset_src(asset)
                assets.append(
                    Asset(
                        id=aid,
                        kind=self._asset_kind(src),
                        path=src,
                        metadata={"name": name, "format": asset.get("format")},
                    )
                )

        tracks: list[Track] = []
        spine = root.find("./library/event/./project/./sequence/spine")
        if spine is None:
            spine = root.find("./library/event/./project/./spine")
        if spine is None:
            spine = root.find("spine")
        if spine is not None:
            tracks = self._parse_spine(spine, assets, fps, meta)

        shots = [
            Shot(
                id=f"shot-{i + 1}",
                name=f"Shot {i + 1}",
                index=i,
                start_frame=0,
                end_frame=0,
            )
            for i in range(0)
        ]

        project = OmniProject(
            meta=meta,
            tracks=tracks,
            assets=assets,
            shots=shots,
            metadata={"imported_from": "fcpxml"},
        )
        project.meta.duration_frames = project.total_frames()
        return project

    def from_universal(self, project: OmniProject) -> str:
        fps = project.meta.fps
        resources: list[str] = []
        asset_refs: dict[str, str] = {}

        fmt_id = "r1"
        resources.append(
            f'    <format id="{fmt_id}" name="FFVideoFormat{project.meta.height}p" '
            f'frameDuration="{self._fraction(fps)}" width="{project.meta.width}" '
            f'height="{project.meta.height}"/>'
        )

        # Assets: the project's declared assets first, then any clip source
        # that no declared asset covers.
        sources: list[tuple[str, str, str]] = []
        for asset in project.assets:
            sources.append(
                (
                    asset.id,
                    asset.path or asset.url or "",
                    str(asset.metadata.get("name", asset.id)),
                )
            )
        for track in project.sorted_tracks():
            for clip in track.sorted_clips():
                if clip.source and not any(entry[1] == clip.source for entry in sources):
                    sources.append((clip.id, clip.source, clip.name or clip.id))

        for index, (_asset_id, source, name) in enumerate(sources):
            ref = f"r{index + 2}"
            asset_refs[source] = ref
            resources.append(
                f'    <asset id="{ref}" name="{_xml_escape(name)}" '
                f'src="{_xml_escape(source)}" start="0s" duration="0s" '
                f'hasVideo="1" hasAudio="1" format="{fmt_id}"/>'
            )

        spine_entries: list[str] = []
        for track in project.sorted_tracks():
            for clip in track.sorted_clips():
                spine_entries.append(self._clip_xml(clip, asset_refs, fps))

        xml = (
            '<?xml version="1.0" encoding="UTF-8"?>\n'
            '<fcpxml version="1.9">\n'
            "  <resources>\n"
            + "\n".join(resources)
            + "\n  </resources>\n"
            "  <library>\n"
            '    <event name="OmniFrame Export">\n'
            '      <project name="'
            + _xml_escape(project.meta.name)
            + '">\n'
            "        <spine>\n"
            + "\n".join(spine_entries)
            + "\n        </spine>\n"
            "      </project>\n"
            "    </event>\n"
            "  </library>\n"
            "</fcpxml>\n"
        )
        return xml

    # -- internals -------------------------------------------------------
    def _clip_xml(self, clip: Clip, asset_refs: dict[str, str], fps: float) -> str:
        offset = frames_to_fcpxml_time(clip.start_frame, fps)
        duration = frames_to_fcpxml_time(clip.duration_frames, fps)
        start = frames_to_fcpxml_time(clip.in_frame, fps)
        name = _xml_escape(clip.name or clip.id)
        ref = asset_refs.get(clip.source or "")
        if ref:
            return (
                f'          <asset-clip ref="{ref}" name="{name}" '
                f'offset="{offset}" start="{start}" duration="{duration}"/>'
            )
        return (
            f'          <ref-clip ref="r1" name="{name}" '
            f'offset="{offset}" start="{start}" duration="{duration}"/>'
        )

    def _parse_spine(
        self, spine: ET.Element, assets: list[Asset], fps: float, meta: ProjectMeta
    ) -> list[Track]:
        track = Track(id="v1", name="Video 1", kind=TrackKind.VIDEO, index=0)
        cursor = 0
        clip_index = 0

        elements: list[ET.Element] = []
        for child in list(spine):
            if child.tag == "lane":
                elements.extend(list(child))
            else:
                elements.append(child)

        for child in elements:
            tag = child.tag
            offset = parse_time_to_frames(child.get("offset", "0s"), fps)
            duration = parse_time_to_frames(child.get("duration", "0s"), fps)
            if tag == "gap":
                cursor = max(cursor, offset + duration)
                continue
            if tag not in {"asset-clip", "resource-clip", "ref-clip"}:
                continue

            start = parse_time_to_frames(child.get("start", "0s"), fps)
            name = child.get("name", f"clip-{clip_index + 1}")
            ref = child.get("ref", "")
            asset = next((a for a in assets if a.id == ref), None)
            clip = Clip(
                id=f"c{clip_index + 1}",
                name=name,
                kind=ClipKind.VIDEO,
                start_frame=cursor,
                duration_frames=max(1, duration),
                source=asset.path if asset else None,
                in_frame=start,
                metadata={"fcpxml_ref": ref},
            )
            track.clips.append(clip)
            clip_index += 1
            cursor += max(1, duration)
        return [track] if track.clips else []

    def _detect_fps(self, root: ET.Element) -> float:
        fmt = root.find(".//format")
        if fmt is not None and fmt.get("frameDuration"):
            # ``frameDuration`` is the length of one frame ("1/30s" == 30 fps).
            frame_duration = self._parse_fraction(fmt.get("frameDuration", ""))
            if frame_duration > 0:
                return 1.0 / frame_duration
        return 30.0

    @staticmethod
    def _parse_fraction(value: str) -> float:
        value = (value or "").strip()
        if not value:
            return 0.0
        if value.endswith("s"):
            value = value[:-1]
        if "/" in value:
            num, den = value.split("/", 1)
            try:
                den_f = float(den)
                return float(num) / den_f if den_f else 0.0
            except ValueError:
                return 0.0
        try:
            return float(value)
        except ValueError:
            return 0.0

    @staticmethod
    def _fraction(fps: float) -> str:
        fps_i = int(round(fps))
        return f"1/{fps_i}s" if fps_i else "1/30s"

    @staticmethod
    def _asset_src(asset: ET.Element) -> str:
        for child in list(asset):
            if child.tag.endswith("file") and child.get("src"):
                return child.get("src", "")
        return ""

    @staticmethod
    def _asset_kind(src: str) -> str:
        lower = src.lower()
        if lower.endswith((".png", ".jpg", ".jpeg", ".webp", ".gif")):
            return "image"
        if lower.endswith((".wav", ".mp3", ".m4a", ".aac", ".flac")):
            return "audio"
        if lower.endswith((".mp4", ".mov", ".mxf", ".mkv")):
            return "video"
        return "other"


class ResolveXMLTranslator(FCPXMLTranslator):
    """DaVinci Resolve's XML flavour of FCPXML."""

    name = "resolve_xml"
    description = "DaVinci Resolve XML timeline (FCPXML superset)."
    source_format = "application/xml"

    def describe(self) -> dict[str, Any]:
        data = super().describe()
        data["source_format"] = "application/xml"
        data["host"] = "DaVinci Resolve"
        return data


# ---------------------------------------------------------------------------
# CMX3600 EDL
# ---------------------------------------------------------------------------

class EDLTranslator(TimelineTranslator):
    """CMX3600 edit decision list import/export."""

    name = "edl"
    description = "CMX3600 edit decision list."
    source_format = "text/plain"

    _LINE_RE = re.compile(
        r"^(?P<num>\d{3})\s+(?P<reel>\S+)\s+(?P<track>[VA]\d+)\s+(?P<transition>\S+)\s+"
        r"(?P<src_in>[\d:]+)\s+(?P<src_out>[\d:]+)\s+(?P<rec_in>[\d:]+)\s+(?P<rec_out>[\d:]+)"
        r"(?P<rest>.*)$"
    )

    def to_universal(self, document: Any) -> OmniProject:
        text = document if isinstance(document, str) else str(document)
        meta = ProjectMeta(name="edl-import")
        track = Track(id="v1", name="V1", kind=TrackKind.VIDEO, index=0)
        assets: list[Asset] = []
        fps = meta.fps
        cursor = 0
        for raw in text.splitlines():
            line = raw.strip()
            if not line or line.startswith("TITLE:") or line.startswith("FCM:"):
                continue
            match = self._LINE_RE.match(line)
            if not match:
                continue
            src_in = parse_time_to_frames(match.group("src_in"), fps)
            src_out = parse_time_to_frames(match.group("src_out"), fps)
            rec_in = parse_time_to_frames(match.group("rec_in"), fps)
            duration = max(1, src_out - src_in)
            reel = match.group("reel")
            name = reel
            for comment in line.split("*"):  # trailing * FROM CLIP NAME: xyz
                if "FROM CLIP NAME" in comment:
                    name = comment.split(":", 1)[1].strip()
            asset_id = f"asset-{reel}"
            if not any(a.id == asset_id for a in assets):
                assets.append(Asset(id=asset_id, kind="video", path=None, metadata={"reel": reel}))
            track.clips.append(
                Clip(
                    id=f"c{len(track.clips) + 1}",
                    name=name,
                    kind=ClipKind.VIDEO,
                    start_frame=cursor,
                    duration_frames=duration,
                    in_frame=src_in,
                    source=None,
                    metadata={"reel": reel, "record_in": rec_in},
                )
            )
            cursor += duration
        project = OmniProject(
            meta=meta,
            tracks=[track] if track.clips else [],
            assets=assets,
            metadata={"imported_from": "edl"},
        )
        project.meta.duration_frames = project.total_frames()
        return project

    def from_universal(self, project: OmniProject) -> str:
        fps = project.meta.fps
        lines = [f"TITLE: {project.meta.name.upper()}", "FCM: NON-DROP FRAME", ""]
        counter = 1
        for track in project.sorted_tracks():
            if track.kind not in {TrackKind.VIDEO, TrackKind.AUDIO}:
                continue
            for clip in track.sorted_clips():
                src_in = clip.in_frame
                src_out = clip.in_frame + clip.duration_frames
                rec_in = clip.start_frame
                rec_out = clip.start_frame + clip.duration_frames
                lines.append(
                    f"{counter:03d}  {clip.id[:8].upper():<8} {track.kind.value[0].upper()}"
                    f"{track.index + 1}     C        "
                    f"{frames_to_timecode(src_in, fps)} {frames_to_timecode(src_out, fps)} "
                    f"{frames_to_timecode(rec_in, fps)} {frames_to_timecode(rec_out, fps)}"
                )
                lines.append(f"* FROM CLIP NAME: {clip.name or clip.id}")
                counter += 1
        lines.append("")
        return "\n".join(lines)


# ---------------------------------------------------------------------------
# CapCut draft (reverse-engineered project format)
# ---------------------------------------------------------------------------

class CapCutDraftTranslator(TimelineTranslator):
    """CapCut desktop draft JSON import/export.

    The desktop draft format is a JSON document with a ``materials`` map and a
    ``tracks`` list; durations are expressed in microseconds.  This translator
    reads and writes that structure directly so a project can be round-tripped
    without CapCut running.
    """

    name = "capcut_draft"
    description = "CapCut desktop draft_content.json project format."
    source_format = "application/json"

    US = 1_000_000  # microseconds per second

    def to_universal(self, document: Any) -> OmniProject:
        import json

        if isinstance(document, str):
            data = json.loads(document)
        else:
            data = document

        materials = data.get("materials", {})
        videos = list(materials.get("videos", [])) + list(materials.get("audios", []))
        assets: list[Asset] = []
        by_material: dict[str, Asset] = {}
        for mat in videos:
            aid = mat.get("id") or mat.get("material_id") or f"asset-{len(assets) + 1}"
            path = mat.get("path") or mat.get("local_material_id") or ""
            asset = Asset(
                id=aid,
                kind="audio" if "audios" in str(mat.get("type", "")) else "video",
                path=path,
                metadata={
                    "duration_us": mat.get("duration", 0),
                    "width": mat.get("width", 0),
                    "height": mat.get("height", 0),
                },
            )
            assets.append(asset)
            by_material[aid] = asset

        meta = ProjectMeta(name=data.get("name", "capcut-import"), fps=float(data.get("fps", 30.0)))
        tracks: list[Track] = []
        for index, tr in enumerate(data.get("tracks", [])):
            kind = self._track_kind(tr.get("type", "video"))
            track = Track(id=tr.get("id", f"t{index + 1}"), name=tr.get("name", ""), kind=kind, index=index)
            for seg_index, seg in enumerate(tr.get("segments", [])):
                target = seg.get("target_timerange", {})
                source = seg.get("source_timerange", {})
                start_us = target.get("start", 0)
                duration_us = target.get("duration", source.get("duration", 0))
                asset = by_material.get(seg.get("material_id", ""))
                track.clips.append(
                    Clip(
                        id=seg.get("id", f"c{index + 1}-{seg_index + 1}"),
                        name=(asset.metadata.get("name") if asset else "") or seg.get("id", ""),
                        kind=ClipKind.AUDIO if kind == TrackKind.AUDIO else ClipKind.VIDEO,
                        start_frame=int(round(start_us / self.US * meta.fps)),
                        duration_frames=max(1, int(round(duration_us / self.US * meta.fps))),
                        in_frame=int(round(source.get("start", 0) / self.US * meta.fps)),
                        source=asset.path if asset else None,
                    )
                )
            tracks.append(track)

        project = OmniProject(
            meta=meta,
            tracks=tracks,
            assets=assets,
            metadata={"imported_from": "capcut_draft"},
        )
        project.meta.duration_frames = project.total_frames()
        return project

    def from_universal(self, project: OmniProject) -> dict[str, Any]:
        materials: dict[str, list[dict[str, Any]]] = {"videos": [], "audios": []}
        material_ids: dict[str, str] = {}
        for index, asset in enumerate(project.assets):
            mid = f"mat-{index + 1}"
            material_ids[asset.id] = mid
            entry = {
                "id": mid,
                "path": asset.path or "",
                "duration": int(asset.metadata.get("duration_us") or 0),
                "type": "video" if asset.kind in {"video", "image"} else "audio",
                "material_name": asset.metadata.get("name", asset.id),
            }
            materials["videos" if entry["type"] == "video" else "audios"].append(entry)

        tracks: list[dict[str, Any]] = []
        for track in project.sorted_tracks():
            segments = []
            for clip in track.sorted_clips():
                asset = next((a for a in project.assets if a.path == clip.source), None)
                mid = material_ids.get(asset.id, "") if asset else ""
                segments.append(
                    {
                        "id": clip.id,
                        "material_id": mid,
                        "target_timerange": {
                            "start": int(round(clip.start_frame / project.meta.fps * self.US)),
                            "duration": int(round(clip.duration_frames / project.meta.fps * self.US)),
                        },
                        "source_timerange": {
                            "start": int(round(clip.in_frame / project.meta.fps * self.US)),
                            "duration": int(round(clip.duration_frames / project.meta.fps * self.US)),
                        },
                    }
                )
            tracks.append(
                {
                    "id": track.id,
                    "name": track.name,
                    "type": "video" if track.kind != TrackKind.AUDIO else "audio",
                    "segments": segments,
                }
            )

        return {
            "version": "13.0.0",
            "name": project.meta.name,
            "fps": project.meta.fps,
            "duration": int(round(project.total_frames() / project.meta.fps * self.US)),
            "canvas_config": {"width": project.meta.width, "height": project.meta.height},
            "materials": materials,
            "tracks": tracks,
        }

    @staticmethod
    def _track_kind(raw: str) -> TrackKind:
        raw = (raw or "video").lower()
        if "audio" in raw:
            return TrackKind.AUDIO
        if "text" in raw:
            return TrackKind.SUBTITLE
        if "effect" in raw or "sticker" in raw:
            return TrackKind.MOTION_FX
        return TrackKind.VIDEO


# ---------------------------------------------------------------------------
# After Effects project manifest
# ---------------------------------------------------------------------------

class AEManifestTranslator(TimelineTranslator):
    """JSON manifest describing an After Effects composition.

    After Effects projects are proprietary binary bundles, so OmniFrame uses a
    documented JSON manifest that the AE bridge converts into ExtendScript.
    The manifest is the interchange format, not a replacement for ``.aep``.
    """

    name = "ae_manifest"
    description = "After Effects composition manifest (JSON) used by the AE bridge."
    source_format = "application/json"

    def to_universal(self, document: Any) -> OmniProject:
        import json

        data = json.loads(document) if isinstance(document, str) else document
        comp = data.get("composition", {})
        fps = float(comp.get("fps", 30.0))
        meta = ProjectMeta(
            name=comp.get("name", "ae-import"),
            fps=fps,
            width=int(comp.get("width", 1920)),
            height=int(comp.get("height", 1080)),
        )
        track = Track(id="a1", name="AE Layers", kind=TrackKind.MOTION_FX, index=0)
        for index, layer in enumerate(data.get("layers", [])):
            start = int(round(float(layer.get("in", 0)) * fps))
            end = int(round(float(layer.get("out", 0)) * fps))
            keyframes: list[Keyframe] = []
            for kf in layer.get("keyframes", []):
                frames = kf.get("frames", [])
                values = kf.get("values", [])
                if not frames:
                    continue
                frame = int(round(float(frames[0]) * fps))
                value = values[0] if values else 0
                keyframes.append(_keyframe_from_value(frame, value))
            track.clips.append(
                Clip(
                    id=layer.get("id", f"l{index + 1}"),
                    name=layer.get("name", ""),
                    kind=ClipKind.MOTION_FX,
                    start_frame=start,
                    duration_frames=max(1, end - start),
                    source=layer.get("source"),
                    keyframes=keyframes,
                    metadata={"ae_type": layer.get("type", "null")},
                )
            )
        project = OmniProject(
            meta=meta, tracks=[track] if track.clips else [], metadata={"imported_from": "ae_manifest"}
        )
        project.meta.duration_frames = project.total_frames()
        return project

    def from_universal(self, project: OmniProject) -> dict[str, Any]:
        fps = project.meta.fps
        layers: list[dict[str, Any]] = []
        for track in project.sorted_tracks():
            for clip in track.sorted_clips():
                layers.append(
                    {
                        "id": clip.id,
                        "name": clip.name or clip.id,
                        "type": clip.metadata.get("ae_type", "null"),
                        "source": clip.source,
                        "in": round(clip.start_frame / fps, 4),
                        "out": round(clip.end_frame / fps, 4),
                        "keyframes": [
                            {
                                "property": prop,
                                "frames": [round(kf.frame / fps, 4)],
                                "values": [value],
                            }
                            for kf in clip.keyframes
                            for prop, value in kf.values.items()
                        ],
                    }
                )
        return {
            "composition": {
                "name": project.meta.name,
                "fps": fps,
                "width": project.meta.width,
                "height": project.meta.height,
                "duration": round(project.total_frames() / fps, 4),
            },
            "layers": layers,
        }


def _keyframe_from_value(frame: int, value: Any) -> Keyframe:
    """Build a :class:`Keyframe` from a single property value."""

    return Keyframe(frame=frame, values={"value": value})


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------

register_translator("fcpxml", FCPXMLTranslator)
register_translator("resolve_xml", ResolveXMLTranslator)
register_translator("edl", EDLTranslator)
register_translator("capcut_draft", CapCutDraftTranslator)
register_translator("ae_manifest", AEManifestTranslator)


def _xml_escape(value: str) -> str:
    return (
        str(value)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )
