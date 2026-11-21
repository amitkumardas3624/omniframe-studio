"""Schema migrations for OmniFrame's local SQLite databases.

:func:`apply_migrations` is idempotent and transactional, so callers may simply
run it on every open; :func:`current_version` reports where a database stands
without touching it.
"""

from __future__ import annotations

from .registry import (
    BASE_JOBS_SCHEMA,
    GUARD_TABLE,
    KNOWN_VERSIONS,
    LATEST_VERSION,
    MIGRATIONS,
    Migration,
    apply_migrations,
    current_version,
)

__all__ = [
    "BASE_JOBS_SCHEMA",
    "GUARD_TABLE",
    "KNOWN_VERSIONS",
    "LATEST_VERSION",
    "MIGRATIONS",
    "Migration",
    "apply_migrations",
    "current_version",
]
