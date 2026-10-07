"""Reading Classic item tooltip text into stats.

Providers such as the Blizzard API describe equip effects as text ("Equip: Improves your
chance to hit by 1%."), and a player can paste a tooltip into the manual entry form. This
module turns each line into a stat and value when it recognizes the wording, and keeps every
other line as text, so that nothing on an item is silently dropped or guessed at.
"""

from __future__ import annotations

import re
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field

from wow_gear.models.enums import CreatureType, Stat
from wow_gear.models.item import EffectCondition, EffectTrigger

_NUMBER = r"(\d+(?:\.\d+)?)"
_SCHOOLS = {
    "arcane": Stat.ARCANE_SPELL_POWER,
    "fire": Stat.FIRE_SPELL_POWER,
    "frost": Stat.FROST_SPELL_POWER,
    "holy": Stat.HOLY_SPELL_POWER,
    "nature": Stat.NATURE_SPELL_POWER,
    "shadow": Stat.SHADOW_SPELL_POWER,
}
_RESISTANCES = {
    "arcane": Stat.ARCANE_RESISTANCE,
    "fire": Stat.FIRE_RESISTANCE,
    "frost": Stat.FROST_RESISTANCE,
    "nature": Stat.NATURE_RESISTANCE,
    "shadow": Stat.SHADOW_RESISTANCE,
}
_PRIMARY = {
    "strength": Stat.STRENGTH,
    "agility": Stat.AGILITY,
    "stamina": Stat.STAMINA,
    "intellect": Stat.INTELLECT,
    "spirit": Stat.SPIRIT,
}
_WEAPON_SKILLS = {
    "daggers": Stat.DAGGER_SKILL,
    "swords": Stat.SWORD_SKILL,
    "two-handed swords": Stat.TWO_HANDED_SWORD_SKILL,
    "axes": Stat.AXE_SKILL,
    "two-handed axes": Stat.TWO_HANDED_AXE_SKILL,
    "maces": Stat.MACE_SKILL,
    "two-handed maces": Stat.TWO_HANDED_MACE_SKILL,
    "fist weapons": Stat.FIST_SKILL,
    "polearms": Stat.POLEARM_SKILL,
    "staves": Stat.STAFF_SKILL,
    "bows": Stat.BOW_SKILL,
    "guns": Stat.GUN_SKILL,
    "crossbows": Stat.CROSSBOW_SKILL,
}
_CREATURES = {
    "beasts": CreatureType.BEAST,
    "demons": CreatureType.DEMON,
    "dragonkin": CreatureType.DRAGONKIN,
    "elementals": CreatureType.ELEMENTAL,
    "giants": CreatureType.GIANT,
    "humanoids": CreatureType.HUMANOID,
    "mechanicals": CreatureType.MECHANICAL,
    "undead": CreatureType.UNDEAD,
}
_FERAL_FORMS = ("cat", "bear", "dire_bear")


@dataclass(frozen=True)
class StatLine:
    """A recognized amount of one stat, possibly only under a condition."""

    stat: Stat
    value: float
    condition: EffectCondition | None = None


@dataclass(frozen=True)
class ParsedLine:
    """One tooltip line: what it says, its trigger, and the stats it grants."""

    text: str
    trigger: EffectTrigger | None
    """Equip, use or chance on hit; None for a plain stat line such as "+10 Stamina"."""
    stats: tuple[StatLine, ...] = field(default=())

    @property
    def recognized(self) -> bool:
        return bool(self.stats)


def _creatures(phrase: str) -> tuple[CreatureType, ...] | None:
    words = [w.strip().lower() for w in re.split(r",|\band\b", phrase) if w.strip()]
    found = tuple(_CREATURES[w] for w in words if w in _CREATURES)
    return found if found and len(found) == len(words) else None


Rule = tuple[re.Pattern[str], Callable[[re.Match[str]], tuple[StatLine, ...] | None]]


def _one(stat: Stat) -> Callable[[re.Match[str]], tuple[StatLine, ...]]:
    return lambda match: (StatLine(stat, float(match.group(1))),)


def _primary(match: re.Match[str]) -> tuple[StatLine, ...]:
    sign = -1.0 if match.group(1) == "-" else 1.0
    return (StatLine(_PRIMARY[match.group(3).lower()], sign * float(match.group(2))),)


def _resistance(match: re.Match[str]) -> tuple[StatLine, ...]:
    value = float(match.group(1))
    school = match.group(2).lower()
    if school == "all":
        return tuple(StatLine(stat, value) for stat in _RESISTANCES.values())
    return (StatLine(_RESISTANCES[school], value),)


