"""Cap formulas: how much of a stat from gear is worth something in a given context.

Each formula kind named in a ruleset (``CapDef.kind``) is implemented here once. A formula
returns the range of gear amounts that carries value: below ``dead_zone`` the stat is
suppressed, above ``cap`` it is wasted. Talents or the build that already provide some of
the stat (``reduced_by``) move the range down.

Sources for the formulas and their inputs are cited in the ruleset and in
docs/research/COMBAT_TABLES.md.
"""

from __future__ import annotations

from dataclasses import dataclass

from wow_gear.calculations.levels import level_gap, target_level, weapon_skill
from wow_gear.core.errors import ConfigError
from wow_gear.models.character import CharacterContext
from wow_gear.models.ruleset import CapDef, MeleeMissParameters, Ruleset, SpellMissParameters


@dataclass(frozen=True)
class EvaluatedCap:
    """A cap evaluated for one context, in the stat's units (percent for hit)."""

    name: str
    cap: float
    """Gear amount beyond which the stat is worth nothing."""
    dead_zone: float
    """Gear amount below which the stat is worth nothing (hit suppression)."""
    derivation: str
    """How the number was reached, for the explanation."""


def melee_miss_chance(gap: int, params: MeleeMissParameters) -> float:
    """Chance to miss a target whose defense exceeds the attacker's skill by ``gap``."""
    gap = max(0, gap)
    if gap <= params.small_gap_limit:
        return params.base_miss + gap * params.per_point_small_gap
    return params.base_miss + gap * params.per_point_large_gap


def hit_suppression(gap: int, params: MeleeMissParameters) -> float:
    """Hit from gear that is ignored when the skill gap exceeds the small-gap limit."""
    return max(0, gap - params.small_gap_limit) * params.suppression_per_point_beyond_limit


def spell_hit_chance(levels_above: int, params: SpellMissParameters) -> float:
    """A spell's base chance to hit a target ``levels_above`` levels higher."""
    levels_above = max(0, levels_above)
    table = params.hit_chance_by_level_gap
    largest = max(table)
    if levels_above <= largest:
        return table[levels_above]
    return table[largest] - (levels_above - largest) * params.per_level_beyond_table


def _reduce(cap: float, dead_zone: float, reduced_by: float) -> tuple[float, float]:
    return max(0.0, cap - reduced_by), max(0.0, dead_zone - reduced_by)


def _melee_like(
    cap_def: CapDef,
    context: CharacterContext,
    ruleset: Ruleset,
    *,
    ranged: bool,
    dual_wield: bool,
) -> tuple[float, float, str]:
    params = ruleset.mechanics.melee_miss
    weapon_type = context.ranged_type if ranged else context.main_hand_type
    skill, parts = weapon_skill(context, ruleset, weapon_type)
    level = target_level(context, ruleset)
    defense = level * params.skill_per_level
    gap = max(0, defense - skill)
    miss = melee_miss_chance(gap, params)
    suppressed = hit_suppression(gap, params)
    total = miss + suppressed
    detail = (
        f"target level {level} has {defense} defense; weapon skill {skill} "
        f"({', '.join(parts)}); gap {gap}: {miss:g}% miss"
    )
    if dual_wield:
        total += params.dual_wield_penalty
        detail += f", +{params.dual_wield_penalty:g}% dual-wield penalty on white hits"
    if suppressed:
        detail += f", first {suppressed:g}% of hit suppressed"
    return total, suppressed, detail


def evaluate_cap(
    name: str, ruleset: Ruleset, context: CharacterContext, reduced_by: float = 0.0
) -> EvaluatedCap:
    """Evaluate the ruleset cap ``name`` for ``context``."""
    try:
        cap_def = ruleset.caps[name]
    except KeyError:
        raise ConfigError(f"ruleset {ruleset.id} has no cap {name!r}") from None

    if cap_def.kind in ("melee_miss", "dual_wield_miss", "ranged_miss"):
        total, dead, detail = _melee_like(
            cap_def,
            context,
            ruleset,
            ranged=cap_def.kind == "ranged_miss",
            dual_wield=cap_def.kind == "dual_wield_miss",
        )
    elif cap_def.kind == "spell_miss":
        params = ruleset.mechanics.spell_miss
        above = level_gap(context, ruleset)
        chance = spell_hit_chance(above, params)
        total, dead = max(0.0, params.max_hit_chance - chance), 0.0
        detail = (
            f"base spell hit {chance:g}% against a target {above} level(s) higher, "
            f"at most {params.max_hit_chance:g}%"
        )
    elif cap_def.kind == "defense_crit_immunity":
        params_d = ruleset.mechanics.defense
        level = target_level(context, ruleset)
        attacker_skill = level * params_d.skill_per_level
        base_defense = context.level * params_d.skill_per_level
        crit = params_d.base_crit_chance + (attacker_skill - base_defense) * (
            params_d.crit_change_per_skill_point
        )
        needed = attacker_skill + params_d.base_crit_chance / params_d.crit_change_per_skill_point
        total, dead = needed - base_defense, 0.0
        detail = (
            f"a level {level} attacker ({attacker_skill} skill) crits {crit:g}% against "
            f"{base_defense} defense; {needed:g} defense removes it"
        )
    else:  # pragma: no cover - CapKind is a closed Literal
        raise ConfigError(f"no formula for cap kind {cap_def.kind!r}")

    cap, dead_zone = _reduce(total, dead, reduced_by)
    if reduced_by:
        detail += f"; {reduced_by:g} already provided by the build"
    return EvaluatedCap(name=name, cap=cap, dead_zone=dead_zone, derivation=detail)
