"""Logging setup for the ``wow_gear`` logger tree.

Secrets never reach a log line: a filter masks any value configured as a secret.
"""

from __future__ import annotations

import logging
import sys
from collections.abc import Iterable
from typing import TextIO

LOGGER_NAME = "wow_gear"
_FORMAT = "%(asctime)s %(levelname)-7s %(name)s: %(message)s"
_MASK = "****"


class SecretMaskingFilter(logging.Filter):
    """Replaces known secret values in a record's message with a mask."""

    def __init__(self, secrets: Iterable[str] = ()) -> None:
        super().__init__()
        self._secrets = tuple(value for value in secrets if value and len(value) >= 4)

    def filter(self, record: logging.LogRecord) -> bool:
        if self._secrets:
            message = record.getMessage()
            for secret in self._secrets:
                message = message.replace(secret, _MASK)
            record.msg, record.args = message, None
        return True


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
    if handler is None:
        handler = _StderrHandler()
        handler._wow_gear = True  # type: ignore[attr-defined]
        handler.setFormatter(logging.Formatter(_FORMAT))
        logger.addHandler(handler)
        logger.propagate = False
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
