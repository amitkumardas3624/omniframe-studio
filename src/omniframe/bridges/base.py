"""The unified ``ToolBridge`` contract.

Every professional host application (Premiere Pro, After Effects, DaVinci
Resolve, CapCut, Krita) is exposed through the same interface so the agent
runtime can treat them interchangeably.

Three capability tiers are modelled explicitly, because they differ wildly in
robustness and in how a reviewer should treat them:

``documented_api``
    The host publishes a scripting API (ExtendScript, Resolve's Python/Lua
    API, ...).  Preferred: stable, supported, safe to automate.

``reverse_engineered``
    The host's project format was inspected and mapped (RAE methodology).
    Used for *reading and generating* project documents.  Never modifies a
    host binary; never patches proprietary code.

``ui_automation``
    A last-resort fallback that drives the host's user interface.  Fragile by
    nature, so it is always reported as such and must be opted into.

Every bridge must degrade gracefully: when the host is not installed the
bridge still answers ``detect()`` and ``capabilities()`` so an agent can plan
around the missing application.
"""

from __future__ import annotations

import os
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any

from ..core.logging import get_logger
from .loss import LossItem, record_loss

LOG = get_logger("bridges.base")


class BridgeTier(str, Enum):
    """How a capability is reached."""

    DOCUMENTED_API = "documented_api"
    REVERSE_ENGINEERED = "reverse_engineered"
    UI_AUTOMATION = "ui_automation"

    def __str__(self) -> str:  # pragma: no cover - trivial
        return self.value


@dataclass
class BridgeCapability:
    """A single thing a bridge can do."""

    name: str
    tier: BridgeTier
    description: str = ""
    requires_host: bool = True

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "tier": self.tier.value,
            "description": self.description,
            "requires_host": self.requires_host,
        }


@dataclass
class BridgeReport:
    """Result of probing a host application on this machine."""

    bridge: str
    host: str
    installed: bool = False
    version: str | None = None
    path: str | None = None
    scripting_api: bool = False
    capabilities: list[BridgeCapability] = field(default_factory=list)
    paths: dict[str, str] = field(default_factory=dict)
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "bridge": self.bridge,
            "host": self.host,
            "installed": self.installed,
            "version": self.version,
            "path": self.path,
            "scripting_api": self.scripting_api,
            "capabilities": [c.to_dict() for c in self.capabilities],
            "paths": dict(self.paths),
            "notes": list(self.notes),
        }


@dataclass
class GeneratedScript:
    """A script (or project document) produced by a bridge."""

    bridge: str
    path: str
    language: str
    summary: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "bridge": self.bridge,
            "path": self.path,
            "language": self.language,
            "summary": self.summary,
            "metadata": self.metadata,
            "warnings": list(self.warnings),
        }


class ToolBridge(ABC):
    """Base class for every host-application adapter."""

    #: Stable bridge identifier, e.g. ``premiere_pro``.
    id: str = "tool_bridge"
    #: Human readable host application name.
    host: str = "Unknown Host"
    #: File extension used for generated scripts.
    script_extension: str = ".txt"
    #: Human readable description of what the bridge does.
    description: str = ""

    # -- detection ------------------------------------------------------
    @abstractmethod
    def detect(self) -> BridgeReport:
        """Probe the machine for this host application."""

    @abstractmethod
    def capabilities(self) -> list[BridgeCapability]:
        """List the capabilities this bridge exposes."""

    # -- optional behaviour ---------------------------------------------
    def inspect(self, target: str | os.PathLike[str]) -> dict[str, Any]:
        """Reverse-engineering inspection of a project file or structure.

        The default implementation performs safe, read-only structural
        probing: size, magic bytes, embedded marker strings and a recursive
        directory listing.  Bridges override this with format-specific
        parsers.
        """

        path = Path(target)
        if not path.exists():
            return {
                "bridge": self.id,
                "target": str(path),
                "exists": False,
                "error": "target not found",
            }

        report: dict[str, Any] = {
            "bridge": self.id,
            "host": self.host,
            "target": str(path),
            "exists": True,
            "kind": "directory" if path.is_dir() else "file",
            "size_bytes": path.stat().st_size if path.is_file() else None,
            "tier": BridgeTier.REVERSE_ENGINEERED.value,
        }

        if path.is_dir():
            entries: list[dict[str, Any]] = []
            for child in sorted(path.rglob("*")):
                if len(entries) >= 500:
                    report["truncated"] = True
                    # Best-effort loss narrative, additive only: never changes
                    # the existing keys and never raises when a field is read.
                    try:
                        inspected = len(entries)
                        report["loss"] = record_loss(
                            self.id,
                            [
                                LossItem(
                                    feature="entries",
                                    status="degraded",
                                    reason=f"inspection truncated at {inspected} entries",
                                )
                            ],
                        ).to_dict()
                    except OSError:
                        pass
                    break
                entries.append(
                    {
                        "path": str(child.relative_to(path)),
                        "dir": child.is_dir(),
                        "size_bytes": child.stat().st_size if child.is_file() else None,
                    }
                )
            report["entries"] = entries
            return report

        head = path.read_bytes()[:64]
        report["magic_hex"] = head[:16].hex()
        report["magic_ascii"] = "".join(chr(b) if 32 <= b < 127 else "." for b in head)
        report["readable_strings"] = self._readable_strings(path)
        return report

    @staticmethod
    def _readable_strings(path: Path, *, limit: int = 40, min_length: int = 6) -> list[str]:
        """Extract printable ASCII runs — a safe, read-only structural probe."""

        try:
            data = path.read_bytes()
        except OSError:
            return []
        out: list[str] = []
        current: list[str] = []
        for byte in data:
            if 32 <= byte < 127:
                current.append(chr(byte))
                continue
            if len(current) >= min_length:
                out.append("".join(current))
                if len(out) >= limit:
                    break
            current = []
        if len(current) >= min_length and len(out) < limit:
            out.append("".join(current))
        return out

    def generate_script(
        self,
        project: Any,
        output_dir: str | os.PathLike[str],
        **options: Any,
    ) -> GeneratedScript:
        """Produce a script or project document for the host application."""

        raise NotImplementedError(f"{type(self).__name__} does not implement generate_script()")

    def health_check(self) -> dict[str, Any]:
        """A compact status object suitable for ``omniframe doctor``."""

        report = self.detect()
        return {
            "bridge": self.id,
            "host": self.host,
            "installed": report.installed,
            "scripting_api": report.scripting_api,
            "version": report.version,
            "capability_count": len(report.capabilities),
            "notes": report.notes,
        }

    def _write(self, output_dir: str | os.PathLike[str], stem: str, content: str) -> Path:
        out_dir = Path(output_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        target = out_dir / f"{stem}{self.script_extension}"
        target.write_text(content, encoding="utf-8")
        return target