def _conditional_ap(match: re.Match[str]) -> tuple[StatLine, ...] | None:
    creatures = _creatures(match.group(2))
    if creatures is None:
        return None
    condition = EffectCondition(target_creature_types=creatures)
    value = float(match.group(1))
    return (
        StatLine(Stat.ATTACK_POWER, value, condition),
        StatLine(Stat.RANGED_ATTACK_POWER, value, condition),
    )


def _conditional_spell(match: re.Match[str]) -> tuple[StatLine, ...] | None:
    creatures = _creatures(match.group(1))
    if creatures is None:
        return None
    condition = EffectCondition(target_creature_types=creatures)
    return (StatLine(Stat.SPELL_DAMAGE, float(match.group(2)), condition),)


def _feral(match: re.Match[str]) -> tuple[StatLine, ...]:
    condition = EffectCondition(shapeshift_forms=_FERAL_FORMS)
    return (StatLine(Stat.FERAL_ATTACK_POWER, float(match.group(1)), condition),)


def _healing_and_damage_values(healing: float, damage: float) -> tuple[StatLine, ...]:
    # The shared amount counts for both; any excess for healing or damage only.
    shared = min(healing, damage)
    lines = [StatLine(Stat.SPELL_POWER, shared)]
    if healing > shared:
        lines.append(StatLine(Stat.HEALING_POWER, healing - shared))
    if damage > shared:
        lines.append(StatLine(Stat.SPELL_DAMAGE, damage - shared))
    return tuple(lines)


def _healing_and_damage(match: re.Match[str]) -> tuple[StatLine, ...]:
    # "Increases healing done by up to X and damage done by up to Y".
    return _healing_and_damage_values(float(match.group(1)), float(match.group(2)))


