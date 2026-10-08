"""Logging setup for the ``wow_gear`` logger tree.

Secrets never reach a log line: the handler masks every value configured as a secret in
what it writes, the message and any traceback alike.
"""

from __future__ import annotations

import logging
import sys
from collections.abc import Iterable
from typing import TextIO

LOGGER_NAME = "wow_gear"
_FORMAT = "%(asctime)s %(levelname)-7s %(name)s: %(message)s"
_MASK = "****"


def _maskable(secrets: Iterable[str]) -> tuple[str, ...]:
    return tuple(value for value in secrets if value and len(value) >= 4)


def mask(text: str, secrets: Iterable[str]) -> str:
    """``text`` with every secret value replaced by a mask."""
    for secret in _maskable(secrets):
        text = text.replace(secret, _MASK)
    return text


class SecretMaskingFilter(logging.Filter):
    """Replaces known secret values in a record's message with a mask."""

    def __init__(self, secrets: Iterable[str] = ()) -> None:
        super().__init__()
        self._secrets = _maskable(secrets)

    def filter(self, record: logging.LogRecord) -> bool:
        if self._secrets:
            record.msg, record.args = mask(record.getMessage(), self._secrets), None
        return True


class MaskingFormatter(logging.Formatter):
    """Masks secrets in the whole formatted record: a traceback can carry them too."""

    def __init__(self, fmt: str, secrets: Iterable[str] = ()) -> None:
        super().__init__(fmt)
        self.secrets = _maskable(secrets)

    def format(self, record: logging.LogRecord) -> str:
        return mask(super().format(record), self.secrets)


class _StderrHandler(logging.StreamHandler):  # type: ignore[type-arg]
    """Writes to whatever ``sys.stderr`` is when a record is emitted, not when the handler
    was made: a test runner swaps the stream for each command it runs."""

    @property
    def stream(self) -> TextIO:
        return sys.stderr

    @stream.setter
    def stream(self, value: TextIO) -> None:
        pass


def configure_logging(level: str = "INFO", secrets: Iterable[str] = ()) -> logging.Logger:
    """Configure the package logger once; later calls only change the level and secrets."""
    logger = logging.getLogger(LOGGER_NAME)
    logger.setLevel(level.upper())
    handler = next((h for h in logger.handlers if getattr(h, "_wow_gear", False)), None)
    secrets = tuple(secrets)
    if handler is None:
        handler = _StderrHandler()
        handler._wow_gear = True  # type: ignore[attr-defined]
        logger.addHandler(handler)
        logger.propagate = False
    handler.setFormatter(MaskingFormatter(_FORMAT, secrets))
    for existing in list(handler.filters):
        if isinstance(existing, SecretMaskingFilter):
            handler.removeFilter(existing)
    handler.addFilter(SecretMaskingFilter(secrets))
    return logger


def get_logger(name: str) -> logging.Logger:
    """A logger under the package tree, e.g. ``get_logger(__name__)``."""
    if name == LOGGER_NAME or name.startswith(LOGGER_NAME + "."):
        return logging.getLogger(name)
    return logging.getLogger(f"{LOGGER_NAME}.{name}")
