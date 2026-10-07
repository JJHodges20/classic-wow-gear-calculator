"""Stable content hashes, so that every stored score can name exactly what produced it."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from datetime import date, datetime
from enum import Enum
from typing import Any


def _default(value: Any) -> Any:
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, datetime | date):
        return value.isoformat()
    if isinstance(value, set | frozenset):
        return sorted(value, key=str)
    raise TypeError(f"cannot hash a {type(value).__name__}")


def canonical_json(data: Any) -> str:
    """JSON with sorted keys and no whitespace: equal data always gives equal text."""
    return json.dumps(data, sort_keys=True, separators=(",", ":"), default=_default)


def content_hash(data: Mapping[str, Any] | list[Any] | Any, length: int = 16) -> str:
    """A short sha256 of the canonical JSON of ``data``."""
    digest = hashlib.sha256(canonical_json(data).encode("utf-8")).hexdigest()
    return digest[:length]
