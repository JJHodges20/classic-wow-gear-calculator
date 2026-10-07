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
