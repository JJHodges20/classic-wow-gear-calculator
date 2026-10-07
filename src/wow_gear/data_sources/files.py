"""Reading item files a player imports: JSON or CSV (roadmap provider priority 4)."""

from __future__ import annotations

import csv
import io
import json
from pathlib import Path
from typing import Any

from wow_gear.core.errors import DataValidationError

MAX_IMPORT_BYTES = 5_000_000


def read_item_file(path: Path) -> list[dict[str, Any]]:
    """The records in an import file, as dictionaries, untouched.

    JSON: a list of records or ``{"items": [...]}``. CSV: one record per row, with a header.
    """
    if not path.is_file():
        raise DataValidationError(f"no file at {path}")
    if path.stat().st_size > MAX_IMPORT_BYTES:
        raise DataValidationError(f"{path.name} is larger than {MAX_IMPORT_BYTES // 1_000_000} MB")
    text = path.read_text(encoding="utf-8-sig")
    return read_item_text(text, path.suffix.lower())


def read_item_text(text: str, suffix: str) -> list[dict[str, Any]]:
    if suffix == ".json":
        try:
            data = json.loads(text)
        except ValueError as error:
            raise DataValidationError(f"the file is not valid JSON: {error}") from error
        if isinstance(data, dict):
            data = data.get("items")
        if not isinstance(data, list) or not all(isinstance(entry, dict) for entry in data):
            raise DataValidationError('a JSON import is a list of items, or {"items": [...]}')
        return data
    if suffix == ".csv":
        return _csv_rows(text)
    raise DataValidationError("import files are .json or .csv")


def _csv_rows(text: str) -> list[dict[str, Any]]:
    reader = csv.DictReader(io.StringIO(text))
    if not reader.fieldnames:
        raise DataValidationError("the CSV file has no header row")
    return [
        {key.strip().lower(): (value or "").strip() for key, value in row.items() if key}
        for row in reader
        if any((value or "").strip() for value in row.values())
    ]


def read_gear_text(text: str, suffix: str) -> dict[str, Any] | list[dict[str, Any]]:
    """A gear import, untouched: a saved character as a JSON object, or a CSV gear list."""
    if len(text.encode("utf-8")) > MAX_IMPORT_BYTES:
        raise DataValidationError(f"the file is larger than {MAX_IMPORT_BYTES // 1_000_000} MB")
    text = text.removeprefix("\ufeff")
    if suffix == ".json":
        try:
            data = json.loads(text)
        except ValueError as error:
            raise DataValidationError(f"the file is not valid JSON: {error}") from error
        if not isinstance(data, dict):
            raise DataValidationError("a JSON gear import is one saved character (an object)")
        return data
    if suffix == ".csv":
        return _csv_rows(text)
    raise DataValidationError("gear files are .json or .csv")
