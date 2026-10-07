"""Gear from an import file: a saved character exported as JSON, or a gear list as CSV.

A CSV gear list has a header row with a ``slot`` column and an ``item_id`` column (``id`` or
``item`` work too); other columns, such as the ``item_name`` an export writes, are ignored.
A slot is written as the export writes it (``finger_1``) or as the app shows it
("Finger 1"); an item id is the app's (``classic_era:12640``) or the game's number alone.
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from typing import Any

from pydantic import ValidationError

from wow_gear.core.errors import DataValidationError
from wow_gear.models.enums import EquipmentSlot
from wow_gear.models.gear import GearSet, SavedCharacter
from wow_gear.models.item import ITEM_ID_PATTERN
from wow_gear.models.labels import EQUIPMENT_SLOT_LABELS

ID_COLUMNS = ("item_id", "id", "item")
_SLOT_NAMES = {
    **{slot.value: slot for slot in EquipmentSlot},
    **{label.lower(): slot for slot, label in EQUIPMENT_SLOT_LABELS.items()},
}


def _reasons(error: ValidationError) -> str:
    return "; ".join(
        f"{'.'.join(str(part) for part in issue['loc'])}: {issue['msg']}"
        if issue["loc"]
        else issue["msg"]
        for issue in error.errors()
    )


def character_from_record(record: dict[str, Any]) -> SavedCharacter:
    """A saved character from its exported JSON object."""
    try:
        return SavedCharacter.model_validate(record)
    except ValidationError as error:
        raise DataValidationError(f"this is not a saved character: {_reasons(error)}") from error


def slot_from_text(text: str) -> EquipmentSlot:
    slot = _SLOT_NAMES.get(" ".join(text.replace("-", " ").split()).lower())
    if slot is None:
        slot = _SLOT_NAMES.get(text.strip().lower())
    if slot is None:
        raise DataValidationError(f"{text!r} is not an equipment slot")
    return slot


def item_reference(text: str, ruleset_id: str) -> str:
    """An item id as the app writes it: "12640" -> "classic_era:12640"."""
    text = text.strip()
    if text.isdigit():
        return f"{ruleset_id}:{int(text)}"
    if not re.match(ITEM_ID_PATTERN, text):
        raise DataValidationError(f"{text!r} is not an item id")
    return text


def gear_from_rows(rows: Sequence[dict[str, Any]], ruleset_id: str, name: str) -> GearSet:
    """A gear set from the rows of a CSV gear list (row 2 is the first after the header)."""
    if not rows:
        raise DataValidationError("the gear list has no rows")
    column = next((key for key in ID_COLUMNS if key in rows[0]), None)
    if "slot" not in rows[0] or column is None:
        raise DataValidationError("a gear list needs a slot column and an item_id column")
    items: dict[EquipmentSlot, str] = {}
    problems = []
    for number, row in enumerate(rows, start=2):
        slot_text, item_text = str(row.get("slot") or ""), str(row.get(column) or "")
        if not item_text:
            continue  # an empty slot
        try:
            slot = slot_from_text(slot_text)
            if slot in items:
                raise DataValidationError(f"the {EQUIPMENT_SLOT_LABELS[slot]} slot is listed twice")
            items[slot] = item_reference(item_text, ruleset_id)
        except DataValidationError as error:
            problems.append(f"row {number}: {error}")
    if problems:
        raise DataValidationError("; ".join(problems))
    return GearSet(name=name, items=items)
