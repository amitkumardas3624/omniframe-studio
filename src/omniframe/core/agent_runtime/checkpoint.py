"""Checkpointing and rollback.

Before a destructive edit the agent runtime snapshots the project document.
Snapshots are plain JSON so they can be inspected, diffed, committed to git,
or fed straight back into an agent's context.
"""

from __future__ import annotations

import hashlib
import json
import shutil
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ..errors import CheckpointError
from ..logging import get_logger
from ..timeline_schema.models import OmniProject

LOG = get_logger("core.agent_runtime.checkpoint")


def project_hash(project: OmniProject | dict[str, Any]) -> str:
    """Stable content hash of a project document."""

    document = project if isinstance(project, dict) else project.model_dump(mode="json")
    canonical = json.dumps(document, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


@dataclass
class Checkpoint:
    """Metadata describing one stored snapshot."""

    id: str
    label: str
    created_at: str
    path: str
    hash: str
    frames: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "label": self.label,
            "created_at": self.created_at,
            "path": self.path,
            "hash": self.hash,
            "frames": self.frames,
        }


class CheckpointStore:
    """Filesystem-backed checkpoint storage."""

    INDEX = "index.json"

    def __init__(self, root: str | Path) -> None:
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    # -- persistence ----------------------------------------------------
    def _index_path(self) -> Path:
        return self.root / self.INDEX

    def _read_index(self) -> dict[str, Any]:
        path = self._index_path()
        if not path.exists():
            return {"checkpoints": []}
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise CheckpointError(f"Corrupt checkpoint index at {path}: {exc}") from exc

    def _write_index(self, data: dict[str, Any]) -> None:
        self._index_path().write_text(
            json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8"
        )

    # -- api ------------------------------------------------------------
    def save(
        self,
        project: OmniProject,
        *,
        label: str = "auto",
        checkpoint_id: str | None = None,
    ) -> Checkpoint:
        """Store a snapshot of ``project`` and return its metadata."""

        document = project.model_dump(mode="json")
        digest = project_hash(document)
        stamp = time.strftime("%Y%m%d-%H%M%S")
        safe_label = "".join(ch if ch.isalnum() or ch in "-_" else "-" for ch in label)[:40]
        cid = checkpoint_id or f"{stamp}-{safe_label}-{digest[:8]}"

        target = self.root / f"{cid}.json"
        if target.exists():
            cid = f"{cid}-{int(time.time() * 1000) % 100000}"
            target = self.root / f"{cid}.json"

        try:
            target.write_text(json.dumps(document, indent=2, ensure_ascii=False), encoding="utf-8")
        except OSError as exc:
            raise CheckpointError(f"Could not write checkpoint {target}: {exc}") from exc

        checkpoint = Checkpoint(
            id=cid,
            label=label,
            created_at=time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime()),
            path=str(target),
            hash=digest,
            frames=int(document.get("meta", {}).get("duration_frames", 0)),
        )

        index = self._read_index()
        entries = [e for e in index["checkpoints"] if e.get("id") != cid]
        entries.append(checkpoint.to_dict())
        entries.sort(key=lambda e: e.get("created_at", ""), reverse=True)
        index["checkpoints"] = entries
        self._write_index(index)

        LOG.info("checkpoint saved", extra={"checkpoint": cid, "label": label})
        return checkpoint

    def list(self) -> list[Checkpoint]:
        """Return every stored checkpoint, newest first."""

        entries = self._read_index()["checkpoints"]
        return [
            Checkpoint(
                id=e.get("id", ""),
                label=e.get("label", ""),
                created_at=e.get("created_at", ""),
                path=e.get("path", ""),
                hash=e.get("hash", ""),
                frames=int(e.get("frames", 0)),
            )
            for e in entries
        ]

    def path_for(self, checkpoint_id: str) -> Path:
        """Resolve the file backing ``checkpoint_id``."""

        for entry in self._read_index()["checkpoints"]:
            if entry.get("id") == checkpoint_id:
                return Path(entry["path"])
        candidate = self.root / f"{checkpoint_id}.json"
        if candidate.exists():
            return candidate
        raise CheckpointError(f"Unknown checkpoint '{checkpoint_id}'.")

    def load(self, checkpoint_id: str) -> OmniProject:
        """Load a checkpoint back into a project document."""

        path = self.path_for(checkpoint_id)
        try:
            document = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise CheckpointError(f"Could not read checkpoint {path}: {exc}") from exc
        return OmniProject.model_validate(document)

    def restore(self, checkpoint_id: str, destination: str | Path) -> Path:
        """Write a checkpoint back to ``destination`` (a project file)."""

        path = self.path_for(checkpoint_id)
        target = Path(destination)
        target.parent.mkdir(parents=True, exist_ok=True)
        try:
            shutil.copyfile(path, target)
        except OSError as exc:
            raise CheckpointError(f"Could not restore checkpoint to {target}: {exc}") from exc
        LOG.info("checkpoint restored", extra={"checkpoint": checkpoint_id, "target": str(target)})
        return target

    def diff(self, checkpoint_a: str, checkpoint_b: str) -> dict[str, Any]:
        """Compare two checkpoints and return a structured diff."""

        a = self.load(checkpoint_a)
        b = self.load(checkpoint_b)
        return diff_projects(a, b)

    def prune(self, keep: int = 20) -> list[str]:
        """Delete the oldest checkpoints, keeping the ``keep`` most recent."""

        entries = self._read_index()["checkpoints"]
        removed: list[str] = []
        for entry in entries[keep:]:
            path = Path(entry.get("path", ""))
            try:
                if path.exists():
                    path.unlink()
                removed.append(entry.get("id", ""))
            except OSError as exc:  # pragma: no cover - filesystem dependent
                LOG.warning("could not prune checkpoint", extra={"error": str(exc)})
        self._write_index({"checkpoints": entries[:keep]})
        return removed


def diff_projects(a: OmniProject, b: OmniProject) -> dict[str, Any]:
    """Structured diff between two projects."""

    def clip_map(project: OmniProject) -> dict[str, dict[str, Any]]:
        out: dict[str, dict[str, Any]] = {}
        for track in project.tracks:
            for clip in track.clips:
                out[clip.id] = {
                    "track_id": track.id,
                    "name": clip.name,
                    "kind": clip.kind.value,
                    "start_frame": clip.start_frame,
                    "duration_frames": clip.duration_frames,
                    "source": clip.source,
                    "keyframes": len(clip.keyframes),
                }
        return out

    map_a, map_b = clip_map(a), clip_map(b)
    added = sorted(set(map_b) - set(map_a))
    removed = sorted(set(map_a) - set(map_b))
    changed: list[dict[str, Any]] = []
    for clip_id in sorted(set(map_a) & set(map_b)):
        before, after = map_a[clip_id], map_b[clip_id]
        fields = {
            key: {"before": before[key], "after": after[key]}
            for key in before
            if before[key] != after[key]
        }
        if fields:
            changed.append({"clip_id": clip_id, "fields": fields})

    meta_fields = {
        key: {"before": getattr(a.meta, key), "after": getattr(b.meta, key)}
        for key in a.meta.model_dump()
        if getattr(a.meta, key) != getattr(b.meta, key)
    }

    return {
        "added_clips": added,
        "removed_clips": removed,
        "changed_clips": changed,
        "meta_changes": meta_fields,
        "track_count": {"before": len(a.tracks), "after": len(b.tracks)},
        "frame_count": {"before": a.total_frames(), "after": b.total_frames()},
        "identical": not (added or removed or changed or meta_fields),
    }
