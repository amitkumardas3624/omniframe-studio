"""Workspace and path containment policy for OmniFrame jobs.

Jobs only touch files under their own sandbox directory, ``<root>/.omniframe``.
``resolve_workspace`` materialises that directory and returns its absolute path;
``ensure_within`` guards every candidate path a job hands us so no file can be
read or written outside the workspace root (path traversal, absolute shortcuts
that resolve elsewhere, or a Windows drive change) without raising
:class:`~omniframe.core.errors.PathSecurityError`.

This module also hosts process and browser resource bounds: ``launch_guarded``
runs a subprocess (argument list, no shell) with cancel/timeout kill semantics,
and ``browser_sandbox_args`` yields the Chromium flags used to keep a render
browser's disk/IO footprint bounded.
"""

from __future__ import annotations

import subprocess
import time
from collections.abc import Sequence
from pathlib import Path
from typing import TYPE_CHECKING, NoReturn

from ..core.errors import OmniFrameError, PathSecurityError, ValidationError

if TYPE_CHECKING:  # pragma: no cover - type-only, avoids an import cycle
    from ..engines.compositor.ffmpeg import CancelFlag


def resolve_workspace(root: str | Path) -> Path:
    """Create (if needed) and return the absolute workspace dir ``<root>/.omniframe``.

    Refuses an empty, whitespace-only, filesystem-root or bare root (a path with
    no directory name) via :class:`ValidationError`.
    """
    raw = "" if root is None else str(root)
    if not raw.strip():
        raise ValidationError(
            "workspace root must be a non-empty path", root=str(root)
        )
    base = Path(raw).expanduser()
    if not base.name:
        raise ValidationError(
            "workspace root must include a directory name; got a bare/root path",
            root=str(root),
        )
    ws = (base / ".omniframe").resolve(strict=False)
    ws.mkdir(parents=True, exist_ok=True)
    return ws


def ensure_within(workspace: str | Path, candidate: str | Path) -> Path:
    """Resolve and return ``candidate``, raising if it escapes ``workspace``.

    Both are resolved to absolute paths (``strict=False`` so not-yet-existing
    files are accepted). A candidate equal to ``workspace`` itself is allowed.
    Raises :class:`PathSecurityError` on path traversal (``..`` above the root),
    an absolute shortcut/symlink resolving outside, or a Windows drive change.
    """
    ws = Path(workspace).expanduser().resolve(strict=False)
    cand = Path(candidate).expanduser().resolve(strict=False)

    # Reject a drive change when both sides carry one (Windows; empty on POSIX).
    if ws.drive and cand.drive and ws.drive.lower() != cand.drive.lower():
        raise PathSecurityError(
            "candidate path is on a different drive than the workspace",
            workspace=str(ws),
            candidate=str(cand),
        )

    if ws == cand:
        return cand

    try:
        cand.relative_to(ws)
    except ValueError:
        raise PathSecurityError(
            "candidate path escapes the workspace root",
            workspace=str(ws),
            candidate=str(cand),
        ) from None
    return cand


# ---------------------------------------------------------------------------
# Process and browser resource bounds (Task 4)
# ---------------------------------------------------------------------------

def _terminate_guarded(
    proc: subprocess.Popen[str],
    argv: Sequence[str],
    *,
    timeout: float,
    canceled: bool,
) -> NoReturn:
    """Kill ``proc``, drain its output, and raise with a bounded stderr tail."""
    try:
        proc.kill()
    except OSError:  # pragma: no cover - already gone
        pass
    stderr = ""
    try:
        _, stderr = proc.communicate(timeout=5)
    except subprocess.TimeoutExpired:  # pragma: no cover - defensive
        try:
            proc.kill()
        except OSError:  # pragma: no cover
            pass
        try:
            if proc.stderr is not None:
                proc.stderr.read()
        except OSError:  # pragma: no cover
            pass
    reason = "canceled" if canceled else f"timed out after {timeout:g}s"
    tail = (stderr or "").strip()[-2000:]
    message = f"subprocess {reason}."
    if tail:
        message = f"{message} stderr tail: {tail}"
    raise OmniFrameError(message, argv=list(argv), stderr=tail, returncode=proc.returncode)


def launch_guarded(
    argv: Sequence[str],
    *,
    cwd: str | Path,
    cancel: CancelFlag | None,
    timeout: float,
) -> subprocess.CompletedProcess[str]:
    """Run ``argv`` (list args, no shell) bounded by ``timeout`` and ``cancel``.

    Launches the program with :class:`subprocess.Popen` (``cwd`` given, stdout
    and stderr captured as pipes) and polls ``cancel.cancelled`` on a short
    interval (0.05s).  On explicit cancel or after ``timeout`` seconds the
    process is killed and an :class:`~omniframe.core.errors.OmniFrameError` is
    raised with the (bounded) tail of stderr.  On a normal exit a
    :class:`subprocess.CompletedProcess` carrying ``returncode``, ``stdout`` and
    ``stderr`` is returned.  A pre-cancelled flag aborts before launch.
    """
    if cancel is not None and cancel.cancelled:
        raise OmniFrameError(
            "subprocess canceled before launch.",
            argv=list(argv),
        )

    deadline = time.monotonic() + max(float(timeout), 0.0)
    try:
        proc = subprocess.Popen(
            list(argv),
            cwd=str(cwd),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
    except OSError as exc:
        raise OmniFrameError(
            f"subprocess could not be executed: {exc}",
            argv=list(argv),
        ) from exc

    try:
        while proc.poll() is None:
            if cancel is not None and cancel.cancelled:
                _terminate_guarded(proc, argv, timeout=timeout, canceled=True)
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                _terminate_guarded(proc, argv, timeout=timeout, canceled=False)
            time.sleep(min(0.05, max(remaining, 0.0)))
        stdout, stderr = proc.communicate()
    except OSError as exc:
        raise OmniFrameError(
            f"subprocess could not be executed: {exc}",
            argv=list(argv),
        ) from exc
    return subprocess.CompletedProcess(list(argv), proc.returncode, stdout, stderr)


def browser_sandbox_args() -> list[str]:
    """Chromium flags that bound the browser's disk/IO footprint.

    Disables the shared-memory usage optimiser, background networking and the
    first-run dialog so a render browser stays lean and does not phone home.
    """
    return ["--disable-dev-shm-usage", "--disable-background-networking", "--no-first-run"]


__all__ = [
    "browser_sandbox_args",
    "ensure_within",
    "launch_guarded",
    "resolve_workspace",
    "PathSecurityError",
]