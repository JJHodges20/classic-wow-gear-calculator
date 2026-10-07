"""Settings: ``configs/app.yaml`` and ``configs/providers.yaml``, with environment overrides.

Secrets are never read from YAML. A provider names the environment variables that hold its
credentials; they come from the process environment or, failing that, from a ``.env`` file
at the project root. The process environment wins.
"""

from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

import yaml
from dotenv import dotenv_values
from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from wow_gear.core.errors import ConfigError

ENV_PREFIX = "WOWGEAR_"
HOME_VARIABLE = "WOWGEAR_HOME"
DATA_DIR_VARIABLE = "WOWGEAR_DATA_DIR"
LOG_LEVEL_VARIABLE = "WOWGEAR_LOG_LEVEL"
APP_CONFIG = Path("configs") / "app.yaml"
PROVIDERS_CONFIG = Path("configs") / "providers.yaml"

LogLevel = Literal["DEBUG", "INFO", "WARNING", "ERROR"]
ProviderKind = Literal[
    "bundled_dataset", "warcraft_logs", "blizzard_game_data", "file_import", "reference_only"
]
ProviderStatus = Literal["active", "planned", "reference_only"]


class _Strict(BaseModel):
    """A configuration block: unknown keys are errors, so a typing slip is caught."""

    model_config = ConfigDict(extra="forbid", frozen=True)


class AppSection(_Strict):
    name: str = Field(min_length=1)
    default_ruleset: str = Field(min_length=1)


class PathsSection(_Strict):
    data_dir: Path = Path("data")
    cache_dir: Path = Path("data/cache")
    user_dir: Path = Path("data/user")
    bundled_dir: Path = Path("data/bundled")


class LoggingSection(_Strict):
    level: LogLevel = "INFO"


class CacheSection(_Strict):
    item_ttl_days: int = Field(default=30, ge=1)


class AppConfig(_Strict):
    """The contents of ``configs/app.yaml``."""

    app: AppSection
    paths: PathsSection = PathsSection()
    logging: LoggingSection = LoggingSection()
    cache: CacheSection = CacheSection()


class ProviderConfig(_Strict):
    """One item data provider as configured."""

    id: str = Field(pattern=r"^[a-z][a-z0-9_]*$")
    kind: ProviderKind
    priority: int = Field(ge=1)
    enabled: bool
    status: ProviderStatus
    description: str = Field(min_length=1)
    secrets: tuple[str, ...] = ()
    settings: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _secrets_are_variable_names(self) -> ProviderConfig:
        for name in self.secrets:
            if not name.startswith(ENV_PREFIX) or not name.replace("_", "").isalnum():
                raise ValueError(
                    f"provider {self.id!r}: secret {name!r} must be an environment variable "
                    f"name starting with {ENV_PREFIX}"
                )
        if self.kind == "reference_only" and (self.enabled or self.status != "reference_only"):
            raise ValueError(f"provider {self.id!r} is a reference only and cannot be enabled")
        return self


class ProvidersConfig(_Strict):
    """The contents of ``configs/providers.yaml``."""

    providers: tuple[ProviderConfig, ...]

    @model_validator(mode="after")
    def _unique(self) -> ProvidersConfig:
        ids = [provider.id for provider in self.providers]
        if len(ids) != len(set(ids)):
            raise ValueError(f"provider ids must be unique: {ids}")
        priorities = [provider.priority for provider in self.providers]
        if len(priorities) != len(set(priorities)):
            raise ValueError(f"provider priorities must be unique: {priorities}")
        return self

    def by_priority(self) -> tuple[ProviderConfig, ...]:
        return tuple(sorted(self.providers, key=lambda provider: provider.priority))

    def get(self, provider_id: str) -> ProviderConfig:
        for provider in self.providers:
            if provider.id == provider_id:
                return provider
        raise ConfigError(f"no provider {provider_id!r} in {PROVIDERS_CONFIG.as_posix()}")


