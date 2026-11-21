"""Job lifecycle manager: queues, runs and coordinates durable jobs.

Task 2 of the Phase 2 hardening plan. :class:`JobManager` owns a bounded pool
of worker threads that claims ``queued`` jobs written by :class:`JobStore`,
runs a registered per-``kind`` callable with cooperative cancellation, and
records the terminal outcome (``done`` / ``failed`` / ``canceled``) back
through the same store so lifecycle state survives across restarts.

Workers call ``callable(payload, cancel=<CancelFlag>)`` when the callable
accepts a ``cancel`` keyword (falling back to ``callable(payload)``). The
``CancelFlag`` is shared with :meth:`JobManager.cancel`, so a running worker
can stop at cooperative checkpoints.
"""

from __future__ import annotations

import inspect
import queue
import threading
import uuid
from collections.abc import Callable
from typing import Any

from ..core.errors import ValidationError
from ..engines.compositor.ffmpeg import CancelFlag
from .store import JobStore

#: Stock worker kinds that are always treated as registered names, even when no
#: concrete callable is supplied. They map to real worker folds in later
#: phases; without a registered callable a job of this kind is marked ``failed``
#: with a clear message rather than crashing the pool.
_STOCK_KINDS: tuple[str, ...] = ("render", "compose", "translate", "validate")

#: Upper bound (seconds) for the threads in :meth:`JobManager.shutdown` to
#: finish after their cancel flags are set, so shutdown stays a bounded join.
_JOIN_TIMEOUT = 5.0

#: Worker queue poll interval (seconds). Keeps ``shutdown`` responsive while a
#: worker waits for the next job id.
_POLL_INTERVAL = 0.05


def _accepts_cancel(callable: Callable[..., Any]) -> bool:
    """Best-effort check whether ``callable`` can take a ``cancel`` keyword."""
    try:
        parameters = inspect.signature(callable).parameters
    except (TypeError, ValueError):
        return False
    if "cancel" in parameters:
        return True
    return any(p.kind is inspect.Parameter.VAR_KEYWORD for p in parameters.values())


