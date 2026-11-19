"""Structured logging helpers.

OmniFrame emits one JSON object per line so that an agent can consume the log
without a parser, while ``omniframe`` on a TTY still shows a human readable
line. Set ``OMNIFRAME_LOG_FORMAT=json`` to force JSON.
"""

from __future__ import annotations

import json
import logging
import os
import sys
import time
from typing import Any

_CONFIGURED = False

_RESERVED = {
    "name", "msg", "args", "levelname", "levelno", "pathname", "filename",
    "module", "exc_info", "exc_text", "stack_info", "lineno", "funcName",
    "created", "msecs", "relativeCreated", "thread", "threadName",
    "processName", "process", "taskName", "message", "asctime",
}


class _JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "ts": time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime(record.created))
            + f".{int(record.msecs):03d}Z",
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        for key, value in record.__dict__.items():
            if key not in _RESERVED and not key.startswith("_"):
                payload[key] = value
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, default=str, ensure_ascii=False)


class _HumanFormatter(logging.Formatter):
    _LEVEL_COLOR = {
        "DEBUG": "\033[36m",
        "INFO": "\033[32m",
        "WARNING": "\033[33m",
        "ERROR": "\033[31m",
        "CRITICAL": "\033[1;31m",
    }
    _RESET = "\033[0m"

    def format(self, record: logging.LogRecord) -> str:
        stamp = time.strftime("%H:%M:%S", time.localtime(record.created))
        color = self._LEVEL_COLOR.get(record.levelname, "")
        reset = self._RESET if color else ""
        base = f"{color}{stamp} {record.levelname:<7}{reset} {record.name}: {record.getMessage()}"
        extras = {
            k: v for k, v in record.__dict__.items()
            if k not in _RESERVED and not k.startswith("_")
        }
        if extras:
            base += " " + json.dumps(extras, default=str, ensure_ascii=False)
        if record.exc_info:
            base += "\n" + self.formatException(record.exc_info)
        return base


def setup_logging(level: str | int | None = None, *, force: bool = False) -> None:
    """Configure the ``omniframe`` logger hierarchy exactly once."""

    global _CONFIGURED
    if _CONFIGURED and not force:
        return

    resolved = level or os.environ.get("OMNIFRAME_LOG_LEVEL", "INFO")
    if isinstance(resolved, str):
        resolved = getattr(logging, resolved.upper(), logging.INFO)

    root = logging.getLogger("omniframe")
    root.setLevel(resolved)
    root.handlers.clear()
    root.propagate = False

    handler = logging.StreamHandler(stream=sys.stderr)
    fmt = os.environ.get("OMNIFRAME_LOG_FORMAT", "").lower()
    wants_json = fmt == "json" or (
        fmt == "" and not sys.stderr.isatty() and os.environ.get("OMNIFRAME_JSON_LOGS") == "1"
    )
    handler.setFormatter(_JsonFormatter() if wants_json else _HumanFormatter())
    root.addHandler(handler)
    _CONFIGURED = True


def get_logger(name: str) -> logging.Logger:
    """Return a namespaced logger under the ``omniframe`` root logger."""

    setup_logging()
    if not name.startswith("omniframe"):
        name = f"omniframe.{name}"
    return logging.getLogger(name)
