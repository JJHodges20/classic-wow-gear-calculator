"""The command line reports the version and the configuration health."""

from __future__ import annotations

from pathlib import Path

import pytest
from typer.testing import CliRunner

from wow_gear import __version__
from wow_gear.cli import app

runner = CliRunner()


def test_version() -> None:
    result = runner.invoke(app, ["--version"])
    assert result.exit_code == 0
    assert __version__ in result.output


def test_check_reports_every_provider(tmp_project: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("WOWGEAR_HOME", str(tmp_project))
    result = runner.invoke(app, ["check"])
    assert result.exit_code == 0, result.output
    for provider in ("bundled", "warcraft_logs", "blizzard", "file_import", "wowhead"):
        assert f"provider {provider}" in result.output
    assert "Reference only; never fetched" in result.output


def test_check_fails_clearly_on_a_broken_configuration(
    tmp_project: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (tmp_project / "configs" / "app.yaml").write_text("app: {name: x}\n", encoding="utf-8")
    monkeypatch.setenv("WOWGEAR_HOME", str(tmp_project))
    result = runner.invoke(app, ["check"])
    assert result.exit_code == 2
    assert "default_ruleset" in result.output


def test_ui_starts_streamlit_without_usage_statistics(
    tmp_project: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls: list[list[str]] = []
    monkeypatch.setenv("WOWGEAR_HOME", str(tmp_project))
    monkeypatch.setattr(
        "wow_gear.cli.subprocess.call", lambda command, cwd: calls.append(command) or 0
    )
    result = runner.invoke(app, ["ui", "--no-browser", "--port", "8650"])
    assert result.exit_code == 0, result.output
    command = calls[0]
    assert command[command.index("--server.port") + 1] == "8650"
    assert command[command.index("--server.headless") + 1] == "true"
    assert command[command.index("--browser.gatherUsageStats") + 1] == "false"
