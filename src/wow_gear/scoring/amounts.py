"""What an item provides in a context: its stats, weapon damage and the effects that apply.

Conditional effects ("+81 Attack Power when fighting Undead") count only when the context
meets the condition; procs and on-use effects are kept aside as not scored.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass

from wow_gear.models.character import CharacterContext
from wow_gear.models.enums import RANGED_WEAPON_TYPES, WEAPON_SKILL_STATS, Stat
from wow_gear.models.item import EffectCondition, EffectTrigger, Item, ItemEffect
from wow_gear.models.labels import weapon_label
from wow_gear.models.profile import BuildProfile
from wow_gear.models.ruleset import Ruleset
from wow_gear.models.score import ComponentKind


@dataclass(frozen=True)
class AmountPart:
    """One source of a stat on an item."""

    stat: Stat
    amount: float
    kind: ComponentKind
    label: str
    note: str | None = None


@dataclass(frozen=True)
class InactiveEffect:
    effect: ItemEffect
    reason: str


@dataclass(frozen=True)
class ItemAmounts:
    parts: tuple[AmountPart, ...]
    inactive: tuple[InactiveEffect, ...]
    unscored: tuple[ItemEffect, ...]

    def totals(self) -> dict[Stat, float]:
        totals: dict[Stat, float] = defaultdict(float)
        for part in self.parts:
            totals[part.stat] += part.amount
        return dict(totals)


_SKILL_WEAPONS = {stat: weapon for weapon, stat in WEAPON_SKILL_STATS.items()}


def stat_label(stat: Stat, ruleset: Ruleset) -> str:
    stat_def = ruleset.stat_def(stat)
    return stat_def.label if stat_def else stat.value.replace("_", " ").capitalize()


def is_percent(stat: Stat, ruleset: Ruleset) -> bool:
    stat_def = ruleset.stat_def(stat)
    return stat_def is not None and stat_def.unit == "percent"


def number_text(value: float) -> str:
    """A number as a player reads it: 3,512, 6, 1.5 - at most two decimals."""
    rounded = round(value, 2)
    if rounded == int(rounded):
        return f"{int(rounded):,}"
    return f"{rounded:,.2f}".rstrip("0").rstrip(".")


def amount_text(stat: Stat, value: float, ruleset: Ruleset) -> str:
    """ "6%" for hit, "120" for Stamina: an amount in the stat's unit."""
    return number_text(value) + ("%" if is_percent(stat, ruleset) else "")


def _condition_text(condition: EffectCondition) -> str:
    if condition.target_creature_types:
        names = [c.value.capitalize() for c in condition.target_creature_types]
        return "against " + " and ".join(names)
    forms = [f.replace("_", " ").title() for f in condition.shapeshift_forms]
    return "in " + ", ".join(forms) + " form" + ("s" if len(forms) > 1 else "")


def condition_holds(
    condition: EffectCondition, context: CharacterContext, profile: BuildProfile
) -> tuple[bool, str]:
    """Whether a conditional effect applies, and the reason when it does not."""
    applies = _condition_text(condition)
    if condition.target_creature_types:
        if context.target_creature_type is None:
            return False, f"applies only {applies}; no target creature type is set"
        if context.target_creature_type not in condition.target_creature_types:
            return False, f"applies only {applies}; the target is {context.target_creature_type}"
    if condition.shapeshift_forms and profile.shapeshift_form not in condition.shapeshift_forms:
        return False, f"applies only {applies}; this profile does not shapeshift"
    return True, applies


def item_amounts(
    item: Item, context: CharacterContext, profile: BuildProfile, ruleset: Ruleset
) -> ItemAmounts:
    parts: list[AmountPart] = []
    inactive: list[InactiveEffect] = []
    used = {weapon for weapon in (context.main_hand_type, context.ranged_type) if weapon}
    for stat, value in item.stats.items():
        weapon = _SKILL_WEAPONS.get(stat)
        if weapon is None:
            parts.append(AmountPart(stat, value, ComponentKind.STAT, stat_label(stat, ruleset)))
            continue
        # Weapon skill helps only with a weapon of its type.
        kind = weapon_label(weapon, plural=True)
        if weapon in used:
            parts.append(
                AmountPart(
                    stat,
                    value,
                    ComponentKind.CONTEXT,
                    f"{stat_label(stat, ruleset)} (you use {kind})",
                )
            )
            continue
        why = (
            "the weapon type you fight with is not set"
            if not used
            else "you fight with "
            + " and ".join(weapon_label(w, plural=True) for w in sorted(used))
        )
        effect = ItemEffect(
            trigger=EffectTrigger.EQUIP,
            description=f"{stat_label(stat, ruleset)} +{value:g}",
            stat=stat,
            value=value,
        )
        inactive.append(InactiveEffect(effect, f"applies only with {kind}; {why}"))
    if item.weapon is not None:
        ranged = item.weapon_type in RANGED_WEAPON_TYPES
        stat = Stat.RANGED_WEAPON_DPS if ranged else Stat.MELEE_WEAPON_DPS
        parts.append(
            AmountPart(
                stat,
                item.weapon.dps,
                ComponentKind.WEAPON,
                stat_label(stat, ruleset),
                f"{item.weapon.min_damage:g}-{item.weapon.max_damage:g} damage, "
                f"speed {item.weapon.speed:.2f}",
            )
        )
    unscored: list[ItemEffect] = []
    for effect in item.equip_effects:
        if effect.stat is None or effect.value is None:
            unscored.append(effect)
            continue
        condition = effect.condition
        if condition is None or condition.is_empty:
            parts.append(
                AmountPart(
                    effect.stat, effect.value, ComponentKind.STAT, stat_label(effect.stat, ruleset)
                )
            )
            continue
        holds, reason = condition_holds(condition, context, profile)
        if holds:
            parts.append(
                AmountPart(
                    effect.stat,
                    effect.value,
                    ComponentKind.CONTEXT,
                    f"{stat_label(effect.stat, ruleset)} {reason}",
                    effect.description,
                )
            )
        else:
            inactive.append(InactiveEffect(effect, reason))
    unscored.extend(item.on_use_effects)
    return ItemAmounts(tuple(parts), tuple(inactive), tuple(unscored))
