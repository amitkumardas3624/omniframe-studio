from __future__ import annotations

from typer.testing import CliRunner

from omniframe.cli.main import app

runner = CliRunner()


def test_project_render_help_mentions_streaming():
    result = runner.invoke(app, ["project", "render", "--help"])
    assert result.exit_code == 0
    assert "stream" in result.stdout.lower()
    assert "resume" in result.stdout.lower()


def test_doctor_json_contains_native_capability():
    result = runner.invoke(app, ["doctor", "--json"])
    assert result.exit_code == 0
    assert "native_accelerator" in result.stdout
