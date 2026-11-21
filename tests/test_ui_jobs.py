"""HTTP smoke test for the Phase 2 job queue endpoints (Task 2 UI).

Submits a trivial job through the FastAPI app and cancels it, asserting HTTP
200 and job status transitions. This mirrors what the Web UI Jobs panel does:
``GET /api/v1/jobs``, ``POST /api/v1/jobs`` (submit) and
``POST /api/v1/jobs/{job_id}/cancel``.

Guarded so the module skips (not fails) when FastAPI is missing or when the
Phase 2 ``jobs`` package is not importable (routes are absent in that build).
"""

from __future__ import annotations

import pytest

fastapi = pytest.importorskip("fastapi")  # noqa: F841  (skips module if missing)
pytest.importorskip("omniframe.jobs")  # skips module when Phase 2 jobs absent

from fastapi.testclient import TestClient  # noqa: E402

from omniframe.backend.server import create_app  # noqa: E402

#: Statuses the job store may be in at any point (used to avoid asserting an
#: intermediate transition, whose timing depends on worker scheduling).
_JOB_STATUSES = {"queued", "running", "paused", "done", "failed", "canceled"}


def _wait_status(client, job_id, statuses, timeout=5.0):
    import time

    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        response = client.get(f"/api/v1/jobs/{job_id}")
        assert response.status_code == 200
        job = response.json()
        if job["success"] and job["result"]["status"] in statuses:
            return job["result"]
        time.sleep(0.01)
    raise AssertionError(
        f"job {job_id} did not reach {sorted(statuses)}; last={job}"
    )


def test_submit_and_cancel_job_via_http() -> None:
    with TestClient(create_app()) as client:
        # Submit a trivial job with a stock Phase 2 kind.
        submit = client.post(
            "/api/v1/jobs",
            json={"kind": "validate", "payload": {"probe": True}, "owner": "ui-test"},
        )
        assert submit.status_code == 200, submit.text
        body = submit.json()
        assert body["success"] is True
        job_id = body["result"]["job_id"]
        assert job_id

        # Single-job status is retrievable and in a valid lifecycle state.
        detail = client.get(f"/api/v1/jobs/{job_id}")
        assert detail.status_code == 200
        assert detail.json()["success"] is True
        assert detail.json()["result"]["id"] == job_id
        assert detail.json()["result"]["status"] in _JOB_STATUSES
        assert detail.json()["result"]["kind"] == "validate"

        # Cancel returns HTTP 200 and the job settles in the canceled state
        # (cancel() flips any non-terminal/lifecycle state to canceled).
        cancel = client.post(f"/api/v1/jobs/{job_id}/cancel")
        assert cancel.status_code == 200, cancel.text
        canceled = _wait_status(client, job_id, {"canceled"})
        assert canceled["status"] == "canceled"

        # The canceled job shows up in the list endpoint the UI consumes.
        listing = client.get("/api/v1/jobs")
        assert listing.status_code == 200
        assert listing.json()["success"] is True
        assert job_id in {job["id"] for job in listing.json()["result"]}


def test_jobs_endpoints_registered_on_app() -> None:
    """The job routes are present/registered when jobs is importable."""
    app = create_app()
    paths = {route.path for route in app.routes}
    assert "/api/v1/jobs" in paths
    assert "/api/v1/jobs/{job_id}" in paths
    assert "/api/v1/jobs/{job_id}/cancel" in paths