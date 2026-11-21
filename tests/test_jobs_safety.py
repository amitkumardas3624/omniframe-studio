"""Tests for workspace and path policy (:mod:`omniframe.jobs.safety`)."""

from __future__ import annotations

import os

import pytest

from omniframe.core.errors import PathSecurityError, ValidationError
from omniframe.jobs.safety import ensure_within, resolve_workspace


def test_nested_path_inside_workspace_is_allowed(tmp_path):
    ws = resolve_workspace(tmp_path)
    nested = ws / "scenes" / "intro.omni.mp4"
    assert ensure_within(ws, nested) == nested.resolve()


def test_workspace_root_itself_is_allowed(tmp_path):
    ws = resolve_workspace(tmp_path)
    assert ensure_within(ws, ws) == ws


def test_dotdot_escape_is_rejected(tmp_path):
    ws = resolve_workspace(tmp_path)
    with pytest.raises(PathSecurityError):
        ensure_within(ws, tmp_path / ".." / "outside.txt")


def test_absolute_path_outside_root_is_rejected(tmp_path):
    ws = resolve_workspace(tmp_path)
    outside = tmp_path / ".." / "somewhere" / "else.txt"
    with pytest.raises(PathSecurityError):
        ensure_within(ws, outside)


def test_second_drive_worth_of_root_is_rejected(tmp_path):
    # On Windows a distinct drive root is outside the workspace; on POSIX
    # nothing below a different anchor is ever under the workspace either.
    ws = resolve_workspace(tmp_path)
    if ws.drive:
        other = ws.drive + "\\other\\file.txt"
    else:
        other = "/etc/passwd"
    with pytest.raises(PathSecurityError):
        ensure_within(ws, other)


def test_resolve_workspace_creates_missing_omniframe_dir(tmp_path):
    target = tmp_path / "brand-new"
    ws = resolve_workspace(target)
    assert ws == (target / ".omniframe").resolve()
    assert ws.is_dir()


def test_resolve_workspace_returns_absolute_path(tmp_path, monkeypatch):
    # A relative root is normalised to an absolute path.
    monkeypatch.chdir(tmp_path)
    rel = tmp_path / "proj"
    ws = resolve_workspace("proj")
    assert ws.is_absolute()
    assert ws == (rel / ".omniframe").resolve()
    assert ws.name == ".omniframe"


def test_resolve_workspace_rejects_empty_root():
    with pytest.raises(ValidationError):
        resolve_workspace("")
    with pytest.raises(ValidationError):
        resolve_workspace("   ")


def test_resolve_workspace_rejects_bare_or_root_path():
    # A bare/root path has no directory name to anchor the workspace in.
    # The drive-root spelling only exists on Windows; on POSIX "/" is the root.
    bad_paths = ["/", "."]
    if os.name == "nt":
        bad_paths.append("C:\\")
    for bad in bad_paths:
        with pytest.raises(ValidationError):
            resolve_workspace(bad)