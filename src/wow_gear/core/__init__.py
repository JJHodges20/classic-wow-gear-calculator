"""Core: settings, logging, errors and other plumbing every layer may use.

Owns: reading ``configs/app.yaml`` and ``configs/providers.yaml``, environment overrides,
secrets lookup, logging setup, the exception hierarchy.

May import: nothing else in ``wow_gear``. Holds no game knowledge.
"""

from wow_gear.core.config import (
    AppConfig,
    ProviderConfig,
    ProvidersConfig,
    Settings,
    find_project_root,
    load_settings,
)
from wow_gear.core.errors import (
    ConfigError,
    DataValidationError,
    NotFoundError,
    ProviderError,
    ProviderNotConfigured,
    ProviderUnavailable,
    WowGearError,
)
from wow_gear.core.logging import configure_logging, get_logger

__all__ = [
    "AppConfig",
    "ConfigError",
    "DataValidationError",
    "NotFoundError",
    "ProviderConfig",
    "ProviderError",
    "ProviderNotConfigured",
    "ProviderUnavailable",
    "ProvidersConfig",
    "Settings",
    "WowGearError",
    "configure_logging",
    "find_project_root",
    "get_logger",
    "load_settings",
]
