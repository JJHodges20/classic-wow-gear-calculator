"""Manual item entry (roadmap section 7, path A).

The player picks a slot and an item type first, so the form shows only the fields that
apply; enters numbers; optionally adds effect rows; and sees the normalized item and its
validation before anything is scored. A pasted tooltip can fill the form.
"""

from __future__ import annotations

from dataclasses import dataclass

from pydantic import ValidationError

from wow_gear.models.enums import (
    RANGED_WEAPON_TYPES,
    TWO_HANDED_WEAPON_TYPES,
    WEAPON_DPS_STATS,
    ArmorType,
    ItemSlot,
    RelicType,
    Stat,
    WeaponType,
)
from wow_gear.models.forms import ManualItemForm
from wow_gear.models.item import ARMOR_SLOTS, WEAPON_SLOTS, Item
from wow_gear.models.ruleset import Ruleset
from wow_gear.processing.manual import TooltipReading, form_to_item, read_tooltip
from wow_gear.processing.validation import ValidationIssue, validate_item

GROUP_LABELS = {
    "primary": "Primary stats",
    "defense": "Armor and defense",
    "physical": "Physical offense",
    "caster": "Spells",
    "regen": "Regeneration",
    "resistance": "Resistances",
    "weapon": "Weapon skill",
}
GROUP_ORDER: dict[ItemSlot, tuple[str, ...]] = {
    ItemSlot.SHIELD: ("defense", "primary", "physical", "caster", "regen", "resistance", "weapon"),
    ItemSlot.HELD_IN_OFF_HAND: (
        "caster",
        "primary",
        "regen",
        "defense",
        "physical",
        "resistance",
        "weapon",
    ),
    ItemSlot.RELIC: ("caster", "primary", "regen", "physical", "defense", "resistance", "weapon"),
}
DEFAULT_GROUP_ORDER = ("primary", "defense", "physical", "caster", "regen", "resistance", "weapon")
ONE_HANDED_WEAPONS = (
    WeaponType.DAGGER,
    WeaponType.SWORD,
    WeaponType.AXE,
    WeaponType.MACE,
    WeaponType.FIST,
)


@dataclass(frozen=True)
class StatField:
    stat: Stat
    label: str
    unit: str
    description: str


@dataclass(frozen=True)
class FieldGroup:
    key: str
    label: str
    fields: tuple[StatField, ...]


@dataclass(frozen=True)
class TypeChoices:
    """The item types that make sense for a slot, and whether it has a weapon block."""

    armor_types: tuple[ArmorType, ...] = ()
    weapon_types: tuple[WeaponType, ...] = ()
    relic_types: tuple[RelicType, ...] = ()
    has_weapon_block: bool = False


@dataclass(frozen=True)
class EntryPreview:
    """A form as the calculator will see it: the item, or why it cannot be built."""

    item: Item | None
    issues: tuple[ValidationIssue, ...]
    form_errors: tuple[str, ...]
    usable: bool
    """True when the item can be scored: no errors, and for a game item no warnings either."""


class ItemEntryService:
    def __init__(self, ruleset: Ruleset) -> None:
        self._ruleset = ruleset

    def type_choices(self, slot: ItemSlot) -> TypeChoices:
        if slot == ItemSlot.BACK:
            return TypeChoices(armor_types=(ArmorType.CLOTH,))
        if slot in ARMOR_SLOTS:
            return TypeChoices(armor_types=tuple(ArmorType))
        if slot == ItemSlot.TWO_HAND:
            return TypeChoices(
                weapon_types=tuple(w for w in WeaponType if w in TWO_HANDED_WEAPON_TYPES),
                has_weapon_block=True,
            )
        if slot == ItemSlot.RANGED:
            return TypeChoices(
                weapon_types=tuple(w for w in WeaponType if w in RANGED_WEAPON_TYPES),
                has_weapon_block=True,
            )
        if slot in WEAPON_SLOTS:
            return TypeChoices(weapon_types=ONE_HANDED_WEAPONS, has_weapon_block=True)
        if slot == ItemSlot.RELIC:
            return TypeChoices(relic_types=tuple(RelicType))
        return TypeChoices()

    def stat_groups(self, slot: ItemSlot) -> list[FieldGroup]:
        """The ruleset's stats, grouped and ordered for the slot (weapon DPS is computed)."""
        groups: dict[str, list[StatField]] = {}
        for stat_def in self._ruleset.stats:
            if stat_def.stat in WEAPON_DPS_STATS:
                continue
            groups.setdefault(stat_def.group, []).append(
                StatField(stat_def.stat, stat_def.label, stat_def.unit, stat_def.description)
            )
        order = GROUP_ORDER.get(slot, DEFAULT_GROUP_ORDER)
        return [
            FieldGroup(key, GROUP_LABELS[key], tuple(groups[key])) for key in order if key in groups
        ]

    def preview(self, form: ManualItemForm) -> EntryPreview:
        """Normalize and validate a submitted form."""
        try:
            item = form_to_item(form, self._ruleset.id)
        except ValidationError as error:
            messages = tuple(
                f"{'.'.join(str(part) for part in issue['loc']) or 'item'}: {issue['msg']}"
                for issue in error.errors()
            )
            return EntryPreview(item=None, issues=(), form_errors=messages, usable=False)
        report = validate_item(item, self._ruleset)
        return EntryPreview(
            item=item,
            issues=report.issues,
            form_errors=(),
            usable=report.usable(custom=form.custom),
        )

    def read_tooltip(self, text: str, *, custom: bool = False) -> TooltipReading:
        return read_tooltip(text, custom=custom)