_RULES: list[Rule] = [
    (re.compile(r"^(\+|-)?(\d+) (strength|agility|stamina|intellect|spirit)$", re.I), _primary),
    (re.compile(rf"^\+?{_NUMBER} armor$", re.I), _one(Stat.ARMOR)),
    (re.compile(rf"^{_NUMBER} block$", re.I), _one(Stat.BLOCK_VALUE)),
    (
        re.compile(rf"^\+{_NUMBER} (fire|frost|nature|shadow|arcane|all) resistances?$", re.I),
        _resistance,
    ),
    (
        re.compile(rf"^improves your chance to hit with spells by {_NUMBER}%$", re.I),
        _one(Stat.SPELL_HIT),
    ),
    (re.compile(rf"^improves your chance to hit by {_NUMBER}%$", re.I), _one(Stat.HIT)),
    (
        re.compile(
            rf"^improves your chance to get a critical strike with spells by {_NUMBER}%$", re.I
        ),
        _one(Stat.SPELL_CRIT),
    ),
    (
        re.compile(rf"^improves your chance to get a critical strike by {_NUMBER}%$", re.I),
        _one(Stat.CRIT),
    ),
    (re.compile(rf"^\+{_NUMBER} ranged attack power$", re.I), _one(Stat.RANGED_ATTACK_POWER)),
    (
        re.compile(rf"^\+{_NUMBER} attack power when fighting (.+)$", re.I),
        _conditional_ap,
    ),
    (
        re.compile(rf"^attack power increased by {_NUMBER} when fighting (.+)$", re.I),
        _conditional_ap,
    ),
    (
        re.compile(
            rf"^\+{_NUMBER} attack power in cat, bear,? (?:and )?dire bear(?:,? and moonkin)? forms only$",
            re.I,
        ),
        _feral,
    ),
    (
        re.compile(rf"^\+{_NUMBER} attack power$", re.I),
        lambda match: (
            StatLine(Stat.ATTACK_POWER, float(match.group(1))),
            StatLine(Stat.RANGED_ATTACK_POWER, float(match.group(1))),
        ),
    ),
    (
        re.compile(
            rf"^increases damage and healing done by magical spells and effects by up to {_NUMBER}$",
            re.I,
        ),
        _one(Stat.SPELL_POWER),
    ),
    (
        re.compile(rf"^increases healing done by spells and effects by up to {_NUMBER}$", re.I),
        _one(Stat.HEALING_POWER),
    ),
    (
        re.compile(
            rf"^increases damage done by magical spells and effects by up to {_NUMBER}$", re.I
        ),
        _one(Stat.SPELL_DAMAGE),
    ),
    (
        re.compile(
            rf"^increases healing done by up to {_NUMBER} and damage done by up to {_NUMBER} "
            r"for all magical spells and effects$",
            re.I,
        ),
        _healing_and_damage,
    ),
    (
        re.compile(
            rf"^increases damage done to (.+) by magical spells and effects by up to {_NUMBER}$",
            re.I,
        ),
        _conditional_spell,
    ),
    (
        re.compile(
            rf"^increases damage done by (arcane|fire|frost|holy|nature|shadow) spells and effects by up to {_NUMBER}$",
            re.I,
        ),
        lambda match: (StatLine(_SCHOOLS[match.group(1).lower()], float(match.group(2))),),
    ),
    (re.compile(rf"^restores {_NUMBER} mana per 5 sec(?:onds)?$", re.I), _one(Stat.MP5)),
    (
        re.compile(rf"^restores {_NUMBER} mana every sec$", re.I),
        lambda match: (StatLine(Stat.MP5, round(float(match.group(1)) * 5, 6)),),
    ),
    (
        re.compile(
            rf"^increases your spell damage by up to {_NUMBER} and your healing by up to {_NUMBER}$",
            re.I,
        ),
        lambda match: _healing_and_damage_values(float(match.group(2)), float(match.group(1))),
    ),
    (
        re.compile(rf"^decreases your chance to (dodge|parry) an attack by {_NUMBER}%$", re.I),
        lambda match: (
            StatLine(
                Stat.DODGE if match.group(1).lower() == "dodge" else Stat.PARRY,
                -float(match.group(2)),
            ),
        ),
    ),
    (re.compile(rf"^restores {_NUMBER} health per 5 sec$", re.I), _one(Stat.HP5)),
    (re.compile(rf"^increased defense \+{_NUMBER}$", re.I), _one(Stat.DEFENSE)),
    (
        re.compile(rf"^increases your chance to dodge an attack by {_NUMBER}%$", re.I),
        _one(Stat.DODGE),
    ),
    (
        re.compile(rf"^increases your chance to parry an attack by {_NUMBER}%$", re.I),
        _one(Stat.PARRY),
    ),
    (
        re.compile(rf"^increases your chance to block attacks with a shield by {_NUMBER}%$", re.I),
        _one(Stat.BLOCK),
    ),
    (
        re.compile(rf"^increases the block value of your shield by {_NUMBER}$", re.I),
        _one(Stat.BLOCK_VALUE),
    ),
    (
        re.compile(
            rf"^decreases the magical resistances of your spell targets by {_NUMBER}$", re.I
        ),
        _one(Stat.SPELL_PENETRATION),
    ),
    (
        re.compile(
            r"^increased (daggers|swords|two-handed swords|axes|two-handed axes|maces|"
            rf"two-handed maces|fist weapons|polearms|staves|bows|guns|crossbows) \+{_NUMBER}$",
            re.I,
        ),
        lambda match: (StatLine(_WEAPON_SKILLS[match.group(1).lower()], float(match.group(2))),),
    ),
]

_TRIGGERS = (
    ("equip:", EffectTrigger.EQUIP),
    ("use:", EffectTrigger.USE),
    ("chance on hit:", EffectTrigger.CHANCE_ON_HIT),
)


def _clean(text: str) -> str:
    text = re.sub(r"\s+", " ", text.replace(" ", " ")).strip()
    return text.rstrip(".").strip()


def parse_line(text: str) -> ParsedLine:
    """Parse one tooltip line. Unrecognized lines come back with no stats, never an error."""
    original = text.strip()
    body = _clean(original)
    trigger: EffectTrigger | None = None
    lowered = body.lower()
    for prefix, kind in _TRIGGERS:
        if lowered.startswith(prefix):
            trigger = kind
            body = body[len(prefix) :].strip()
            break
    if trigger in (EffectTrigger.USE, EffectTrigger.CHANCE_ON_HIT):
        return ParsedLine(text=original, trigger=trigger)
    # Some lines add a second sentence ("... It also allows the acquisition of
    # Scourgestones"); when the whole line is not recognized, its first sentence may be.
    first_sentence = re.split(r"\.\s+", body, maxsplit=1)[0].strip()
    for candidate in dict.fromkeys((body, first_sentence)):
        for pattern, build in _RULES:
            match = pattern.match(candidate)
            if match:
                stats = build(match)
                if stats:
                    return ParsedLine(text=original, trigger=trigger, stats=stats)
    return ParsedLine(text=original, trigger=trigger)


def parse_tooltip(lines: Iterable[str]) -> list[ParsedLine]:
    """Parse every non-empty line of a tooltip."""
    return [parse_line(line) for line in lines if line and line.strip()]
