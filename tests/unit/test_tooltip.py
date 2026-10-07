"""Tooltip lines into stats: every Classic wording the calculator scores, and what it leaves alone."""

from __future__ import annotations

import pytest

from wow_gear.models.enums import CreatureType, Stat
from wow_gear.models.item import EffectTrigger
from wow_gear.processing.tooltip import parse_line, parse_tooltip


@pytest.mark.parametrize(
    ("line", "stat", "value"),
    [
        ("+18 Strength", Stat.STRENGTH, 18),
        ("+9 Agility", Stat.AGILITY, 9),
        ("-10 Spirit", Stat.SPIRIT, -10),
        ("565 Armor", Stat.ARMOR, 565),
        ("47 Block", Stat.BLOCK_VALUE, 47),
        ("+10 Fire Resistance", Stat.FIRE_RESISTANCE, 10),
        ("Equip: Improves your chance to hit by 2%.", Stat.HIT, 2),
        ("Equip: Improves your chance to get a critical strike by 1%.", Stat.CRIT, 1),
        ("Equip: Improves your chance to hit with spells by 1%.", Stat.SPELL_HIT, 1),
        (
            "Equip: Improves your chance to get a critical strike with spells by 1%.",
            Stat.SPELL_CRIT,
            1,
        ),
        ("Equip: +56 Attack Power.", Stat.ATTACK_POWER, 56),
        ("Equip: +20 ranged Attack Power.", Stat.RANGED_ATTACK_POWER, 20),
        (
            "Equip: Increases damage and healing done by magical spells and effects by up to 25.",
            Stat.SPELL_POWER,
            25,
        ),
        (
            "Equip: Increases healing done by spells and effects by up to 44.",
            Stat.HEALING_POWER,
            44,
        ),
        (
            "Equip: Increases damage done by Shadow spells and effects by up to 30.",
            Stat.SHADOW_SPELL_POWER,
            30,
        ),
        (
            "Equip: Increases damage done by magical spells and effects by up to 12.",
            Stat.SPELL_DAMAGE,
            12,
        ),
        ("Equip: Restores 6 mana per 5 sec.", Stat.MP5, 6),
        ("Equip: Restores 10 health per 5 sec.", Stat.HP5, 10),
        ("Equip: Increased Defense +7.", Stat.DEFENSE, 7),
        ("Equip: Increases your chance to dodge an attack by 1%.", Stat.DODGE, 1),
        ("Equip: Increases your chance to parry an attack by 1%.", Stat.PARRY, 1),
        ("Equip: Increases your chance to block attacks with a shield by 2%.", Stat.BLOCK, 2),
        ("Equip: Increases the block value of your shield by 26.", Stat.BLOCK_VALUE, 26),
        (
            "Equip: Decreases the magical resistances of your spell targets by 10.",
            Stat.SPELL_PENETRATION,
            10,
        ),
        ("Equip: Increased Swords +7.", Stat.SWORD_SKILL, 7),
        ("Equip: Increased Two-handed Maces +5.", Stat.TWO_HANDED_MACE_SKILL, 5),
        ("Equip: Increased Fist Weapons +4.", Stat.FIST_SKILL, 4),
    ],
)
def test_recognized_lines(line: str, stat: Stat, value: float) -> None:
    parsed = parse_line(line)
    assert parsed.recognized
    assert (parsed.stats[0].stat, parsed.stats[0].value) == (stat, value)
    assert parsed.stats[0].condition is None


def test_equip_lines_carry_the_equip_trigger_and_stat_lines_none() -> None:
    assert parse_line("Equip: Increased Defense +7.").trigger == EffectTrigger.EQUIP
    assert parse_line("+10 Stamina").trigger is None


def test_generic_attack_power_also_counts_for_ranged() -> None:
    stats = {line.stat: line.value for line in parse_line("Equip: +20 Attack Power.").stats}
    assert stats == {Stat.ATTACK_POWER: 20, Stat.RANGED_ATTACK_POWER: 20}


def test_attack_power_against_a_creature_type_is_conditional() -> None:
    parsed = parse_line("Equip: +81 Attack Power when fighting Undead.")
    assert {line.stat for line in parsed.stats} == {Stat.ATTACK_POWER, Stat.RANGED_ATTACK_POWER}
    condition = parsed.stats[0].condition
    assert condition is not None and condition.target_creature_types == (CreatureType.UNDEAD,)
    both = parse_line("Equip: +150 Attack Power when fighting Undead and Demons.")
    assert both.stats[0].condition is not None
    assert set(both.stats[0].condition.target_creature_types) == {
        CreatureType.UNDEAD,
        CreatureType.DEMON,
    }


def test_spell_damage_against_undead_is_conditional() -> None:
    parsed = parse_line(
        "Equip: Increases damage done to Undead by magical spells and effects by up to 35."
    )
    assert parsed.stats[0].stat == Stat.SPELL_DAMAGE and parsed.stats[0].value == 35
    assert parsed.stats[0].condition is not None


def test_feral_attack_power_applies_in_forms_only() -> None:
    parsed = parse_line("Equip: +120 Attack Power in Cat, Bear, and Dire Bear forms only.")
    line = parsed.stats[0]
    assert line.stat == Stat.FERAL_ATTACK_POWER and line.value == 120
    assert line.condition is not None and "cat" in line.condition.shapeshift_forms


def test_all_resistances_grant_each_school() -> None:
    parsed = parse_line("+5 All Resistances")
    assert len(parsed.stats) == 5 and {line.value for line in parsed.stats} == {5}


def test_the_later_healing_wording_splits_into_both_stats() -> None:
    parsed = parse_line(
        "Equip: Increases healing done by up to 53 and damage done by up to 18 for all "
        "magical spells and effects."
    )
    stats = {line.stat: line.value for line in parsed.stats}
    assert stats == {Stat.SPELL_POWER: 18, Stat.HEALING_POWER: 35}


@pytest.mark.parametrize(
    "line",
    [
        "Chance on hit: Blasts your enemy with lightning, dealing 300 Nature damage.",
        "Use: Increases your attack power by 260 for 20 sec.",
        "Equip: Increases your effective stealth level by 1.",
        "Equip: 2% chance on melee hit to gain 1 extra attack.",
        "Soulbound",
    ],
)
def test_procs_uses_and_unknown_lines_are_kept_as_text(line: str) -> None:
    parsed = parse_line(line)
    assert not parsed.recognized
    assert parsed.text == line


def test_use_and_proc_triggers_are_recognized_even_when_not_scored() -> None:
    assert parse_line("Use: Restores 375 to 625 mana.").trigger == EffectTrigger.USE
    assert parse_line("Chance on hit: Stuns target.").trigger == EffectTrigger.CHANCE_ON_HIT


def test_a_whole_tooltip_skips_blank_lines() -> None:
    lines = ["Lionheart Helm", "", "Head   Plate", "565 Armor", "+18 Strength", "  "]
    parsed = parse_tooltip(lines)
    assert len(parsed) == 4
    assert [p.recognized for p in parsed] == [False, False, True, True]


def test_whitespace_and_missing_period_do_not_matter() -> None:
    assert parse_line("  Equip:   Improves your chance to hit by 1%  ").stats[0].value == 1
