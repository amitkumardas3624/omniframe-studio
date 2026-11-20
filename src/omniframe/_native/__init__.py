"""Optional native acceleration with a safe Python fallback."""

from .loader import get_frame_sink, native_available, native_module, native_status

__all__ = ["get_frame_sink", "native_available", "native_module", "native_status"]
