"""Levels and skills a context implies: the target's level and the character's weapon skill."""

from __future__ import annotations

from wow_gear.models.character import CharacterContext
from wow_gear.models.enums import WEAPON_SKILL_STATS, WeaponType
from wow_gear.models.ruleset import Ruleset


def target_level(context: CharacterContext, ruleset: Ruleset) -> int:
    """The level of what the character fights: an explicit override, else the content mode's.

    Raid content puts the target three levels above a level-60 character, and so on; the
    offsets live in the ruleset, never here. The result never exceeds the ruleset's highest
    target level.
    """
    if context.target_level is not None:
        return context.target_level
    offset = ruleset.content_mode(context.content_mode).target_level_offset
    return min(context.level + offset, ruleset.max_target_level)


def level_gap(context: CharacterContext, ruleset: Ruleset) -> int:
    """How many levels the target stands above the character (never negative)."""
    return max(0, target_level(context, ruleset) - context.level)


def weapon_skill(
    context: CharacterContext, ruleset: Ruleset, weapon_type: WeaponType | None
) -> tuple[int, list[str]]:
    """The character's skill with ``weapon_type`` and the parts it is made of.

    Base skill is level x the ruleset's skill per level (a character keeps weapon skill
    trained to its maximum); a racial bonus and the weapon-skill total of current gear add
    to it. Returns the skill and a description of each part, for the explanation.
    """
    per_level = ruleset.mechanics.melee_miss.skill_per_level
    skill = context.level * per_level
    parts = [f"{skill} base ({context.level} x {per_level})"]
    if weapon_type is None:
        return skill, parts
    if context.race is not None:
        racial = ruleset.race_def(context.race).weapon_skill_bonus.get(weapon_type, 0)
        if racial:
            skill += racial
            parts.append(f"+{racial} {context.race} racial ({weapon_type})")
    stat = WEAPON_SKILL_STATS.get(weapon_type)
    if stat is not None:
        from_gear = int(context.current(stat))
        if from_gear:
            skill += from_gear
            parts.append(f"+{from_gear} from current gear")
    return skill, parts
