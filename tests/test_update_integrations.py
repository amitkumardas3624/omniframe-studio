from __future__ import annotations

import json

from typer.testing import CliRunner

import omniframe.cli.main as cli
import omniframe.mcp_server as mcp

runner = CliRunner()


def test_update_check_cli_reports_mocked_release(monkeypatch) -> None:
    monkeypatch.setattr(
        cli,
        "check_for_update",
        lambda **_: {
            "current_version": "0.1.0",
            "latest_version": "0.2.0",
            "update_available": True,
            "release_url": "https://example.test/release",
        },
    )

    result = runner.invoke(cli.app, ["update", "check", "--json"])

    assert result.exit_code == 0
    assert json.loads(result.stdout)["update_available"] is True


def test_cached_advisory_is_added_to_mcp_fields(monkeypatch) -> None:
    monkeypatch.setattr(
        mcp,
        "get_cached_update_advisory",
        lambda: {"latest_version": "0.2.0", "release_url": "https://example.test/release"},
    )

    fields = mcp._update_fields()

    assert fields["update_available"] is True
    assert fields["update_info"]["latest_version"] == "0.2.0"
