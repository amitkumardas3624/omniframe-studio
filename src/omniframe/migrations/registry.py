"""Ordered, transactional schema migrations for OmniFrame SQLite databases.

The Phase 2 job store proved that a durable local database is worth keeping; it
also showed that ``CREATE TABLE IF NOT EXISTS`` on every open cannot express a
change to an existing schema. This module replaces that with a real chain:

* :data:`MIGRATIONS` is an ordered, append-only tuple of :class:`Migration`
  records. Version ``1`` is the base job schema from Phase 2. New versions are
  appended, never edited in place: editing an applied migration would silently
  diverge databases on different machines.
* ``schema_migrations`` is the guard table. It records ``(version, applied_at)``
  for every migration a database has run, which makes :func:`apply_migrations`
  idempotent -- reopening an up-to-date database applies nothing.
* Each migration runs in its own transaction together with its bookkeeping row,
  so a crash mid-migration leaves the database at the previous version rather
  than at a half-applied one.

Failure policy: an unreadable or corrupt database raises
:class:`~omniframe.core.errors.MigrationError`. Nothing is deleted or recreated
to "fix" it -- a corrupt file is still user data, and a silent wipe is how a
tool loses the work it was trusted with.
"""

from __future__ import annotations

import sqlite3
from contextlib import closing
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from ..core.errors import MigrationError, ValidationError

__all__ = [
    "BASE_JOBS_SCHEMA",
    "GUARD_TABLE",
    "LATEST_VERSION",
    "MIGRATIONS",
    "KNOWN_VERSIONS",
    "Migration",
    "apply_migrations",
    "current_version",
]

#: Bookkeeping table recording which migrations a database has applied.
GUARD_TABLE = "schema_migrations"

#: Base job schema (Phase 2), verbatim in intent: every column the job store
#: reads and writes. Kept here so the store owns behaviour, not DDL.
BASE_JOBS_SCHEMA = """
CREATE TABLE IF NOT EXISTS jobs (
  id TEXT PRIMARY KEY,
  kind TEXT NOT NULL,
  status TEXT NOT NULL,
  workspace TEXT NOT NULL,
  owner TEXT,
  payload_json TEXT NOT NULL,
  result_json TEXT,
  error TEXT,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  attempts INTEGER NOT NULL DEFAULT 0
);
"""


@dataclass(frozen=True)
class Migration:
    """One ordered, atomic schema step."""

    version: int
    name: str
    statements: tuple[str, ...]


#: Append-only chain. Never edit or reorder an entry that has shipped.
MIGRATIONS: tuple[Migration, ...] = (
    Migration(version=1, name="base_job_schema", statements=(BASE_JOBS_SCHEMA,)),
)

#: Version the schema reaches after every migration has been applied.
LATEST_VERSION = MIGRATIONS[-1].version

#: Every version this build knows how to produce.
KNOWN_VERSIONS = frozenset(migration.version for migration in MIGRATIONS)

#: Targets that do not name a persistent file (sqlite URI and in-memory forms).
_NON_PERSISTENT_PREFIXES = (":memory:", "file:")

_GUARD_TABLE_SQL = f"""
CREATE TABLE IF NOT EXISTS {GUARD_TABLE} (
  version INTEGER PRIMARY KEY,
  applied_at TEXT NOT NULL
);
"""


def _now() -> str:
    """ISO-8601 UTC timestamp recorded for an applied migration."""
    return datetime.now(timezone.utc).isoformat()


def _resolve_path(db_path: str | Path) -> Path:
    """Validate and normalize ``db_path``.

    In-memory and URI targets are rejected rather than silently ignored: the job
    store opens a fresh connection per operation, so a schema held in process
    memory would vanish between calls and every migration would appear to apply
    forever.
    """
    text = str(db_path)
    if text.startswith(_NON_PERSISTENT_PREFIXES):
        raise ValidationError(
            "schema migrations need a persistent database file; "
            ":memory: and sqlite URI targets are not supported",
            db_path=text,
        )
    return Path(db_path).expanduser()


