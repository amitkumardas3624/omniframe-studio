"""Tests for the :class:`JobManager` job lifecycle.

Uses small in-thread callables (no real ffmpeg) so the tests are deterministic
and fast. ``results.json`` and ``cancel_flag`` payloads keep the worker folds
self-contained.
"""

from __future__ import annotations

import time

import pytest

from omniframe.core.errors import ValidationError
from omniframe.jobs import JobManager, JobStore

# --------------------------------------------------------------------------- #
# helpers
# --------------------------------------------------------------------------- #


def _mk_manager(tmp_path, registry=None, workers=2) -> tuple[JobManager, JobStore]:
    store = JobStore(db_path=tmp_path / "jobs.db")
    return JobManager(store, workers=workers, registry=registry), store


def _wait_status(mgr, job_id, statuses, timeout=5.0):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        job = mgr.status(job_id)
        if job is not None and job["status"] in statuses:
            return job
        time.sleep(0.01)
    raise AssertionError(
        f"job {job_id} did not reach {statuses}; got {mgr.status(job_id)}"
    )


def _add(payload, cancel=None):
    """Deterministic success worker."""
    assert cancel is not None
    return {"value": payload["a"] + payload["b"]}


def _sleeper(payload, cancel=None):
    """Sleeps for payload['seconds'] but returns early on cancel."""
    deadline = time.monotonic() + payload["seconds"]
    while time.monotonic() < deadline:
        if cancel is not None and cancel.cancelled:
            return {"slept": False}
        time.sleep(0.01)
    return {"slept": True}


def _boom(payload, cancel=None):
    raise RuntimeError("kaboom")


# --------------------------------------------------------------------------- #
# lifecycle tests
# --------------------------------------------------------------------------- #


def test_submit_runs_to_done_and_persists_result(tmp_path):
    mgr, _ = _mk_manager(tmp_path, registry={"add": _add})
    try:
        job_id = mgr.submit("add", {"a": 2, "b": 3})
        # With a fast in-memory worker the job may already be terminal by the
        # time we read it, so do not assert an intermediate status; wait for the
        # terminal result directly (deterministic regardless of scheduling).
        done = _wait_status(mgr, job_id, {"done", "failed"})
        assert done["status"] == "done"
        assert done["result"] == {"value": 5}
    finally:
        mgr.shutdown()


def test_submit_returns_in_owned_workspace(tmp_path):
    mgr, store = _mk_manager(tmp_path, registry={"add": _add})
    try:
        job_id = mgr.submit("add", {"a": 1, "b": 1})
        job = mgr.status(job_id)
        assert job["workspace"] == str(store.db_path.parent)
    finally:
        mgr.shutdown()


def test_retry_increments_attempts_and_reruns(tmp_path):
    state = {"calls": 0}

    def _flaky(payload, cancel=None):
        state["calls"] += 1
        if state["calls"] == 1:
            raise RuntimeError("first attempt fails")
        return {"attempt": state["calls"]}

    mgr, _ = _mk_manager(tmp_path, registry={"flaky": _flaky})
    try:
        job_id = mgr.submit("flaky", {})
        failed = _wait_status(mgr, job_id, {"done", "failed"})
        assert failed["status"] == "failed"
        assert state["calls"] == 1
        assert failed["attempts"] == 0

        retried = mgr.retry(job_id)
        # `retry` re-queues the job, bumping attempts. A free worker may claim
        # and re-run it (the fast callable) before this read, flipping it past
        # ``queued``/``running``, so assert only the stable attempts bump here;
        # the terminal outcome is checked deterministically via `_wait_status`.
        assert retried["attempts"] == 1

        done = _wait_status(mgr, job_id, {"done", "failed"})
        assert done["status"] == "done"
        assert done["attempts"] == 1
        assert done["result"] == {"attempt": 2}
        assert state["calls"] == 2
    finally:
        mgr.shutdown()


def test_retry_rejects_non_terminal_status(tmp_path):
    mgr, _ = _mk_manager(tmp_path, registry={"add": _add})
    try:
        job_id = mgr.submit("add", {"a": 1, "b": 1})
        _wait_status(mgr, job_id, {"done", "failed"})
        with pytest.raises(ValidationError) as exc:
            mgr.retry(job_id)
        assert exc.value.code == "E_VALIDATION"
    finally:
        mgr.shutdown()


def test_cancel_sleeping_job_marks_canceled(tmp_path):
    mgr, _ = _mk_manager(tmp_path, registry={"sleeper": _sleeper})
    try:
        job_id = mgr.submit("sleeper", {"seconds": 5.0})
        _wait_status(mgr, job_id, {"running"})
        mgr.cancel(job_id)
        assert mgr.status(job_id)["status"] == "canceled"
    finally:
        mgr.shutdown()


def test_unknown_kind_raises_validation_error_listing_registered(tmp_path):
    mgr, _ = _mk_manager(tmp_path, registry={"add": _add})
    try:
        with pytest.raises(ValidationError) as exc:
            mgr.submit("bogus", {})
        assert exc.value.code == "E_VALIDATION"
        message = str(exc.value)
        # Lists the registered kinds (both stock and custom).
        assert "add" in message
        assert "render" in message  # a stock kind is listed too
    finally:
        mgr.shutdown()


def test_stock_kind_without_callable_marks_failed_not_crash(tmp_path):
    mgr, _ = _mk_manager(tmp_path, registry={})  # no render worker registered
    try:
        job_id = mgr.submit("render", {"file": "scene"})
        failed = _wait_status(mgr, job_id, {"done", "failed"})
        assert failed["status"] == "failed"
        assert "no worker registered" in failed["error"]
    finally:
        mgr.shutdown()


def test_failure_records_error(tmp_path):
    mgr, _ = _mk_manager(tmp_path, registry={"boom": _boom})
    try:
        job_id = mgr.submit("boom", {})
        failed = _wait_status(mgr, job_id, {"done", "failed"})
        assert failed["status"] == "failed"
        assert failed["error"] == "kaboom"
        assert failed["result"] is None
    finally:
        mgr.shutdown()


def test_shutdown_is_idempotent_and_cancels_running(tmp_path):
    mgr, _ = _mk_manager(tmp_path, registry={"sleeper": _sleeper})
    job_id = mgr.submit("sleeper", {"seconds": 5.0})
    _wait_status(mgr, job_id, {"running"})

    mgr.shutdown()
    # Running work was marked canceled.
    assert mgr.status(job_id)["status"] == "canceled"

    # A second shutdown is a safe no-op.
    mgr.shutdown()
    mgr.shutdown()


def test_cancel_running_job_keeps_canceled_after_worker_exits(tmp_path):
    mgr, _ = _mk_manager(tmp_path, registry={"sleeper": _sleeper})
    try:
        job_id = mgr.submit("sleeper", {"seconds": 5.0})
        _wait_status(mgr, job_id, {"running"})
        mgr.cancel(job_id)
        # The sleeping worker notices the flag and returns early; the manager
        # must leave the job canceled instead of overwriting it with ``done``.
        time.sleep(0.2)
        assert mgr.status(job_id)["status"] == "canceled"
        assert mgr.status(job_id)["result"] is None
    finally:
        mgr.shutdown()