"""Tests for the ordered schema-migration registry.

The contract under test: a fresh database reaches the latest schema version in
one call, re-running it changes nothing, the guard table records when each
version was applied, and a corrupt file fails loudly instead of being wiped.
"""

from __future__ import annotations

import sqlite3
from datetime import datetime

import pytest

from omniframe.core.errors import MigrationError, OmniFrameError, ValidationError
from omniframe.jobs import JobStore
from omniframe.migrations import (
    GUARD_TABLE,
    LATEST_VERSION,
    MIGRATIONS,
    apply_migrations,
    current_version,
)
from omniframe.migrations import registry as migration_registry

#: Columns the job store's public row shape depends on.
JOB_COLUMNS = [
    "id",
    "kind",
    "status",
    "workspace",
    "owner",
    "payload_json",
    "result_json",
    "error",
    "created_at",
    "updated_at",
    "attempts",
]


def _tables(path) -> list[str]:
    with sqlite3.connect(str(path)) as conn:
        rows = conn.execute("SELECT name FROM sqlite_master WHERE type = 'table'").fetchall()
    return sorted(row[0] for row in rows)


def _guard_rows(path) -> list[tuple]:
    with sqlite3.connect(str(path)) as conn:
        return conn.execute(f"SELECT version, applied_at FROM {GUARD_TABLE}").fetchall()


def _columns(path, table: str) -> list[str]:
    with sqlite3.connect(str(path)) as conn:
        return [row[1] for row in conn.execute(f"PRAGMA table_info({table})")]


def test_registry_is_an_ordered_chain() -> None:
    versions = [migration.version for migration in MIGRATIONS]
    assert versions == sorted(versions)
    assert len(set(versions)) == len(versions)
    assert versions[0] == 1
    assert LATEST_VERSION == versions[-1]


def test_fresh_database_reaches_latest_version(tmp_path) -> None:
    path = tmp_path / "jobs.db"
    assert current_version(path) == 0

    assert apply_migrations(path) == LATEST_VERSION
    assert current_version(path) == LATEST_VERSION


def test_current_version_does_not_create_the_file(tmp_path) -> None:
    path = tmp_path / "absent.db"
    assert current_version(path) == 0
    assert not path.exists()


def test_apply_creates_missing_parent_directories(tmp_path) -> None:
    path = tmp_path / "deep" / "nested" / "jobs.db"
    assert apply_migrations(path) == LATEST_VERSION
    assert path.is_file()


def test_reapplying_is_idempotent_and_keeps_the_record(tmp_path) -> None:
    path = tmp_path / "jobs.db"
    apply_migrations(path)
    first = _guard_rows(path)

    assert apply_migrations(path) == LATEST_VERSION
    second = _guard_rows(path)

    assert first == second, "a no-op migration must not rewrite history"
    assert len(second) == LATEST_VERSION


def test_guard_table_records_a_timestamp(tmp_path) -> None:
    path = tmp_path / "jobs.db"
    apply_migrations(path)

    rows = _guard_rows(path)
    assert [row[0] for row in rows] == list(range(1, LATEST_VERSION + 1))
    applied_at = datetime.fromisoformat(rows[0][1])
    assert applied_at.tzinfo is not None, rows[0][1]


def test_base_schema_creates_the_documented_jobs_table(tmp_path) -> None:
    path = tmp_path / "jobs.db"
    apply_migrations(path)

    assert set(_tables(path)) == {"jobs", GUARD_TABLE}
    assert _columns(path, "jobs") == JOB_COLUMNS


def test_unknown_target_is_rejected_before_touching_disk(tmp_path) -> None:
    path = tmp_path / "jobs.db"
    with pytest.raises(ValidationError) as excinfo:
        apply_migrations(path, to_version=LATEST_VERSION + 1)
    assert excinfo.value.code == "E_VALIDATION"
    assert not path.exists()


def test_non_integer_target_is_rejected(tmp_path) -> None:
    with pytest.raises(ValidationError):
        apply_migrations(tmp_path / "jobs.db", to_version="2")


