"""Durable local job lifecycle.

Task 1 provides the SQLite-backed :class:`~omniframe.jobs.store.JobStore` and
re-exports the Phase 1 :class:`~omniframe.engines.compositor.ffmpeg.CancelFlag`;
Task 2 adds the :class:`~omniframe.jobs.manager.JobManager` lifecycle manager.
Together they give job-facing code a single clean import surface.
"""

from __future__ import annotations

from ..engines.compositor.ffmpeg import CancelFlag
from .manager import JobManager
from .store import JOB_STATUSES, JobStore

__all__ = ["CancelFlag", "JOB_STATUSES", "JobManager", "JobStore"]