"""Settings come from configs/*.yaml; secrets only from the environment or .env."""

from __future__ import annotations

from pathlib import Path

import pytest

from wow_gear.core import ConfigError, find_project_root, load_settings
from wow_gear.core.logging import configure_logging


def test_the_shipped_configuration_loads(project_root: Path) -> None:
    settings = load_settings(project_root, environment={})
    assert settings.app.app.default_ruleset == "classic_era"
    assert settings.data_dir == (project_root / "data").resolve()
    assert settings.cache_dir == (project_root / "data" / "cache").resolve()
    ids = [provider.id for provider in settings.providers.by_priority()]
    assert ids[0] == "bundled" and "wowhead" in ids


def test_providers_follow_the_roadmap_priority(project_root: Path) -> None:
    providers = load_settings(project_root, environment={}).providers
    order = [provider.id for provider in providers.by_priority()]
    assert order == ["bundled", "warcraft_logs", "blizzard", "file_import", "wowhead"]


def test_the_project_root_is_found_from_a_subfolder(project_root: Path) -> None:
    assert find_project_root(project_root / "src" / "wow_gear") == project_root


def test_an_environment_override_moves_the_data_directory(tmp_project: Path) -> None:
    elsewhere = tmp_project / "elsewhere"
    settings = load_settings(tmp_project, environment={"WOWGEAR_DATA_DIR": str(elsewhere)})
    assert settings.data_dir == elsewhere
    assert settings.cache_dir == elsewhere / "cache"
    assert settings.user_dir == elsewhere / "user"


def test_the_log_level_can_be_overridden(tmp_project: Path) -> None:
    assert load_settings(tmp_project, environment={}).log_level == "INFO"
    settings = load_settings(tmp_project, environment={"WOWGEAR_LOG_LEVEL": "debug"})
    assert settings.log_level == "DEBUG"


class TestSecrets:
    def test_secrets_come_from_dotenv(self, tmp_project: Path) -> None:
        (tmp_project / ".env").write_text(
            "WOWGEAR_BLIZZARD_CLIENT_ID=abc\nWOWGEAR_BLIZZARD_CLIENT_SECRET=def\n",
            encoding="utf-8",
        )
        settings = load_settings(tmp_project, environment={})
        blizzard = settings.providers.get("blizzard")
        assert settings.secret("WOWGEAR_BLIZZARD_CLIENT_ID") == "abc"
        assert settings.has_credentials(blizzard)

    def test_the_process_environment_beats_dotenv(self, tmp_project: Path) -> None:
        (tmp_project / ".env").write_text("WOWGEAR_WCL_CLIENT_ID=from-file\n", encoding="utf-8")
        settings = load_settings(tmp_project, environment={"WOWGEAR_WCL_CLIENT_ID": "from-env"})
        assert settings.secret("WOWGEAR_WCL_CLIENT_ID") == "from-env"

    def test_blank_or_missing_secrets_mean_not_configured(self, tmp_project: Path) -> None:
        settings = load_settings(
            tmp_project,
            environment={"WOWGEAR_BLIZZARD_CLIENT_ID": "  ", "WOWGEAR_BLIZZARD_CLIENT_SECRET": ""},
        )
        assert settings.secret("WOWGEAR_BLIZZARD_CLIENT_ID") is None
        assert not settings.has_credentials(settings.providers.get("blizzard"))

    def test_only_prefixed_variables_are_kept(self, tmp_project: Path) -> None:
        settings = load_settings(tmp_project, environment={"PATH": "x", "WOWGEAR_HOME": "y"})
        assert "PATH" not in settings.environment


class TestInvalidConfiguration:
    def test_an_unknown_key_is_rejected(self, tmp_project: Path) -> None:
        path = tmp_project / "configs" / "app.yaml"
        path.write_text(path.read_text(encoding="utf-8") + "\ntypo_section: 1\n", encoding="utf-8")
        with pytest.raises(ConfigError, match="typo_section"):
            load_settings(tmp_project, environment={})

    def test_duplicate_provider_priorities_are_rejected(self, tmp_project: Path) -> None:
        path = tmp_project / "configs" / "providers.yaml"
        text = path.read_text(encoding="utf-8").replace("priority: 2", "priority: 1")
        path.write_text(text, encoding="utf-8")
        with pytest.raises(ConfigError, match="priorities must be unique"):
            load_settings(tmp_project, environment={})

    def test_a_secret_must_be_a_variable_name_not_a_value(self, tmp_project: Path) -> None:
        path = tmp_project / "configs" / "providers.yaml"
        text = path.read_text(encoding="utf-8").replace("WOWGEAR_WCL_CLIENT_ID,", "sk-live-1234,")
        path.write_text(text, encoding="utf-8")
        with pytest.raises(ConfigError, match="environment variable"):
            load_settings(tmp_project, environment={})

    def test_a_reference_provider_cannot_be_enabled(self, tmp_project: Path) -> None:
        path = tmp_project / "configs" / "providers.yaml"
        text = path.read_text(encoding="utf-8")
        head, _, tail = text.rpartition("enabled: false")
        path.write_text(head + "enabled: true" + tail, encoding="utf-8")
        with pytest.raises(ConfigError, match="reference only"):
            load_settings(tmp_project, environment={})

    def test_a_missing_file_says_which(self, tmp_project: Path) -> None:
        (tmp_project / "configs" / "providers.yaml").unlink()
        with pytest.raises(ConfigError, match=r"providers\.yaml"):
            load_settings(tmp_project, environment={})

    def test_broken_yaml_says_so(self, tmp_project: Path) -> None:
        (tmp_project / "configs" / "app.yaml").write_text("app: [unclosed", encoding="utf-8")
        with pytest.raises(ConfigError, match="not valid YAML"):
            load_settings(tmp_project, environment={})


class TestSecretsStayOutOfLogs:
    HIDDEN = "hidden-value-for-tests"

    def test_settings_never_print_a_secret_value(self, tmp_project: Path) -> None:
        settings = load_settings(
            tmp_project, environment={"WOWGEAR_BLIZZARD_CLIENT_SECRET": self.HIDDEN}
        )
        assert self.HIDDEN not in repr(settings)
        assert settings.secret_values() == (self.HIDDEN,)

    def test_log_lines_and_tracebacks_are_masked(self, capsys: pytest.CaptureFixture[str]) -> None:
        logger = configure_logging("INFO", secrets=[self.HIDDEN])
        try:
            logger.warning("token request with %s failed", self.HIDDEN)
            try:
                raise RuntimeError(f"rejected {self.HIDDEN}")
            except RuntimeError:
                logger.exception("lookup failed")
        finally:
            configure_logging("INFO")
        written = capsys.readouterr().err
        assert self.HIDDEN not in written
        assert written.count("****") == 2
        assert "RuntimeError: rejected ****" in written
