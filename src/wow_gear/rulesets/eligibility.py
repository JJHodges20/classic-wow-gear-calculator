"""Can this character use this item? The ruleset's class rules, applied to one item.

An item that fails a rule is still scored - the reasons are shown beside its score - so a
player can see what an unusable item would have been worth. Comparisons rank usable items
first.
"""

from __future__ import annotations

from dataclasses import dataclass

from wow_gear.models.character import CharacterContext
from wow_gear.models.enums import ItemSlot
from wow_gear.models.item import Item
from wow_gear.models.labels import weapon_label
from wow_gear.models.ruleset import Ruleset


@dataclass(frozen=True)
class Eligibility:
    eligible: bool
    reasons: tuple[str, ...] = ()


def _plural(label: str) -> str:
    return label if label.endswith("s") else f"{label}s"


def eligibility(item: Item, context: CharacterContext, ruleset: Ruleset) -> Eligibility:
    """Every rule ``item`` breaks for ``context``; none means usable."""
    class_def = ruleset.class_def(context.class_name)
    who = _plural(class_def.label)
    reasons: list[str] = []

    if item.required_level > context.level:
        reasons.append(f"Requires level {item.required_level}; the character is {context.level}")
    if item.phase is not None and item.phase > context.phase:
        reasons.append(f"Available from phase {item.phase}; phase {context.phase} is selected")
    if item.allowed_classes and context.class_name not in item.allowed_classes:
        allowed = ", ".join(ruleset.class_def(c).label for c in item.allowed_classes)
        reasons.append(f"Restricted to {allowed}")
    if item.allowed_races and context.race is not None and context.race not in item.allowed_races:
        allowed = ", ".join(ruleset.race_def(r).label for r in item.allowed_races)
        reasons.append(f"Restricted to {allowed}")

    if item.armor_type is not None:
        from_level = class_def.armor_from_level(item.armor_type)
        if from_level is None:
            reasons.append(f"{who} cannot wear {item.armor_type} armor")
        elif from_level > context.level:
            reasons.append(f"{who} wear {item.armor_type} armor from level {from_level}")

    if item.weapon_type is not None and item.weapon_type not in class_def.weapons:
        reasons.append(f"{who} cannot use {weapon_label(item.weapon_type, plural=True)}")

    if item.slot == ItemSlot.SHIELD and not class_def.shields:
        reasons.append(f"{who} cannot use shields")
    if item.slot == ItemSlot.RELIC and item.relic_type != class_def.relic:
        reasons.append(f"A {item.relic_type} is not a {class_def.label} relic")
    if item.slot == ItemSlot.OFF_HAND:
        problem = dual_wield_problem(context, ruleset)
        if problem:
            reasons.append(problem)

    return Eligibility(eligible=not reasons, reasons=tuple(reasons))


def dual_wield_problem(context: CharacterContext, ruleset: Ruleset) -> str | None:
    """Why the character cannot hold a weapon in the off hand, or None when it can."""
    class_def = ruleset.class_def(context.class_name)
    who = _plural(class_def.label)
    from_level = class_def.dual_wield_from_level
    if from_level is None:
        return f"{who} cannot dual wield"
    if from_level > context.level:
        return f"{who} dual wield from level {from_level}"
    return None
