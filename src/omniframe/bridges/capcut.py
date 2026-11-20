"""CapCut bridge.

CapCut's desktop project is a *draft*: a directory holding
``draft_content.json`` plus a media folder.  The format is undocumented, so
this bridge classifies it as ``REVERSE_ENGINEERED``: the JSON structure is
read and written, never patched at the binary level, and the export workflow
(which has no public API) is explicitly labelled ``UI_AUTOMATION``.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ..core.config import detect_capcut
from ..core.logging import get_logger
from ..core.timeline_schema.translate import get_translator
from .base import BridgeCapability, BridgeReport, BridgeTier, GeneratedScript, ToolBridge

LOG = get_logger("bridges.capcut")

DRAFT_FILES = ("draft_content.json", "draft_meta_info.json", "draft_virtual_store.json")


def _slug(value: str) -> str:
    cleaned = "".join(ch if ch.isalnum() else "_" for ch in str(value)).strip("_")
    return (cleaned.lower() or "omniframe_project")


class CapCutBridge(ToolBridge):
    """Adapter for CapCut desktop drafts."""

    id = "capcut"
    host = "CapCut"
    script_extension = ".json"
    description = (
        "Generates CapCut desktop draft projects from an OmniFrame project and "
        "inspects existing draft directories read-only."
    )

    # -- detection ------------------------------------------------------
    def detect(self) -> BridgeReport:
        notes: list[str] = []
        try:
            cap = detect_capcut()
        except Exception as exc:  # pragma: no cover
            return BridgeReport(
                bridge=self.id,
                host=self.host,
                installed=False,
                capabilities=self.capabilities(),
                notes=[f"CapCut detection failed: {exc}"],
            )

        if cap.available:
            notes.append("CapCut detected.")
            notes.append(
                "The draft format has no public API: open the generated draft folder "
                "in CapCut and import it from the project list."
            )
        else:
            notes.append(
                cap.detail or "CapCut not detected - drafts can still be generated ahead of time."
            )

        paths: dict[str, str] = {}
        if cap.path:
            paths["executable"] = cap.path
        return BridgeReport(
            bridge=self.id,
            host=self.host,
            installed=bool(cap.available),
            version=cap.version,
            path=cap.path,
            scripting_api=False,
            capabilities=self.capabilities(),
            paths=paths,
            notes=notes,
        )

    # -- capabilities ---------------------------------------------------
    def capabilities(self) -> list[BridgeCapability]:
        return [
            BridgeCapability(
                name="draft_generation",
                tier=BridgeTier.REVERSE_ENGINEERED,
                description="Write a draft_content.json compatible with CapCut desktop.",
                requires_host=False,
            ),
            BridgeCapability(
                name="draft_inspection",
                tier=BridgeTier.REVERSE_ENGINEERED,
                description="Summarise materials, tracks and segments of an existing draft.",
                requires_host=False,
            ),
            BridgeCapability(
                name="track_clip_mapping",
                tier=BridgeTier.REVERSE_ENGINEERED,
                description="Map universal tracks/clips onto draft segments.",
                requires_host=False,
            ),
            BridgeCapability(
                name="text_effect_audio_mapping",
                tier=BridgeTier.REVERSE_ENGINEERED,
                description="Map text, effect and audio clips into draft materials.",
                requires_host=False,
            ),
            BridgeCapability(
                name="export_workflow",
                tier=BridgeTier.UI_AUTOMATION,
                description="CapCut export has no scriptable API; export is driven in the UI.",
                requires_host=True,
            ),
        ]

    # -- generation -----------------------------------------------------
    def generate_script(
        self,
        project: Any,
        output_dir: str | Path,
        **options: Any,
    ) -> GeneratedScript:
        name = project.meta.name or "OmniFrame Project"
        stem = _slug(options.get("stem") or f"{_slug(name)}_capcut")

        out_dir = Path(output_dir)
        draft_dir = out_dir / f"{stem}_capcut_draft"
        draft_dir.mkdir(parents=True, exist_ok=True)

        draft = get_translator("capcut_draft").from_universal(project)
        draft_path = draft_dir / "draft_content.json"
        draft_path.write_text(
            json.dumps(draft, indent=2, ensure_ascii=False), encoding="utf-8"
        )

        manifest = {
            "bridge": self.id,
            "project": name,
            "fps": project.meta.fps,
            "resolution": [project.meta.width, project.meta.height],
            "duration_frames": project.total_frames(),
            "draft_content": "draft_content.json",
            "media_folder": "materials",
            "instructions": [
                "Copy the referenced media files into the 'materials' folder.",
                "Open CapCut, add the project and pick this draft directory.",
                "Export manually - CapCut exposes no scriptable export API.",
            ],
        }
        manifest_path = draft_dir / "manifest.json"
        manifest_path.write_text(
            json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8"
        )

        materials = draft_dir / "materials"
        materials.mkdir(exist_ok=True)

        warnings: list[str] = []
        if not self.detect().installed:
            warnings.append(
                "CapCut was not detected. The draft was still generated; open it in CapCut "
                "on a machine where the app is installed."
            )
        warnings.append(
            "The CapCut draft format is undocumented and version specific: verify the draft "
            "loads correctly in your CapCut build before relying on it."
        )
        missing = [
            asset.id
            for asset in project.assets
            if asset.path and not Path(asset.path).exists()
        ]
        if missing:
            warnings.append(
                f"{len(missing)} referenced media file(s) are missing: "
                + ", ".join(missing[:8])
                + ". Copy them into the 'materials' folder."
            )

        return GeneratedScript(
            bridge=self.id,
            path=str(draft_path),
            language="json",
            summary=(
                f"CapCut draft for {name}: {len(draft.get('tracks', []))} track(s), "
                f"{len(draft.get('materials', {}).get('videos', []))} material(s)."
            ),
            metadata={
                "draft_path": str(draft_path),
                "manifest_path": str(manifest_path),
                "draft_dir": str(draft_dir),
                "sidecars": [str(manifest_path)],
                "project_name": name,
                "fps": project.meta.fps,
                "track_count": len(draft.get("tracks", [])),
                "tier": BridgeTier.REVERSE_ENGINEERED.value,
            },
            warnings=warnings,
        )

    # -- inspection -----------------------------------------------------
    def inspect(self, target: str | Path) -> dict[str, Any]:
        path = Path(target)
        if not path.exists():
            return {
                "bridge": self.id,
                "host": self.host,
                "target": str(path),
                "exists": False,
                "error": "target not found",
            }

        if path.is_file():
            return self._inspect_draft_file(path)

        entries = [
            {
                "path": str(child.relative_to(path)),
                "dir": child.is_dir(),
                "size_bytes": child.stat().st_size if child.is_file() else None,
            }
            for child in sorted(path.rglob("*"))[:300]
        ]

        report: dict[str, Any] = {
            "bridge": self.id,
            "host": self.host,
            "target": str(path),
            "exists": True,
            "kind": "directory",
            "tier": BridgeTier.REVERSE_ENGINEERED.value,
            "entry_count": len(entries),
            "entries": entries,
            "draft_files": [name for name in DRAFT_FILES if (path / name).exists()],
        }

        content = path / "draft_content.json"
        if content.exists():
            report.update(self._summarise_draft(content))
        return report

    def _inspect_draft_file(self, path: Path) -> dict[str, Any]:
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            return {
                "bridge": self.id,
                "host": self.host,
                "target": str(path),
                "exists": True,
                "kind": "file",
                "tier": BridgeTier.REVERSE_ENGINEERED.value,
                "size_bytes": path.stat().st_size,
                "error": f"could not parse JSON: {exc}",
            }
        summary = self._summarise_draft(path)
        summary["top_level_keys"] = sorted(data.keys())
        return summary

    def _summarise_draft(self, path: Path) -> dict[str, Any]:
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            return {"error": f"could not parse JSON: {exc}"}

        materials = data.get("materials", {}) or {}
        tracks = data.get("tracks", []) or []
        material_paths = [
            mat.get("path")
            for group in materials.values()
            if isinstance(group, list)
            for mat in group
            if isinstance(mat, dict) and mat.get("path")
        ]
        return {
            "bridge": self.id,
            "host": self.host,
            "target": str(path),
            "exists": True,
            "kind": "file",
            "tier": BridgeTier.REVERSE_ENGINEERED.value,
            "size_bytes": path.stat().st_size,
            "track_count": len(tracks),
            "track_types": sorted({str(t.get("type", "unknown")) for t in tracks}),
            "segment_counts": [
                {"track": t.get("name") or t.get("id"), "segments": len(t.get("segments", []))}
                for t in tracks
            ],
            "material_counts": {
                key: len(value) for key, value in materials.items() if isinstance(value, list)
            },
            "material_paths": material_paths[:50],
            "duration_us": data.get("duration"),
            "fps": data.get("fps"),
        }