def test_corrupt_database_raises_documented_error_and_keeps_bytes(tmp_path) -> None:
    path = tmp_path / "jobs.db"
    path.write_bytes(b"not a sqlite file\x00\x01\x02")

    with pytest.raises(MigrationError) as excinfo:
        apply_migrations(path)
    assert isinstance(excinfo.value, OmniFrameError)
    assert excinfo.value.code == "E_MIGRATION"
    assert path.read_bytes() == b"not a sqlite file\x00\x01\x02", "never wiped"


def test_current_version_on_a_corrupt_database_raises(tmp_path) -> None:
    path = tmp_path / "jobs.db"
    path.write_bytes(b"garbage")
    with pytest.raises(MigrationError):
        current_version(path)


def test_non_persistent_targets_are_rejected() -> None:
    for target in (":memory:", "file:jobs?mode=memory&cache=shared"):
        with pytest.raises(ValidationError) as excinfo:
            apply_migrations(target)
        assert excinfo.value.code == "E_VALIDATION"


def test_database_from_a_newer_build_is_refused(tmp_path) -> None:
    path = tmp_path / "jobs.db"
    apply_migrations(path)
    with sqlite3.connect(str(path)) as conn:
        conn.execute(
            f"INSERT INTO {GUARD_TABLE} (version, applied_at) VALUES (?, ?)",
            (LATEST_VERSION + 1, "2027-01-01T00:00:00+00:00"),
        )
        conn.commit()

    with pytest.raises(MigrationError):
        apply_migrations(path)
    assert current_version(path) == LATEST_VERSION + 1, "the file is untouched"


# -- the Phase 2 job store now opens through this chain ----------------------


def test_job_store_opens_at_the_latest_schema_version(tmp_path) -> None:
    store = JobStore(db_path=tmp_path / "jobs.db")

    assert current_version(store.db_path) == LATEST_VERSION
    store.create_job(
        id="job-1", kind="render", status="queued", workspace=str(tmp_path / "ws")
    )
    assert store.get_job("job-1") is not None


def test_reopening_a_job_store_does_not_reapply_migrations(tmp_path) -> None:
    db_path = tmp_path / "jobs.db"
    JobStore(db_path=db_path)
    first = _guard_rows(db_path)

    JobStore(db_path=db_path)
    assert _guard_rows(db_path) == first


def test_job_store_rejects_an_in_memory_target() -> None:
    # A per-operation connection cannot share an in-memory schema, so the store
    # fails loudly instead of raising "no such table: jobs" on first use.
    with pytest.raises(ValidationError):
        JobStore(db_path=":memory:")


def test_pending_migrations_apply_in_ascending_order(tmp_path, monkeypatch) -> None:
    second = migration_registry.Migration(
        version=2,
        name="test_extra_table",
        statements=("CREATE TABLE IF NOT EXISTS extra (id INTEGER);",),
    )
    monkeypatch.setattr(
        migration_registry, "MIGRATIONS", (*migration_registry.MIGRATIONS, second)
    )
    monkeypatch.setattr(migration_registry, "KNOWN_VERSIONS", frozenset({1, 2}))

    path = tmp_path / "jobs.db"
    assert migration_registry.apply_migrations(path, to_version=2) == 2
    assert [row[0] for row in _guard_rows(path)] == [1, 2]
    assert set(_tables(path)) == {"jobs", "extra", GUARD_TABLE}


def test_migrating_below_the_current_version_is_refused(tmp_path, monkeypatch) -> None:
    second = migration_registry.Migration(
        version=2,
        name="test_extra_table",
        statements=("CREATE TABLE IF NOT EXISTS extra (id INTEGER);",),
    )
    monkeypatch.setattr(
        migration_registry, "MIGRATIONS", (*migration_registry.MIGRATIONS, second)
    )
    monkeypatch.setattr(migration_registry, "KNOWN_VERSIONS", frozenset({1, 2}))

    path = tmp_path / "jobs.db"
    migration_registry.apply_migrations(path, to_version=2)
    with pytest.raises(ValidationError) as excinfo:
        migration_registry.apply_migrations(path, to_version=1)

    assert excinfo.value.code == "E_VALIDATION"
    assert current_version(path) == 2, "a refused downgrade changes nothing"


