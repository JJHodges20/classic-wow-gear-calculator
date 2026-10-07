"""Data health: what is configured, what is loaded, what each provider can do right now."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

from wow_gear.core import ConfigError, Settings
from wow_gear.profiles.loader import ProfileRegistry
from wow_gear.repositories.items import ItemRepository, ProviderCall
from wow_gear.rulesets.loader import RulesetRegistry

CheckStatus = Literal["ok", "warning", "error", "info"]
CredentialState = Literal["not_needed", "present", "missing"]


@dataclass(frozen=True)
class HealthCheck:
    """One line of the health report."""

    name: str
    status: CheckStatus
    detail: str


@dataclass(frozen=True)
class ProviderStatus:
    """A configured provider and whether it can be used now."""

    id: str
    kind: str
    priority: int
    status: str
    enabled: bool
    credentials: CredentialState
    description: str

    @property
    def usable(self) -> bool:
        return self.enabled and self.status == "active" and self.credentials != "missing"


@dataclass(frozen=True)
class BundledStatus:
    """The bundled dataset as loaded into the local database."""

    version: str | None
    loaded: int
    metadata: dict[str, Any] = field(default_factory=dict)
    problem: str | None = None


class HealthService:
    """Reports on the configuration and, when given them, the data the workspace holds."""

    def __init__(
        self,
        settings: Settings,
        *,
        repository: ItemRepository | None = None,
        bundled: BundledStatus | None = None,
        online_detail: str | None = None,
    ) -> None:
        self._settings = settings
        self._repository = repository
        self._bundled = bundled
        self._online_detail = online_detail

    @property
    def bundled(self) -> BundledStatus | None:
        return self._bundled

    def item_counts(self) -> dict[str, int]:
        return self._repository.counts() if self._repository else {}

    def recent_calls(self, limit: int = 10) -> list[ProviderCall]:
        return self._repository.recent_calls(limit=limit) if self._repository else []

    def provider_statuses(self) -> list[ProviderStatus]:
        statuses = []
        for provider in self._settings.providers.by_priority():
            if not provider.secrets:
                credentials: CredentialState = "not_needed"
            elif self._settings.has_credentials(provider):
                credentials = "present"
            else:
                credentials = "missing"
            statuses.append(
                ProviderStatus(
                    id=provider.id,
                    kind=provider.kind,
                    priority=provider.priority,
                    status=provider.status,
                    enabled=provider.enabled,
                    credentials=credentials,
                    description=provider.description,
                )
            )
        return statuses

    def checks(self) -> list[HealthCheck]:
        settings = self._settings
        checks = [HealthCheck("configuration", "ok", f"Read configs/ under {settings.root}")]
        checks.extend(self._ruleset_and_profile_checks())
        checks.extend(self._data_checks())
        for provider in self.provider_statuses():
            name = f"provider {provider.id}"
            if provider.status == "reference_only":
                checks.append(HealthCheck(name, "info", "Reference only; never fetched"))
            elif provider.status == "planned":
                checks.append(HealthCheck(name, "info", "Planned; not implemented yet"))
            elif not provider.enabled:
                checks.append(HealthCheck(name, "info", "Disabled"))
            elif provider.credentials == "missing":
                checks.append(HealthCheck(name, "warning", "Credentials not set; see .env.example"))
            else:
                detail = "Ready"
                if provider.id == "blizzard" and self._online_detail:
                    detail = self._online_detail
                checks.append(HealthCheck(name, "ok", detail))
        return checks

    def _data_checks(self) -> list[HealthCheck]:
        checks: list[HealthCheck] = []
        if self._bundled is not None:
            if self._bundled.version is None:
                checks.append(
                    HealthCheck("bundled dataset", "warning", self._bundled.problem or "Not loaded")
                )
            else:
                detail = f"{self._bundled.loaded} items, version {self._bundled.version}"
                status: CheckStatus = "warning" if self._bundled.problem else "ok"
                if self._bundled.problem:
                    detail += f" ({self._bundled.problem})"
                checks.append(HealthCheck("bundled dataset", status, detail))
        if self._repository is not None:
            counts = self._repository.counts()
            checks.append(
                HealthCheck(
                    "local items",
                    "info",
                    f"{counts.get('bundled', 0)} bundled, {counts.get('cache', 0)} looked up, "
                    f"{counts.get('user', 0)} your own",
                )
            )
        return checks

    def _ruleset_and_profile_checks(self) -> list[HealthCheck]:
        settings = self._settings
        try:
            rulesets = RulesetRegistry.from_directory(settings.config_dir / "rulesets")
        except ConfigError as error:
            return [HealthCheck("rulesets", "error", str(error))]
        checks = [
            HealthCheck(
                f"ruleset {ruleset.id}",
                "ok",
                f"{ruleset.label} {ruleset.version} ({ruleset.validation_status}), "
                f"{len(ruleset.sources)} sources",
            )
            for ruleset in rulesets
        ]
        default = settings.app.app.default_ruleset
        if default not in rulesets.ids():
            checks.append(HealthCheck("default ruleset", "error", f"{default} is not configured"))
        try:
            profiles = ProfileRegistry.from_directory(settings.config_dir / "profiles", rulesets)
        except ConfigError as error:
            return [*checks, HealthCheck("profiles", "error", str(error))]
        statuses = sorted({profile.validation_status.value for profile in profiles})
        checks.append(
            HealthCheck(
                "profiles",
                "ok" if len(profiles) else "warning",
                f"{len(profiles)} build profiles ({', '.join(statuses) or 'none'})",
            )
        )
        return checks