def _connect(path: Path) -> sqlite3.Connection:
    """Open ``path`` in explicit-transaction mode, creating parents as needed."""
    path.parent.mkdir(parents=True, exist_ok=True)
    return sqlite3.connect(str(path), isolation_level=None, timeout=5.0)


def _applied_versions(conn: sqlite3.Connection) -> list[int]:
    """Return the recorded versions, oldest first (``[]`` when unguarded)."""
    row = conn.execute(
        "SELECT name FROM sqlite_master WHERE type = 'table' AND name = ?",
        (GUARD_TABLE,),
    ).fetchone()
    if row is None:
        return []
    rows = conn.execute(f"SELECT version FROM {GUARD_TABLE} ORDER BY version").fetchall()
    return [int(item[0]) for item in rows]


def _apply_one(conn: sqlite3.Connection, migration: Migration) -> None:
    """Run one migration and its bookkeeping row in a single transaction."""
    conn.execute("BEGIN IMMEDIATE")
    try:
        for statement in migration.statements:
            conn.execute(statement)
        conn.execute(
            f"INSERT INTO {GUARD_TABLE} (version, applied_at) VALUES (?, ?)",
            (migration.version, _now()),
        )
    except sqlite3.Error as exc:
        conn.rollback()
        raise MigrationError(
            f"migration {migration.version} ({migration.name}) failed: {exc}",
            version=migration.version,
            name=migration.name,
            db_error=str(exc),
        ) from exc
    conn.commit()


def current_version(db_path: str | Path) -> int:
    """Return the schema version ``db_path`` is at, or ``0`` when unmigrated.

    A path that does not exist yet reports ``0`` and is not created as a
    side effect. An unreadable file raises :class:`MigrationError`.
    """
    path = _resolve_path(db_path)
    if not path.exists():
        return 0
    try:
        with closing(_connect(path)) as conn:
            applied = _applied_versions(conn)
    except sqlite3.DatabaseError as exc:
        raise MigrationError(
            f"cannot read the schema version of {path}: {exc}",
            db_path=str(path),
            db_error=str(exc),
        ) from exc
    return max(applied) if applied else 0


def apply_migrations(db_path: str | Path, *, to_version: int | None = None) -> int:
    """Bring ``db_path`` up to ``to_version`` (default: latest) and return it.

    Idempotent: a database already at the target gains nothing and keeps its
    existing ``applied_at`` records. Downgrades are refused rather than faked,
    and every pending migration is applied in ascending version order inside its
    own transaction.
    """
    path = _resolve_path(db_path)
    target = LATEST_VERSION if to_version is None else to_version
    if isinstance(target, bool) or not isinstance(target, int):
        raise ValidationError(
            "to_version must be an integer schema version", to_version=to_version
        )
    if target not in KNOWN_VERSIONS:
        raise ValidationError(
            f"unknown schema version {target}; this build knows {sorted(KNOWN_VERSIONS)}",
            to_version=target,
            known=sorted(KNOWN_VERSIONS),
        )

    try:
        with closing(_connect(path)) as conn:
            conn.execute(_GUARD_TABLE_SQL)
            applied = _applied_versions(conn)
            unknown = sorted(set(applied) - KNOWN_VERSIONS)
            if unknown:
                raise MigrationError(
                    f"database reports schema versions {unknown} this build does not "
                    "know; it was written by a newer OmniFrame -- upgrade instead of "
                    "downgrading",
                    db_path=str(path),
                    applied=applied,
                    known=sorted(KNOWN_VERSIONS),
                )
            current = max(applied) if applied else 0
            if target < current:
                raise ValidationError(
                    f"cannot migrate down from schema version {current} to {target}",
                    db_path=str(path),
                    current=current,
                    to_version=target,
                )
            for migration in MIGRATIONS:
                if current < migration.version <= target:
                    _apply_one(conn, migration)
            return max(_applied_versions(conn) or [0])
    except sqlite3.DatabaseError as exc:
        raise MigrationError(
            f"cannot migrate {path}: {exc}; the file was left untouched",
            db_path=str(path),
            db_error=str(exc),
        ) from exc



