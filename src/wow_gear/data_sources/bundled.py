"""Reading the bundled curated item dataset (``data/bundled``)."""

from __future__ import annotations

import gzip
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from wow_gear.core.errors import ProviderUnavailable

DATASET_FILE = "classic_era_items.json.gz"
METADATA_FILE = "classic_era_items.meta.json"


@dataclass(frozen=True)
class BundledDataset:
    """The dataset as stored: provider-shaped item dictionaries plus its metadata."""

    version: str
    ruleset: str
    items: list[dict[str, Any]]
    metadata: dict[str, Any] = field(default_factory=dict)


def bundled_paths(directory: Path) -> tuple[Path, Path]:
    return directory / DATASET_FILE, directory / METADATA_FILE


def read_metadata(directory: Path) -> dict[str, Any] | None:
    """The dataset's metadata, or None when there is no bundled dataset."""
    _, meta = bundled_paths(directory)
    if not meta.is_file():
        return None
    data = json.loads(meta.read_text(encoding="utf-8"))
    return data if isinstance(data, dict) else None


def read_bundled(directory: Path) -> BundledDataset:
    data_file, _ = bundled_paths(directory)
    if not data_file.is_file():
        raise ProviderUnavailable(f"no bundled dataset at {data_file}")
    try:
        with gzip.open(data_file, "rt", encoding="utf-8") as handle:
            payload = json.load(handle)
    except (OSError, ValueError) as error:
        raise ProviderUnavailable(f"the bundled dataset could not be read: {error}") from error
    items = payload.get("items")
    if not isinstance(items, list):
        raise ProviderUnavailable("the bundled dataset has no item list")
    return BundledDataset(
        version=str(payload.get("version", "unknown")),
        ruleset=str(payload.get("ruleset", "classic_era")),
        items=items,
        metadata=read_metadata(directory) or {},
    )
