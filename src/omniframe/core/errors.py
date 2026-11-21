"""Typed error hierarchy with stable machine-readable codes.

Every error carries an ``code`` so an agent can branch on the failure without
parsing English prose. The codes are part of the public contract and are
mirrored in ``schemas/tools.json``.
"""

from __future__ import annotations

from typing import Any


class OmniFrameError(Exception):
    """Base class for every error raised by OmniFrame Studio."""

    code: str = "E_OMNIFRAME"

    def __init__(self, message: str, **details: Any) -> None:
        super().__init__(message)
        self.message = message
        self.details: dict[str, Any] = details

    def to_dict(self) -> dict[str, Any]:
        return {
            "error": type(self).__name__,
            "code": self.code,
            "message": self.message,
            "details": self.details,
        }

    def __str__(self) -> str:  # pragma: no cover - trivial
        if not self.details:
            return self.message
        extra = ", ".join(f"{k}={v!r}" for k, v in sorted(self.details.items()))
        return f"{self.message} ({extra})"


class SchemaError(OmniFrameError):
    """The project document does not satisfy the OmniProject schema."""

    code = "E_SCHEMA"


class ValidationError(OmniFrameError):
    """Semantic validation failed (timeline consistency, overlaps, ...)."""

    code = "E_VALIDATION"


class PathSecurityError(OmniFrameError):
    """A workspace path escaped its allowed root (traversal, drive change, symlink)."""

    code = "E_PATH_SECURITY"


class EngineUnavailable(OmniFrameError):
    """A required engine/backend is not installed or not usable on this host."""

    code = "E_ENGINE_UNAVAILABLE"


class RenderError(OmniFrameError):
    """Frame rendering failed; details carry the offending scene + console log."""

    code = "E_RENDER"


class RenderCanceled(RenderError):
    """Rendering was canceled (by request or timed out) before or during work."""

    code = "E_RENDER_CANCELED"


class BridgeUnavailable(OmniFrameError):
    """A DCC host application (Premiere, AE, Resolve, CapCut, Krita) is absent."""

    code = "E_BRIDGE_UNAVAILABLE"


class BridgeError(OmniFrameError):
    """A bridge ran but the host rejected the operation or the script."""

    code = "E_BRIDGE"


class CheckpointError(OmniFrameError):
    """Checkpoint creation or restoration failed."""

    code = "E_CHECKPOINT"


class ToolNotFound(OmniFrameError):
    """The requested action/tool is not registered."""

    code = "E_TOOL_NOT_FOUND"


class PreconditionFailed(OmniFrameError):
    """A tool precondition was not met (missing asset, missing host, ...)."""

    code = "E_PRECONDITION"


class DependencyMissing(OmniFrameError):
    """An optional Python dependency is required for this operation."""

    code = "E_DEPENDENCY_MISSING"


class ActionError(OmniFrameError):
    """A registered action raised while executing."""

    code = "E_ACTION"


class MigrationError(OmniFrameError):
    """A schema migration could not be applied.

    Raised for an unreadable/corrupt database, a stored version this build does
    not know, or a database written by a newer OmniFrame than the one running.
    The database is never deleted or recreated to recover: a corrupt file is
    still user data.
    """

    code = "E_MIGRATION"