class JobManager:
    """Queues and runs jobs against a :class:`JobStore` on worker threads.

    Args:
        store: The :class:`JobStore` that persists job records. The store opens a
            fresh connection per operation, so it is safe to share across the
            worker threads.
        workers: Maximum number of jobs to run concurrently (default 2, minimum 1).
        registry: Optional mapping of ``kind -> callable(payload, *, cancel=None)``.
            Missing stock kinds without a callable are allowed by :meth:`submit`
            but their jobs are marked ``failed`` when claimed; submitting a kind
            that is neither stock nor in ``registry`` raises :class:`ValidationError`.
    """

    def __init__(
        self,
        store: JobStore,
        workers: int = 2,
        *,
        registry: dict[str, Callable[..., Any]] | None = None,
    ) -> None:
        self._store = store
        self._workers = max(1, int(workers))
        self._registry: dict[str, Callable[..., Any]] = dict(registry or {})
        #: Every name accepted by ``submit``: the stock kinds plus any explicit
        #: registry keys (an explicit entry overrides the same stock name).
        self._kinds: set[str] = set(_STOCK_KINDS) | set(self._registry)

        self._queue: queue.Queue[str] = queue.Queue()
        self._shutdown = threading.Event()
        self._cancel_flags: dict[str, CancelFlag] = {}
        self._flags_lock = threading.Lock()
        self._threads: list[threading.Thread] = []

        for _ in range(self._workers):
            thread = threading.Thread(target=self._run_worker, daemon=True)
            self._threads.append(thread)
            thread.start()

    # -- public API -------------------------------------------------------

    def submit(self, kind: str, payload: Any = None, owner: str | None = None) -> str:
        """Persist a ``queued`` job and return its ``job_id`` immediately.

        The job is enqueued for the worker pool without blocking the caller.
        Raises :class:`ValidationError` when ``kind`` is not a registered kind.
        """
        if kind not in self._kinds:
            raise ValidationError(
                f"unknown job kind {kind!r}; registered kinds: {self._registered_kinds()}",
                kind=kind,
                registered=sorted(self._kinds),
            )
        job_id = uuid.uuid4().hex
        self._store.create_job(
            id=job_id,
            kind=kind,
            status="queued",
            workspace=self._workspace(),
            payload=payload,
            owner=owner,
        )
        self._enqueue(job_id)
        return job_id

    def status(self, job_id: str) -> dict[str, Any] | None:
        """Return the job record (from the store) or ``None`` if unknown."""
        return self._store.get_job(job_id)

    def cancel(self, job_id: str) -> dict[str, Any] | None:
        """Set the job's ``CancelFlag`` and mark the job ``canceled``.

        A running worker observes the flag at cooperative points and stops; a
        still-queued job is skipped when the worker next claims it. Returns the
        updated job record, or ``None`` if the job does not exist.
        """
        if self._store.get_job(job_id) is None:
            return None
        with self._flags_lock:
            flag = self._cancel_flags.get(job_id)
        if flag is not None:
            flag.cancel()
        return self._store.update_job(job_id, status="canceled")

    def retry(self, job_id: str) -> dict[str, Any] | None:
        """Re-queue a ``failed`` or ``canceled`` job, bumping ``attempts``.

        Any other current status raises :class:`ValidationError`. Returns the
        updated job record, or ``None`` if the job does not exist.
        """
        job = self._store.get_job(job_id)
        if job is None:
            return None
        if job["status"] not in ("failed", "canceled"):
            raise ValidationError(
                f"only failed or canceled jobs may be retried, got {job['status']!r}",
                job_id=job_id,
                status=job["status"],
            )
        attempts = int(job["attempts"] or 0) + 1
        self._store.update_job(job_id, status="queued", attempts=attempts)
        self._enqueue(job_id)
        return self._store.get_job(job_id)

    def shutdown(self) -> None:
        """Cancel all running/queued jobs and wait for workers (bounded join).

        Idempotent: calling it more than once is safe and returns immediately
        after the first call completes.
        """
        if self._shutdown.is_set():
            return
        self._shutdown.set()

        with self._flags_lock:
            flags = list(self._cancel_flags.values())
        for flag in flags:
            flag.cancel()
        # Any job still marked running was interrupted by the cancel above.
        for job in self._store.list_jobs(status="running"):
            self._store.update_job(job["id"], status="canceled")

        for thread in self._threads:
            thread.join(timeout=_JOIN_TIMEOUT)
        self._threads.clear()

    # -- internal helpers ---------------------------------------------------

    def _workspace(self) -> str:
        """A stable workspace label derived from the store's db location."""
        return str(self._store.db_path.parent)

    def _registered_kinds(self) -> str:
        return ", ".join(sorted(self._kinds))

    def _enqueue(self, job_id: str) -> None:
        if not self._shutdown.is_set():
            self._queue.put(job_id)

    def _run_worker(self) -> None:
        while not self._shutdown.is_set():
            try:
                job_id = self._queue.get(timeout=_POLL_INTERVAL)
            except queue.Empty:
                continue
            try:
                self._execute(job_id)
            except Exception:  # pragma: no cover - defense in depth
                # Failures inside a single job must not tear down the worker.
                self._store.update_job(
                    job_id,
                    status="failed",
                    error="unexpected worker failure",
                )
            finally:
                self._queue.task_done()

    def _execute(self, job_id: str) -> None:
        flag = CancelFlag()
        with self._flags_lock:
            self._cancel_flags[job_id] = flag
        try:
            job = self._store.get_job(job_id)
            if job is None:
                return
            if job["status"] == "canceled":
                return
            self._store.update_job(job_id, status="running")

            callable_ = self._registry.get(job["kind"])
            if callable_ is None:
                # Known stock kind with no concrete worker registered: record a
                # clear failure instead of crashing the pool.
                self._store.update_job(
                    job_id,
                    status="failed",
                    error=(
                        f"no worker registered for job kind {job['kind']!r}; "
                        f"registered kinds: {self._registered_kinds()}"
                    ),
                )
                return

            if _accepts_cancel(callable_):
                result = callable_(job["payload"], cancel=flag)
            else:
                result = callable_(job["payload"])

            refreshed = self._store.get_job(job_id)
            # A cancel may land while the callable is returning (e.g. during
            # shutdown, which sets the flag before joining). Honor the in-memory
            # flag directly so the job is deterministically left ``canceled``
            # rather than being overwritten with ``done`` by a store-time race.
            if flag.cancelled:
                self._store.update_job(job_id, status="canceled")
                return
            if refreshed is not None and refreshed["status"] == "canceled":
                return  # canceled while running; keep it canceled.
            self._store.update_job(job_id, status="done", result=result)
        except Exception as exc:
            self._store.update_job(job_id, status="failed", error=str(exc))
        finally:
            with self._flags_lock:
                self._cancel_flags.pop(job_id, None)


__all__ = ["JobManager"]