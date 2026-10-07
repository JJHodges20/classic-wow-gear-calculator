"""The exception hierarchy. Every error the package raises on purpose is a ``WowGearError``."""

from __future__ import annotations


class WowGearError(Exception):
    """Base class for errors raised by the calculator."""


class ConfigError(WowGearError):
    """A configuration file is missing, unreadable or invalid."""


class DataValidationError(WowGearError):
    """Input data (an item, a profile, a ruleset, an import file) failed validation."""


class NotFoundError(WowGearError):
    """Something that was asked for by id does not exist."""


class ProviderError(WowGearError):
    """An item data provider could not answer."""


class ProviderNotConfigured(ProviderError):
    """The provider needs credentials or settings that are not present."""


class ProviderUnavailable(ProviderError):
    """The provider was asked and failed: network error, timeout, bad status or bad payload."""
