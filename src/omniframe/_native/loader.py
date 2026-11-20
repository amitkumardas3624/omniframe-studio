"""Safe discovery and selection of the optional native accelerator."""

from __future__ import annotations

import importlib
from pathlib import Path
from typing import Any

from .fallback import FramePipeSink as PythonFramePipeSink

_EXTENSION_NAME = "omniframe._native._omniframe_native"
_NATIVE_MODULE: Any | None = None
_NATIVE_ERROR: str | None = None
_DISCOVERED = False


def _discover() -> Any | None:
    global _DISCOVERED, _NATIVE_MODULE, _NATIVE_ERROR
    if _DISCOVERED:
        return _NATIVE_MODULE
    _DISCOVERED = True
    try:
        _NATIVE_MODULE = importlib.import_module(_EXTENSION_NAME)
    except (ImportError, OSError, Exception) as exc:  # extension init errors are optional
        _NATIVE_MODULE = None
        _NATIVE_ERROR = f"native extension not installed: {exc}"
    return _NATIVE_MODULE


def native_available() -> bool:
    """Return whether the optional compiled extension can be used."""

    module = _discover()
    if module is None:
        return False
    try:
        checker = getattr(module, "native_available", None)
        return bool(checker()) if checker is not None else True
    except Exception as exc:  # pragma: no cover - broken optional extension
        global _NATIVE_ERROR
        _NATIVE_ERROR = f"native extension probe failed: {exc}"
        return False


def native_status() -> dict[str, Any]:
    """Return a JSON-safe capability report that never raises."""

    module = _discover()
    available = native_available() if module is not None else False
    if available:
        return {
            "available": True,
            "mode": "native",
            "backend": "pybind11",
            "module": _EXTENSION_NAME,
            "path": getattr(module, "__file__", None),
            "reason": None,
        }
    return {
        "available": False,
        "mode": "fallback",
        "backend": "python",
        "module": _EXTENSION_NAME,
        "path": None,
        "reason": _NATIVE_ERROR or "native extension unavailable",
    }


def native_module() -> Any | None:
    """Return the loaded extension, or ``None`` when fallback is required."""

    return _discover() if native_available() else None


def get_frame_sink(
    output_dir: str | Path,
    *,
    fps: float,
    width: int,
    height: int,
    backend: str = "auto",
    start_frame: int = 0,
    **kwargs: Any,
) -> Any:
    """Construct a native or Python frame sink according to ``backend``."""

    choice = str(backend).lower()
    if choice not in {"auto", "native", "python", "fallback"}:
        raise ValueError("backend must be auto, native, python, or fallback")
    if choice == "native" and not native_available():
        from ..core.errors import EngineUnavailable

        raise EngineUnavailable(
            "The native accelerator is not available; use backend='auto' or 'python'.",
            capability="native_accelerator",
            status=native_status(),
        )
    if choice in {"auto", "native"} and native_available():
        module = native_module()
        sink_type = getattr(module, "FramePipeSink", None) if module is not None else None
        if sink_type is not None:
            return sink_type(
                str(output_dir),
                fps=float(fps),
                width=int(width),
                height=int(height),
                start_frame=int(start_frame),
                **kwargs,
            )
    return PythonFramePipeSink(
        output_dir,
        fps=fps,
        width=width,
        height=height,
        start_frame=start_frame,
        **kwargs,
    )


__all__ = ["get_frame_sink", "native_available", "native_module", "native_status"]
