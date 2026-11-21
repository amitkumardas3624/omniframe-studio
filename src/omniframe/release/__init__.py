"""Release tooling: reproducible artifact checksums and compatibility reporting.

The release modules are deliberately dependency-free beyond the standard library
so that a signed release can be re-verified by a downloader without installing the
platform's optional rendering extras.
"""

from __future__ import annotations

from .compat import PROBED_CODECS, VERIFICATION_LEVELS, compatibility_report, probe_preset
from .sign import ARCHIVE_SUFFIXES, CHUNK_SIZE, DEFAULT_SIDECAR, checksum_archive

__all__ = [
    "ARCHIVE_SUFFIXES",
    "CHUNK_SIZE",
    "DEFAULT_SIDECAR",
    "PROBED_CODECS",
    "VERIFICATION_LEVELS",
    "checksum_archive",
    "compatibility_report",
    "probe_preset",
]
