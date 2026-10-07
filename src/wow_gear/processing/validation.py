"""Checking an item against its ruleset: impossible, implausible and merely unusual.

Every item, manual or looked up, passes through here before it is stored or scored. An
``error`` means the calculator cannot use the item as it stands (a stat the ruleset does not
have, a phase that does not exist). A ``warning`` means the item is unlike anything in the
game - plate below level 40, a sword in a two-hand slot - which a custom (theorycrafted) item
may be on purpose. ``info`` notes what the calculator will not do with it.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from wow_gear.models.enums import (
    RANGED_WEAPON_TYPES,
    TWO_HANDED_WEAPON_TYPES,
    WEAPON_DPS_STATS,
    ItemSlot,
    Stat,
)
from wow_gear.models.item import ARMOR_SLOTS, WEAPON_SLOTS, Item
from wow_gear.models.ruleset import Ruleset

Severity = Literal["error", "warning", "info"]

PERCENT_PER_ITEM_LIMIT = 5.0
"""More than this much hit, crit, spell hit, spell crit, dodge, parry or block on one item is
unusual enough to double-check."""
WEAPON_SPEED_RANGE = (1.0, 4.0)
PERCENT_STATS = (
    Stat.HIT,
    Stat.CRIT,
    Stat.SPELL_HIT,
    Stat.SPELL_CRIT,
    Stat.DODGE,
    Stat.PARRY,
    Stat.BLOCK,
)


@dataclass(frozen=True)
class ValidationIssue:
    code: str
    severity: Severity
    message: str
    field: str | None = None


@dataclass(frozen=True)
class ValidationReport:
    issues: tuple[ValidationIssue, ...]

    @property
    def errors(self) -> tuple[ValidationIssue, ...]:
        return tuple(issue for issue in self.issues if issue.severity == "error")

    @property
    def warnings(self) -> tuple[ValidationIssue, ...]:
        return tuple(issue for issue in self.issues if issue.severity == "warning")

    @property
    def ok(self) -> bool:
        """No errors. Warnings do not block a custom item."""
        return not self.errors

    def usable(self, custom: bool) -> bool:
        """An item from the game must have no warnings either; a custom one only no errors."""
        return self.ok if custom else not (self.errors or self.warnings)


def validate_item(item: Item, ruleset: Ruleset) -> ValidationReport:
    issues: list[ValidationIssue] = []

    def add(code: str, severity: Severity, message: str, field: str | None = None) -> None:
        issues.append(ValidationIssue(code, severity, message, field))

    if item.ruleset != ruleset.id:
        add("ruleset", "error", f"The item is for {item.ruleset}, not {ruleset.label}.", "ruleset")
    phases = {phase.number for phase in ruleset.phases}
    if item.phase is not None and item.phase not in phases:
        add("phase", "error", f"{ruleset.label} has no phase {item.phase}.", "phase")
    if item.required_level > ruleset.max_level:
        add(
            "required_level",
            "error",
            f"Required level {item.required_level} is above the level cap of {ruleset.max_level}.",
            "required_level",
        )
    for stat in item.stats:
        if not ruleset.allows(stat):
            add("stat_not_allowed", "error", f"{ruleset.label} items do not carry {stat}.", "stats")

    if item.slot in ARMOR_SLOTS and item.armor_type is None:
        add(
            "armor_type_missing",
            "warning",
            "No armor type: whether a class can wear it cannot be checked.",
            "armor_type",
        )
    if item.slot in WEAPON_SLOTS:
        if item.weapon_type is None:
            add(
                "weapon_type_missing",
                "warning",
                "No weapon type: whether a class can use it cannot be checked.",
                "weapon_type",
            )
        if item.weapon is None:
            add(
                "weapon_damage_missing",
                "warning",
                "No weapon damage: its damage per second will not be scored.",
                "weapon",
            )
    if item.weapon_type is not None:
        is_two_handed = item.weapon_type in TWO_HANDED_WEAPON_TYPES
        is_ranged = item.weapon_type in RANGED_WEAPON_TYPES
        if item.slot == ItemSlot.TWO_HAND and not is_two_handed:
            add("slot_type", "warning", f"A {item.weapon_type} is not two-handed.", "weapon_type")
        if item.slot in (ItemSlot.ONE_HAND, ItemSlot.MAIN_HAND, ItemSlot.OFF_HAND) and (
            is_two_handed or is_ranged
        ):
            add(
                "slot_type",
                "warning",
                f"A {item.weapon_type} is not a one-hand weapon.",
                "weapon_type",
            )
        if item.slot == ItemSlot.RANGED and not is_ranged:
            add(
                "slot_type",
                "warning",
                f"A {item.weapon_type} is not a ranged weapon.",
                "weapon_type",
            )
    if (
        item.weapon is not None
        and not WEAPON_SPEED_RANGE[0] <= item.weapon.speed <= WEAPON_SPEED_RANGE[1]
    ):
        add(
            "weapon_speed",
            "warning",
            f"Speed {item.weapon.speed:.2f} is outside the usual {WEAPON_SPEED_RANGE[0]:g} to "
            f"{WEAPON_SPEED_RANGE[1]:g} seconds.",
            "weapon",
        )

    if item.armor_type is not None:
        levels = [
            level
            for class_def in ruleset.classes
            if (level := class_def.armor_from_level(item.armor_type)) is not None
        ]
        earliest = min(levels) if levels else None
        if earliest is not None and item.required_level < earliest:
            add(
                "armor_level",
                "warning",
                f"No class can wear {item.armor_type} before level {earliest}, but the item "
                f"requires level {item.required_level}.",
                "required_level",
            )

    for stat, value in item.stats.items():
        if value < 0:
            add("negative_stat", "warning", f"{stat} is negative ({value:g}).", "stats")
        if stat in PERCENT_STATS and value > PERCENT_PER_ITEM_LIMIT:
            add(
                "large_percent",
                "warning",
                f"{value:g}% {stat} on one item is unusually high; percentages are entered as "
                "numbers (1 means 1%).",
                "stats",
            )
    if item.slot not in WEAPON_SLOTS and any(stat in WEAPON_DPS_STATS for stat in item.stats):
        add("weapon_dps_stat", "error", "Weapon damage per second comes from a weapon.", "stats")

    unscored = [effect for effect in item.equip_effects if effect.stat is None]
    if unscored or item.on_use_effects:
        add(
            "unscored_effects",
            "info",
            f"{len(unscored) + len(item.on_use_effects)} effect(s) are kept as text and not scored.",
            "effects",
        )
    if not item.stats and item.weapon is None and not item.equip_effects:
        add("empty", "warning", "The item has no stats, armor, weapon damage or effects.", "stats")
    return ValidationReport(tuple(issues))
