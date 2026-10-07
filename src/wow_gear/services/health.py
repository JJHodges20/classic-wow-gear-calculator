"""Data health: what is configured, what is missing, what each provider can do right now.

This service grows with the milestones: rulesets, profiles, the item cache and the bundled
dataset join the report as they are built.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from wow_gear.core import Settings

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


class HealthService:
    """Reports on the configuration of one project root."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

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
        checks = [
            HealthCheck("configuration", "ok", f"Read configs/ under {settings.root}"),
            HealthCheck(
                "default ruleset",
                "info",
                f"{settings.app.app.default_ruleset} (rulesets are loaded from milestone 2)",
            ),
        ]
        for provider in self.provider_statuses():
            if provider.status == "reference_only":
                checks.append(
                    HealthCheck(f"provider {provider.id}", "info", "Reference only; never fetched")
                )
            elif provider.status == "planned":
                checks.append(
                    HealthCheck(f"provider {provider.id}", "info", "Planned; not implemented yet")
                )
            elif not provider.enabled:
                checks.append(HealthCheck(f"provider {provider.id}", "info", "Disabled"))
            elif provider.credentials == "missing":
                checks.append(
                    HealthCheck(
                        f"provider {provider.id}",
                        "warning",
                        "Credentials not set; see .env.example",
                    )
                )
            else:
                checks.append(HealthCheck(f"provider {provider.id}", "ok", "Ready"))
        return checks
