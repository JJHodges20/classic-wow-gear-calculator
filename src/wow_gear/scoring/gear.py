"""What a set of gear adds up to, and what the whole set is worth under a profile.

An item's contribution to the totals is what the scoring engine reads from it in the same
context - its stats, the conditional bonuses whose condition holds, weapon skill only with
a weapon of that type - without weapon damage, which belongs to each weapon, not the set.

A whole set is scored by the engine one item at a time, each on top of the items before it.
A stat's counted amount is the area under its value curve between two totals, so the parts
add up to the same value in any order: the gear's value depends only on what it adds up to
(an exclusive group, which no shipped profile uses, is the exception: it applies per item).
That holds while every item is measured against the same caps. The caps are those of the
gear as worn - its weapon types and its weapon skill - and stay put when another set is
valued against it: version 1 does not value weapon skill, so a change that moves the hit cap
is measured against the current cap rather than counted as a loss or gain of hit.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass

from wow_gear.models.character import CharacterContext
from wow_gear.models.enums import WEAPON_DPS_STATS, WEAPON_SKILL_STATS, EquipmentSlot, Stat
from wow_gear.models.item import Item
from wow_gear.models.profile import BuildProfile
from wow_gear.models.ruleset import Ruleset
from wow_gear.models.score import ScoreComponent, ScoreResult
from wow_gear.scoring.amounts import item_amounts
from wow_gear.scoring.engine import score_item

_EPSILON = 1e-9
_SKILL_STATS = frozenset(WEAPON_SKILL_STATS.values())


def item_totals(
    item: Item, context: CharacterContext, profile: BuildProfile, ruleset: Ruleset
) -> dict[Stat, float]:
    """The stats ``item`` gives in ``context``, without weapon damage per second."""
    totals = item_amounts(item, context, profile, ruleset).totals()
    return {stat: value for stat, value in totals.items() if stat not in WEAPON_DPS_STATS}


def combine(
    base: Mapping[Stat, float], extra: Mapping[Stat, float], sign: float = 1.0
) -> dict[Stat, float]:
    """``base`` plus (or, with ``sign`` -1, minus) ``extra``, dropping zeros."""
    combined = dict(base)
    for stat, value in extra.items():
        combined[stat] = combined.get(stat, 0.0) + sign * value
    return {stat: value for stat, value in combined.items() if abs(value) > _EPSILON}


def gear_totals(
    items: Iterable[Item], context: CharacterContext, profile: BuildProfile, ruleset: Ruleset
) -> dict[Stat, float]:
    """Everything ``items`` add up to in ``context``, in the ruleset's order of stats."""
    totals: dict[Stat, float] = {}
    for item in items:
        totals = combine(totals, item_totals(item, context, profile, ruleset))
    order = {stat_def.stat: index for index, stat_def in enumerate(ruleset.stats)}
    return dict(
        sorted(totals.items(), key=lambda entry: (order.get(entry[0], len(order)), entry[0]))
    )


def with_totals(context: CharacterContext, totals: Mapping[Stat, float]) -> CharacterContext:
    """``context`` with ``totals`` as its current gear totals."""
    data = context.model_dump(mode="python")
    data["current_stats"] = dict(totals)
    return CharacterContext.model_validate(data)


def gear_context(context: CharacterContext, gear: Mapping[EquipmentSlot, Item]) -> CharacterContext:
    """``context`` for a character wearing ``gear``: its weapon types, no gear totals yet."""
    main = gear.get(EquipmentSlot.MAIN_HAND)
    ranged = gear.get(EquipmentSlot.RANGED)
    data = context.model_dump(mode="python")
    data["main_hand_type"] = main.weapon_type if main is not None else None
    data["ranged_type"] = ranged.weapon_type if ranged is not None else None
    data["current_stats"] = None
    return CharacterContext.model_validate(data)


def _unskilled(totals: Mapping[Stat, float]) -> dict[Stat, float]:
    """``totals`` without weapon skill, which the caps take from the gear as worn."""
    return {stat: value for stat, value in totals.items() if stat not in _SKILL_STATS}


@dataclass(frozen=True)
class GearEvaluation:
    """A whole set of gear scored as the character wears it."""

    context: CharacterContext
    """The character wearing the gear: its weapon types, its totals as current gear (with
    the weapon skill of the gear the caps come from)."""
    totals: dict[Stat, float]
    skills: dict[Stat, float]
    """The weapon skill the caps are measured with."""
    results: dict[EquipmentSlot, ScoreResult]
    """Each item scored on top of the items before it in slot order - the parts of
    ``score``, not what each item is worth on its own."""
    score: float
    components: tuple[ScoreComponent, ...]
    """Every item's scored components added up by key, largest first."""


def add_components(results: Iterable[ScoreResult]) -> tuple[ScoreComponent, ...]:
    """The scored components of ``results`` added up by key, largest contribution first.

    The sums carry no notes: a note describes one item's amount, not a total.
    """
    added: dict[str, ScoreComponent] = {}
    for result in results:
        for component in result.components:
            if not component.scored:
                continue
            seen = added.get(component.key)
            if seen is None:
                added[component.key] = component.model_copy(update={"note": None})
                continue
            added[component.key] = seen.model_copy(
                update={
                    "amount": seen.amount + component.amount,
                    "effective_amount": seen.effective_amount + component.effective_amount,
                    "contribution": seen.contribution + component.contribution,
                }
            )
    return tuple(sorted(added.values(), key=lambda c: (-abs(c.contribution), c.label)))


def evaluate_gear(
    gear: Mapping[EquipmentSlot, Item],
    context: CharacterContext,
    profile: BuildProfile,
    ruleset: Ruleset,
    *,
    caps_from: Mapping[EquipmentSlot, Item] | None = None,
) -> GearEvaluation:
    """Score the whole of ``gear`` for the character of ``context`` under ``profile``.

    The caps are those of ``caps_from`` - the gear as worn - when another set is valued
    against it; by default those of ``gear`` itself.
    """
    worn_gear = gear if caps_from is None else caps_from
    worn = gear_context(context, worn_gear)
    totals = gear_totals(gear.values(), worn, profile, ruleset)
    worn_totals = (
        totals if caps_from is None else gear_totals(worn_gear.values(), worn, profile, ruleset)
    )
    skills = {stat: value for stat, value in worn_totals.items() if stat in _SKILL_STATS}
    running: dict[Stat, float] = {}
    results: dict[EquipmentSlot, ScoreResult] = {}
    for slot in EquipmentSlot:
        item = gear.get(slot)
        if item is None:
            continue
        before = with_totals(worn, {**_unskilled(running), **skills})
        results[slot] = score_item(item, before, profile, ruleset)
        running = combine(running, item_totals(item, worn, profile, ruleset))
    return GearEvaluation(
        context=with_totals(worn, {**_unskilled(totals), **skills}),
        totals=totals,
        skills=skills,
        results=results,
        score=sum(result.score for result in results.values()),
        components=add_components(results.values()),
    )
