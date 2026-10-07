"""Import records (from JSON or CSV files) into canonical items.

Two record shapes are accepted:

- a canonical item, as the app exports it (it has ``id`` and ``provenance``);
- a simple record - ``name``, ``slot``, optional ``armor_type``, ``weapon_type``,
  ``relic_type``, ``quality``, ``required_level``, ``phase``, ``min_damage``,
  ``max_damage``, ``speed``, ``custom``, ``set_name``, one column per stat (named as the
  stat, e.g. ``strength`` or ``spell_hit``), and ``effects``: tooltip lines separated by
  ``|``. It goes through the manual form, so an imported item and a hand-entered one are
  built the same way.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any

from pydantic import ValidationError

from wow_gear.models.enums import Stat
from wow_gear.models.forms import EffectRow, ManualItemForm
from wow_gear.models.item import EffectTrigger, Item
from wow_gear.processing.manual import form_to_item
from wow_gear.processing.tooltip import parse_line

FORM_FIELDS = {
    "name",
    "slot",
    "armor_type",
    "weapon_type",
    "relic_type",
    "quality",
    "required_level",
    "phase",
    "min_damage",
    "max_damage",
    "speed",
    "damage_school",
    "custom",
    "set_name",
}
STAT_NAMES = {stat.value for stat in Stat}


@dataclass(frozen=True)
class ImportedRecord:
    """One record of an import file: the item it became, or why it did not."""

    row: int
    item: Item | None
    errors: tuple[str, ...] = ()


def _blank(value: Any) -> bool:
    return value is None or (isinstance(value, str) and not value.strip())


def _boolean(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() not in ("false", "no", "0", "n")


def record_to_form(record: dict[str, Any], source: str) -> ManualItemForm:
    """A simple import record as a manual form. Unknown columns are an error."""
    unknown = set(record) - FORM_FIELDS - STAT_NAMES - {"effects"}
    if unknown:
        raise ValueError(f"unknown columns: {', '.join(sorted(unknown))}")
    data: dict[str, Any] = {
        key: value for key, value in record.items() if key in FORM_FIELDS and not _blank(value)
    }
    if "custom" in data:
        data["custom"] = _boolean(data["custom"])
    stats: dict[str, float] = {}
    for key, value in record.items():
        if key in STAT_NAMES and not _blank(value):
            stats[key] = float(value)
    rows: list[EffectRow] = []
    for line in str(record.get("effects") or "").split("|"):
        line = line.strip()
        if not line:
            continue
        parsed = parse_line(line)
        unconditional = [s for s in parsed.stats if s.condition is None or s.condition.is_empty]
        if parsed.recognized and len(unconditional) == len(parsed.stats):
            for stat_line in unconditional:
                stats[stat_line.stat.value] = stats.get(stat_line.stat.value, 0.0) + stat_line.value
        elif parsed.recognized and all(
            s.condition and s.condition.target_creature_types for s in parsed.stats
        ):
            for stat_line in parsed.stats:
                assert stat_line.condition is not None
                rows.append(
                    EffectRow(
                        kind="conditional_stat",
                        stat=stat_line.stat,
                        value=stat_line.value,
                        target_creature_types=stat_line.condition.target_creature_types,
                        text=line,
                    )
                )
        else:
            rows.append(
                EffectRow(kind="text", trigger=parsed.trigger or EffectTrigger.EQUIP, text=line)
            )
    data["stats"] = stats
    data["effects"] = tuple(rows)
    data.setdefault("source_note", source)
    return ManualItemForm.model_validate(data)


def import_records(
    records: Iterable[dict[str, Any]], *, ruleset_id: str, source: str
) -> list[ImportedRecord]:
    results = []
    for row, record in enumerate(records, start=1):
        try:
            if "provenance" in record and "id" in record:
                item = Item.model_validate(record)
            else:
                form = record_to_form(record, source)
                item = form_to_item(form, ruleset_id, provider="file_import")
        except ValidationError as error:
            messages = tuple(
                f"{'.'.join(str(part) for part in issue['loc']) or 'record'}: {issue['msg']}"
                for issue in error.errors()
            )
            results.append(ImportedRecord(row=row, item=None, errors=messages))
            continue
        except ValueError as error:
            results.append(ImportedRecord(row=row, item=None, errors=(str(error),)))
            continue
        results.append(ImportedRecord(row=row, item=item))
    return results