@dataclass(frozen=True)
class Settings:
    """Everything configured for one project root."""

    root: Path
    app: AppConfig
    providers: ProvidersConfig
    environment: Mapping[str, str] = field(default_factory=dict)
    """The ``WOWGEAR_`` variables in effect: ``.env`` overlaid by the process environment."""

    @property
    def config_dir(self) -> Path:
        return self.root / "configs"

    @property
    def data_dir(self) -> Path:
        override = self.environment.get(DATA_DIR_VARIABLE)
        return self._resolve(Path(override) if override else self.app.paths.data_dir)

    @property
    def cache_dir(self) -> Path:
        if self.environment.get(DATA_DIR_VARIABLE):
            return self.data_dir / "cache"
        return self._resolve(self.app.paths.cache_dir)

    @property
    def user_dir(self) -> Path:
        if self.environment.get(DATA_DIR_VARIABLE):
            return self.data_dir / "user"
        return self._resolve(self.app.paths.user_dir)

    @property
    def bundled_dir(self) -> Path:
        """The bundled dataset ships with the code, so it never moves with the data directory."""
        return self._resolve(self.app.paths.bundled_dir)

    @property
    def database_path(self) -> Path:
        return self.user_dir / "wowgear.sqlite3"

    @property
    def log_level(self) -> LogLevel:
        override = self.environment.get(LOG_LEVEL_VARIABLE, "").upper()
        if override in ("DEBUG", "INFO", "WARNING", "ERROR"):
            return override  # type: ignore[return-value]
        return self.app.logging.level

    def secret(self, name: str) -> str | None:
        """The value of a secret variable, or None when it is unset or blank."""
        value = self.environment.get(name, "").strip()
        return value or None

    def has_credentials(self, provider: ProviderConfig) -> bool:
        """Whether every secret the provider needs is set."""
        return all(self.secret(name) for name in provider.secrets)

    def _resolve(self, path: Path) -> Path:
        return path if path.is_absolute() else (self.root / path).resolve()


def find_project_root(start: Path | None = None) -> Path:
    """The project root: ``WOWGEAR_HOME`` if set, else the nearest folder with configs/app.yaml."""
    home = os.environ.get(HOME_VARIABLE)
    if home:
        root = Path(home).expanduser().resolve()
        if not (root / APP_CONFIG).is_file():
            raise ConfigError(f"{HOME_VARIABLE}={home} has no {APP_CONFIG.as_posix()}")
        return root
    here = (start or Path.cwd()).resolve()
    for candidate in (here, *here.parents):
        if (candidate / APP_CONFIG).is_file():
            return candidate
    package_root = Path(__file__).resolve().parents[3]
    if (package_root / APP_CONFIG).is_file():
        return package_root
    raise ConfigError(f"no {APP_CONFIG.as_posix()} found above {here}; set {HOME_VARIABLE}")


def load_settings(
    root: Path | None = None, environment: Mapping[str, str] | None = None
) -> Settings:
    """Read the configuration of a project root.

    ``environment`` replaces the process environment (tests pass their own); the ``.env``
    file at the root is read either way and loses to it.
    """
    root = (root or find_project_root()).resolve()
    app = _parse(root / APP_CONFIG, AppConfig)
    providers = _parse(root / PROVIDERS_CONFIG, ProvidersConfig)
    return Settings(
        root=root,
        app=app,
        providers=providers,
        environment=_environment(root, os.environ if environment is None else environment),
    )


def _environment(root: Path, process: Mapping[str, str]) -> dict[str, str]:
    merged: dict[str, str] = {}
    dotenv = root / ".env"
    if dotenv.is_file():
        merged.update(
            {key: value for key, value in dotenv_values(dotenv).items() if value is not None}
        )
    merged.update(process)
    return {key: value for key, value in merged.items() if key.startswith(ENV_PREFIX)}


def _parse[ModelT: BaseModel](path: Path, model: type[ModelT]) -> ModelT:
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    except FileNotFoundError as error:
        raise ConfigError(f"missing configuration file {path}") from error
    except yaml.YAMLError as error:
        raise ConfigError(f"{path} is not valid YAML: {error}") from error
    try:
        return model.model_validate(raw or {})
    except ValidationError as error:
        raise ConfigError(f"{path} is invalid:\n{error}") from error
