"""Tests for the durable SQLite-backed :class:`JobStore`."""

from __future__ import annotations

import pytest

from omniframe.core.errors import ValidationError
from omniframe.jobs import JobStore


def _mk(tmp_path) -> JobStore:
    return JobStore(db_path=tmp_path / "jobs.db")


def test_create_get_round_trip(tmp_path):
    store = _mk(tmp_path)
    job_id = store.create_job(
        id="job-1",
        kind="render",
        status="queued",
        workspace=str(tmp_path / "workspace"),
        payload={"scene": "intro", "frames": 120},
        owner="amit",
    )

    job = store.get_job(job_id)
    assert job is not None
    assert job["id"] == "job-1"
    assert job["kind"] == "render"
    assert job["status"] == "queued"
    assert job["workspace"] == str(tmp_path / "workspace")
    assert job["owner"] == "amit"
    assert job["payload"] == {"scene": "intro", "frames": 120}
    assert job["result"] is None
    assert job["attempts"] == 0
    assert job["created_at"] == job["updated_at"]


def test_get_missing_returns_none(tmp_path):
    assert _mk(tmp_path).get_job("nope") is None


def test_update_merges_fields_and_bumps_updated_at(tmp_path):
    store = _mk(tmp_path)
    store.create_job(
        id="j", kind="compose", status="queued", workspace=str(tmp_path), payload={"a": 1}
    )
    original = store.get_job("j")

    updated = store.update_job(
        "j", status="running", payload={"a": 2, "b": True}, attempts=1
    )

    assert updated is not None
    assert updated["status"] == "running"
    assert updated["payload"] == {"a": 2, "b": True}
    assert updated["attempts"] == 1
    assert updated["updated_at"] != original["updated_at"]
    # Other fields preserved.
    assert updated["kind"] == "compose"
    assert updated["created_at"] == original["created_at"]


def test_update_returns_none_for_missing(tmp_path):
    assert _mk(tmp_path).update_job("ghost", status="done") is None


def test_list_all_and_filter_by_status(tmp_path):
    store = _mk(tmp_path)
    store.create_job(id="a", kind="render", status="queued", workspace=str(tmp_path))
    store.create_job(id="b", kind="render", status="done", workspace=str(tmp_path))
    store.create_job(id="c", kind="render", status="queued", workspace=str(tmp_path))

    all_jobs = store.list_jobs()
    assert [j["id"] for j in all_jobs] == ["a", "b", "c"]

    queued = store.list_jobs(status="queued")
    assert [j["id"] for j in queued] == ["a", "c"]

    done = store.list_jobs(status="done")
    assert [j["id"] for j in done] == ["b"]


def test_delete_removes_job(tmp_path):
    store = _mk(tmp_path)
    store.create_job(id="bye", kind="translate", status="done", workspace=str(tmp_path))

    assert store.delete_job("bye") is True
    assert store.get_job("bye") is None
    # Deleting again is a no-op.
    assert store.delete_job("bye") is False


def test_empty_kind_raises_validation_error(tmp_path):
    store = _mk(tmp_path)
    with pytest.raises(ValidationError) as exc:
        store.create_job(id="x", kind="", status="queued", workspace=str(tmp_path))
    assert exc.value.code == "E_VALIDATION"


def test_unknown_status_raises_validation_error(tmp_path):
    store = _mk(tmp_path)
    with pytest.raises(ValidationError):
        store.create_job(
            id="x", kind="render", status="bogus", workspace=str(tmp_path)
        )


def test_invalid_status_supplied_to_update_raises(tmp_path):
    store = _mk(tmp_path)
    store.create_job(id="x", kind="render", status="queued", workspace=str(tmp_path))
    with pytest.raises(ValidationError):
        store.update_job("x", status="invalid")


def test_workspace_derived_default_db_path(tmp_path):
    store = JobStore(workspace=tmp_path)
    assert store.db_path == (tmp_path / ".omniframe" / "jobs.db")
    assert store.db_path.exists()