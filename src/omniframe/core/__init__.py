"""Core primitives shared by every OmniFrame subsystem."""

from __future__ import annotations

from .config import Config, detect_environment, get_config
from .errors import (
    ActionError,
    BridgeError,
    BridgeUnavailable,
    CheckpointError,
    DependencyMissing,
    EngineUnavailable,
    OmniFrameError,
    PreconditionFailed,
    RenderError,
    SchemaError,
    ToolNotFound,
    ValidationError,
)
from .logging import get_logger, setup_logging

__all__ = [
    "ActionError",
    "BridgeError",
    "BridgeUnavailable",
    "CheckpointError",
    "Config",
    "DependencyMissing",
    "EngineUnavailable",
    "OmniFrameError",
    "PreconditionFailed",
    "RenderError",
    "SchemaError",
    "ToolNotFound",
    "ValidationError",
    "detect_environment",
    "get_config",
    "get_logger",
    "setup_logging",
]
