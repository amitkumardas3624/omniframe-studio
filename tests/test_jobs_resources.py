"""Tests for process and browser resource bounds (:mod:`omniframe.jobs.safety`).

Covers ``launch_guarded`` cancel/timeout/kill semantics, the exact browser
sandbox flag set, and the additive, default-neutral ``sandbox`` flag on
``PlaywrightBackend``.
"""

from __future__ import annotations

import sys

import pytest

from omniframe.core.errors import OmniFrameError
from omniframe.engines.code_video.backends import PlaywrightBackend
from omniframe.engines.compositor.ffmpeg import CancelFlag
from omniframe.jobs.safety import browser_sandbox_args, launch_guarded

# Keep the process bounded: a short sleep means a pre-cancel / timeout check
# returns quickly regardless of how fast the child starts.
_SLUMBER = "import time; time.sleep(30)"


def test_launch_guarded_returns_rc_zero(tmp_path):
    proc = launch_guarded(
        [sys.executable, "-c", "print('hi')"],
        cwd=tmp_path,
        cancel=CancelFlag(),
        timeout=30,
    )
    assert proc.returncode == 0
    assert "hi" in (proc.stdout or "")


def test_launch_guarded_pre_cancelled_kills_and_raises(tmp_path):
    cancel = CancelFlag()
    cancel.cancel()
    with pytest.raises(OmniFrameError):
        launch_guarded(
            [sys.executable, "-c", "print('start')", _SLUMBER],
            cwd=tmp_path,
            cancel=cancel,
            timeout=10,
        )


def test_launch_guarded_timeout_kills_and_raises(tmp_path):
    with pytest.raises(OmniFrameError):
        launch_guarded(
            [sys.executable, "-c", _SLUMBER],
            cwd=tmp_path,
            cancel=CancelFlag(),
            timeout=0.05,
        )


def test_launch_guarded_never_passes_shell(tmp_path):
    # No shell=True path is exercised: an argv that would need a shell (a bare
    # command with operators) must still run via argument-list Popen.
    # Launch is expected to fail (no such program, so Popen raises OSError and
    # launch_guarded wraps it) -- crucially it must go through Popen, not a
    # shell. This asserts the argv is treated as a program list.
    with pytest.raises(OmniFrameError):
        launch_guarded(
            ["__definitely_not_a_real_binary___", "a && b"],
            cwd=tmp_path,
            cancel=CancelFlag(),
            timeout=5,
        )


def test_browser_sandbox_args_exact_strings():
    assert browser_sandbox_args() == [
        "--disable-dev-shm-usage",
        "--disable-background-networking",
        "--no-first-run",
    ]


def test_playwright_sandbox_true_adds_sandbox_args():
    backend = PlaywrightBackend(sandbox=True)
    for flag in browser_sandbox_args():
        assert flag in backend.browser_args


def test_playwright_default_is_unchanged_and_contains_no_sandbox():
    default = PlaywrightBackend()
    for flag in browser_sandbox_args():
        assert flag not in default.browser_args
    # Default flags are preserved.
    assert "--force-color-profile=srgb" in default.browser_args


def test_browser_sandbox_args_does_not_mutate_default():
    expected_default = [
        "--force-color-profile=srgb",
        "--disable-lcd-text",
        "--font-render-hinting=none",
    ]
    # Run the sandboxed path first, then confirm a fresh default is untouched.
    with_sandbox = PlaywrightBackend(sandbox=True)
    assert with_sandbox.browser_args != expected_default
    fresh_default = PlaywrightBackend()
    assert fresh_default.browser_args == expected_default
    # The constructor always copies, so mutating one instance never leaks.
    with_sandbox.browser_args.append("--extra-virtual")
    assert "--extra-virtual" not in PlaywrightBackend().browser_args