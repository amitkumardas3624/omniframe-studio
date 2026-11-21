"""Durable SQLite-backed job store for OmniFrame.

Holds one ``jobs`` table recording each job's status, owner, workspace, JSON
payload/result and attempt count. Connections are opened per-operation via a
context manager so concurrent threads (e.g. the Phase 2 ``JobManager``) are
safe without sharing a connection.

The schema itself is owned by :mod:`omniframe.migrations` -- this module opens
the database and then calls :func:`~omniframe.migrations.apply_migrations`, so
adding a column is a new migration entry rather than an edit to a ``CREATE
TABLE IF NOT EXISTS`` that existing databases would silently ignore.
"""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ..core.errors import ValidationError
from ..migrations import apply_migrations

#: The set of valid lifecycle statuses a job may be in.
JOB_STATUSES = frozenset({"queued", "running", "paused", "done", "failed", "canceled"})

#: Column names from the schema that ``update_job`` may write through ``**fields``.
_UPDATEABLE_COLUMNS = frozenset(
    {"kind", "status", "workspace", "owner", "payload_json", "result_json", "error", "attempts"}
)

# Columns present on every row returned to callers (parsed forms in place of the
# ``_json`` storage columns).
_ROW_KEYS = (
    "id",
    "kind",
    "status",
    "workspace",
    "owner",
    "payload",
    "result",
    "error",
    "created_at",
    "updated_at",
    "attempts",
)


def _now() -> str:
    """ISO-8601 UTC timestamp string for created_at/updated_at."""
    return datetime.now(timezone.utc).isoformat()


def _dumps(value: Any) -> str:
    """Serialize ``value`` to a JSON string (``null`` when sensibly empty)."""
    if value is None:
        return "null"
    return json.dumps(value)


def _loads(raw: str | None) -> Any:
    """Parse a stored JSON string back into a Python object (None when absent)."""
    if raw is None:
        return None
    try:
        return json.loads(raw)
    except (ValueError, TypeError):
        return raw


class JobStore:
    """SQLite persistence for OmniFrame jobs.

    Either an explicit ``db_path`` or a ``workspace`` directory may be given.
    When only ``workspace`` is supplied the database file defaults to
    ``<workspace>/.omniframe/jobs.db``; when neither is given the current
    working directory is treated as the workspace.
    """

    def __init__(
        self,
        db_path: str | Path | None = None,
        *,
        workspace: str | Path | None = None,
    ) -> None:
        if db_path is not None and workspace is not None:
            raise ValidationError(
                "Pass either db_path or workspace, not both.",
                db_path=str(db_path),
                workspace=str(workspace),
            )
        if db_path is not None:
            self.db_path = Path(db_path).expanduser()
        else:
            base = Path(workspace).expanduser() if workspace is not None else Path.cwd()
            self.db_path = base / ".omniframe" / "jobs.db"
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_schema()

    # -- low-level connection helpers ------------------------------------

    def _connect(self) -> sqlite3.Connection:
        # check_same_thread=False so a plain in-memory or shared handle could be
        # used down the line; we still open a fresh connection per operation.
        conn = sqlite3.connect(self.db_path, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_schema(self) -> None:
        """Bring the database to the latest schema version (idempotent)."""
        apply_migrations(self.db_path)

    @staticmethod
    def _to_dict(row: sqlite3.Row) -> dict[str, Any]:
        """Turn a stored row into the public dict with parsed payload/result."""
        data = dict(row)
        data["payload"] = _loads(data.pop("payload_json", None))
        data["result"] = _loads(data.pop("result_json", None))
        return {key: data.get(key) for key in _ROW_KEYS}

    # -- public API -------------------------------------------------------

    def create_job(
        self,
        id: str,
        kind: str,
        status: str,
        workspace: str,
        payload: Any = None,
        owner: str | None = None,
    ) -> str:
        """Persist a new job and return its ``id``.

        ``kind`` must be non-empty and ``status`` must be one of
        :data:`JOB_STATUSES`; both are validated via :class:`ValidationError`.
        """
        if not kind or not kind.strip():
            raise ValidationError("job kind must be a non-empty string", kind=kind)
        if status not in JOB_STATUSES:
            raise ValidationError(
                f"unknown job status {status!r}; expected one of {sorted(JOB_STATUSES)}",
                status=status,
            )
        timestamp = _now()
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO jobs (
                  id, kind, status, workspace, owner, payload_json,
                  created_at, updated_at, attempts
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 0)
                """,
                (
                    id,
                    kind,
                    status,
                    workspace,
                    owner,
                    _dumps(payload),
                    timestamp,
                    timestamp,
                ),
            )
            conn.commit()
        return id

    def get_job(self, job_id: str) -> dict[str, Any] | None:
        """Return the job as a dict (parsed payload/result) or ``None``."""
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone()
        return self._to_dict(row) if row is not None else None

    def update_job(
        self,
        job_id: str,
        *,
        status: str | None = None,
        result: Any = None,
        error: str | None = None,
        payload: Any = None,
        **fields: Any,
    ) -> dict[str, Any] | None:
        """Merge updates into a job, bump ``updated_at`` and return the new row.

        ``status`` is validated against :data:`JOB_STATUSES` when supplied.
        Any extra keyword in ``fields`` must name a writable schema column.
        Returns ``None`` when the job does not exist.
        """
        if status is not None and status not in JOB_STATUSES:
            raise ValidationError(
                f"unknown job status {status!r}; expected one of {sorted(JOB_STATUSES)}",
                status=status,
            )

        assignments: list[str] = ["updated_at = ?"]
        values: list[Any] = [_now()]
        for key, value in (
            ("status", status),
            ("result", result),
            ("error", error),
            ("payload", payload),
        ):
            if key in ("status", "error"):
                if value is not None:
                    assignments.append(f"{key} = ?")
                    values.append(value)
            elif key == "payload":
                if value is not None:
                    assignments.append("payload_json = ?")
                    values.append(_dumps(value))
            else:  # result
                if value is not None:
                    assignments.append("result_json = ?")
                    values.append(_dumps(value))
        for key, value in fields.items():
            if key not in _UPDATEABLE_COLUMNS:
                raise ValidationError(
                    f"cannot update unknown job column {key!r}",
                    column=key,
                )
            if key in ("payload_json", "result_json"):
                assignments.append(f"{key} = ?")
                values.append(_dumps(value))
            else:
                assignments.append(f"{key} = ?")
                values.append(value)

        values.append(job_id)
        with self._connect() as conn:
            conn.execute(
                f"UPDATE jobs SET {', '.join(assignments)} WHERE id = ?", values
            )
            conn.commit()
        return self.get_job(job_id)

    def list_jobs(self, status: str | None = None) -> list[dict[str, Any]]:
        """List jobs ordered by ``created_at``, optionally filtered by status."""
        if status is not None and status not in JOB_STATUSES:
            raise ValidationError(
                f"unknown job status {status!r}; expected one of {sorted(JOB_STATUSES)}",
                status=status,
            )
        with self._connect() as conn:
            if status is None:
                rows = conn.execute(
                    "SELECT * FROM jobs ORDER BY created_at ASC"
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM jobs WHERE status = ? ORDER BY created_at ASC",
                    (status,),
                ).fetchall()
        return [self._to_dict(row) for row in rows]

    def delete_job(self, job_id: str) -> bool:
        """Delete a job, returning True if a row was removed."""
        with self._connect() as conn:
            cur = conn.execute("DELETE FROM jobs WHERE id = ?", (job_id,))
            conn.commit()
        return cur.rowcount > 0


__all__ = ["JobStore", "JOB_STATUSES"]