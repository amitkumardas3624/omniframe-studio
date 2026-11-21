from __future__ import annotations

from pathlib import Path

from omniframe import __version__
from omniframe.updater import (
    apply_update,
    check_for_update,
    compare_versions,
    get_cached_update_advisory,
    load_cached_update_status,
    restart_instructions,
    stream_update_events,
    upgrade_command,
)


def _newer_than_current() -> str:
    """Return a release version guaranteed to be newer than this build.

    Hard-coding a version here would make the test fail on every release bump,
    so the mocked "latest release" is derived from the running version.
    """

    parts = [int(part) for part in __version__.split(".")]
    parts[-1] += 1
    return ".".join(str(part) for part in parts)


def test_compare_versions_handles_prefix_and_prerelease() -> None:
    assert compare_versions("v0.2.0", "0.1.0") == 1
    assert compare_versions("0.2.0-rc.1", "0.2.0") == -1
    assert compare_versions("0.2.0+build.1", "0.2.0") == 0


def test_check_for_update_uses_mocked_github_and_cache(tmp_path: Path) -> None:
    cache = tmp_path / "update.json"
    latest = _newer_than_current()
    status = check_for_update(
        force=True,
        cache_path=cache,
        now=100.0,
        fetcher=lambda _: {
            "tag_name": f"v{latest}",
            "html_url": "https://example.test/release",
            "body": "release notes",
        },
    )

    assert status["update_available"] is True
    assert status["latest_version"] == latest
    assert status["release_url"] == "https://example.test/release"
    assert load_cached_update_status(cache)["latest_version"] == latest
    assert get_cached_update_advisory(cache)["upgrade_command"] == "omniframe self-update"


def test_check_for_update_returns_offline_status_without_network(tmp_path: Path) -> None:
    status = check_for_update(
        force=True,
        cache_path=tmp_path / "offline.json",
        fetcher=lambda _: (_ for _ in ()).throw(OSError("offline")),
        now=200.0,
    )

    assert status["source"] == "offline"
    assert status["update_available"] is False
    assert "offline" in status["error"]


def test_upgrade_command_uses_argv_without_shell(monkeypatch) -> None:
    monkeypatch.delenv("OMNIFRAME_UPGRADE_COMMAND", raising=False)
    command = upgrade_command()
    assert command[1:4] == ["-m", "pip", "install"]
    assert all("shell=True" not in part for part in command)


def test_apply_update_skips_when_no_update() -> None:
    result = apply_update({"current_version": "0.1.0", "latest_version": "0.1.0", "update_available": False})
    assert result["success"] is True
    assert result["skipped"] is True


def test_stream_update_events_reports_process_output() -> None:
    class FakeProcess:
        stdout = ["Downloading\n", "Installing\n"]

        def wait(self):
            return 0

    events = list(
        stream_update_events(
            {"current_version": "0.1.0", "latest_version": "0.2.0", "update_available": True},
            popen_factory=lambda *args, **kwargs: FakeProcess(),
        )
    )
    assert [event["event"] for event in events] == ["status", "started", "log", "log", "completed"]
    assert events[-1]["success"] is True


def test_restart_instructions_are_explicit() -> None:
    result = restart_instructions()
    assert result["restart_required"] is True
    assert "omniframe" in result["command"]
