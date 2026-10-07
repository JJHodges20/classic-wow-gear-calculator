"""Cap formulas and value curves, against hand-calculated values.

Inputs come from configs/rulesets/classic_era.yaml (sources in docs/research/
COMBAT_TABLES.md). Each expected number is worked out in the test's comment.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from wow_gear.calculations.caps import (
    evaluate_cap,
    hit_suppression,
    melee_miss_chance,
    spell_hit_chance,
)
from wow_gear.calculations.curves import FLAT, ValueCurve
from wow_gear.calculations.levels import level_gap, target_level, weapon_skill
from wow_gear.core import ConfigError
from wow_gear.models.character import CharacterContext
from wow_gear.models.enums import ClassName, ContentMode, Race, Role, Stat, WeaponType
from wow_gear.rulesets.loader import load_ruleset

RULESET = load_ruleset(Path(__file__).resolve().parents[2] / "configs/rulesets/classic_era.yaml")
MELEE = RULESET.mechanics.melee_miss
SPELL = RULESET.mechanics.spell_miss


def context(**changes: Any) -> CharacterContext:
    data: dict[str, Any] = {
        "ruleset": "classic_era",
        "phase": 6,
        "level": 60,
        "class_name": ClassName.WARRIOR,
        "role": Role.MELEE_DPS,
        "profile_id": "x",
        "content_mode": ContentMode.RAID,
    }
    data.update(changes)
    return CharacterContext(**data)


class TestLevels:
    @pytest.mark.parametrize(
        ("level", "mode", "expected"),
        [
            (60, ContentMode.RAID, 63),
            (60, ContentMode.DUNGEON, 62),
            (60, ContentMode.LEVELING, 60),
            (60, ContentMode.PVP, 60),
            (40, ContentMode.RAID, 43),
            (62, ContentMode.RAID, 63),  # never above the ruleset's highest target level
        ],
    )
    def test_target_level_follows_the_content_mode(
        self, level: int, mode: ContentMode, expected: int
    ) -> None:
        assert target_level(context(level=level, content_mode=mode), RULESET) == expected

    def test_an_explicit_target_level_wins(self) -> None:
        assert target_level(context(target_level=61), RULESET) == 61
        assert level_gap(context(target_level=58), RULESET) == 0

    def test_base_weapon_skill_is_five_per_level(self) -> None:
        assert weapon_skill(context(), RULESET, WeaponType.SWORD)[0] == 300
        assert weapon_skill(context(level=40), RULESET, None)[0] == 200

    def test_racial_bonus_applies_to_its_weapon_types_only(self) -> None:
        human = context(race=Race.HUMAN)
        assert weapon_skill(human, RULESET, WeaponType.SWORD)[0] == 305
        assert weapon_skill(human, RULESET, WeaponType.TWO_HANDED_MACE)[0] == 305
        assert weapon_skill(human, RULESET, WeaponType.AXE)[0] == 300
        orc = context(race=Race.ORC)
        assert weapon_skill(orc, RULESET, WeaponType.TWO_HANDED_AXE)[0] == 305

    def test_gear_skill_adds_to_the_racial_bonus(self) -> None:
        human = context(race=Race.HUMAN, current_stats={Stat.SWORD_SKILL: 7})
        skill, parts = weapon_skill(human, RULESET, WeaponType.SWORD)
        assert skill == 312
        assert len(parts) == 3


class TestMissFormula:
    @pytest.mark.parametrize(
        ("gap", "miss"),
        [
            (0, 5.0),  # equal skill: 5%
            (7, 5.7),  # 5 + 7 x 0.1
            (10, 6.0),  # 5 + 10 x 0.1: 305 skill against a level 63 boss
            (11, 7.2),  # 5 + 11 x 0.2
            (15, 8.0),  # 5 + 15 x 0.2: 300 skill against 315 defense, Blizzard's 8%
        ],
    )
    def test_melee_miss_chance(self, gap: int, miss: float) -> None:
        assert melee_miss_chance(gap, MELEE) == pytest.approx(miss)

    @pytest.mark.parametrize(("gap", "suppressed"), [(15, 1.0), (11, 0.2), (10, 0.0), (0, 0.0)])
    def test_hit_suppression(self, gap: int, suppressed: float) -> None:
        assert hit_suppression(gap, MELEE) == pytest.approx(suppressed)

    @pytest.mark.parametrize(
        ("levels_above", "chance"), [(0, 96.0), (1, 95.0), (2, 94.0), (3, 83.0), (4, 72.0)]
    )
    def test_spell_hit_chance(self, levels_above: int, chance: float) -> None:
        assert spell_hit_chance(levels_above, SPELL) == pytest.approx(chance)


class TestCaps:
    def test_melee_hit_cap_against_a_raid_boss(self) -> None:
        # 8% miss + 1% suppressed = 9%; the first 1% of hit from gear is worth nothing.
        cap = evaluate_cap("melee_hit", RULESET, context())
        assert (cap.cap, cap.dead_zone) == pytest.approx((9.0, 1.0))
        assert "8% miss" in cap.derivation and "suppressed" in cap.derivation

    def test_talent_hit_moves_the_cap_down(self) -> None:
        # A rogue with 5% from Precision needs 9 - 5 = 4% from gear; no dead zone remains.
        cap = evaluate_cap("melee_hit", RULESET, context(class_name=ClassName.ROGUE), 5)
        assert (cap.cap, cap.dead_zone) == pytest.approx((4.0, 0.0))
        assert "already provided" in cap.derivation

    def test_racial_weapon_skill_lowers_the_cap(self) -> None:
        # A human with a sword has 305 skill: gap 10, 6% miss, no suppression.
        human = context(race=Race.HUMAN, main_hand_type=WeaponType.SWORD)
        cap = evaluate_cap("melee_hit", RULESET, human)
        assert (cap.cap, cap.dead_zone) == pytest.approx((6.0, 0.0))

    def test_equal_level_targets_need_five_percent(self) -> None:
        cap = evaluate_cap("melee_hit", RULESET, context(content_mode=ContentMode.LEVELING))
        assert (cap.cap, cap.dead_zone) == pytest.approx((5.0, 0.0))

    def test_dual_wield_cap(self) -> None:
        # 8% + 19% dual-wield penalty + 1% suppressed = 28%; 25% with 305 skill.
        assert evaluate_cap("dual_wield_hit", RULESET, context()).cap == pytest.approx(28.0)
        human = context(race=Race.HUMAN, main_hand_type=WeaponType.SWORD)
        assert evaluate_cap("dual_wield_hit", RULESET, human).cap == pytest.approx(25.0)

    def test_ranged_cap_uses_the_ranged_weapon(self) -> None:
        hunter = context(class_name=ClassName.HUNTER, race=Race.TROLL)
        assert evaluate_cap("ranged_hit", RULESET, hunter).cap == pytest.approx(9.0)
        with_bow = hunter.model_copy(update={"ranged_type": WeaponType.BOW})
        assert evaluate_cap("ranged_hit", RULESET, with_bow).cap == pytest.approx(6.0)

    def test_spell_hit_cap(self) -> None:
        # 99% maximum - 83% base against a level 63 target = 16% from gear.
        assert evaluate_cap("spell_hit", RULESET, context()).cap == pytest.approx(16.0)
        # A mage with 6% from Elemental Precision needs 10%.
        assert evaluate_cap("spell_hit", RULESET, context(), 6).cap == pytest.approx(10.0)
        # Against a target of the caster's level: 99 - 96 = 3%.
        same = context(content_mode=ContentMode.PVP)
        assert evaluate_cap("spell_hit", RULESET, same).cap == pytest.approx(3.0)

    def test_crit_immunity_defense(self) -> None:
        # A level 63 boss has 315 skill: 5% + 15 x 0.04% = 5.6% crit against 300 defense;
        # 315 + 5 / 0.04 = 440 defense removes it, 140 of it from gear.
        cap = evaluate_cap("crit_immunity_defense", RULESET, context(role=Role.TANK))
        assert cap.cap == pytest.approx(140.0)
        assert "5.6% against 300 defense" in cap.derivation
        # Against an equal-level attacker 5% / 0.04% = 125 from gear.
        pvp = context(role=Role.TANK, content_mode=ContentMode.PVP)
        assert evaluate_cap("crit_immunity_defense", RULESET, pvp).cap == pytest.approx(125.0)

    def test_an_unknown_cap(self) -> None:
        with pytest.raises(ConfigError, match="no cap"):
            evaluate_cap("haste", RULESET, context())


class TestValueCurve:
    HARD = ValueCurve(dead_zone=1.0, full_until=9.0)
    SOFT = ValueCurve(dead_zone=1.0, full_until=9.0, soft_multiplier=0.5, soft_until=28.0)

    def test_a_flat_curve_counts_everything(self) -> None:
        assert FLAT.is_flat
        assert FLAT.counted(0, 5) == 5
        assert FLAT.counted(100, 5) == 5

    @pytest.mark.parametrize(
        ("before", "amount", "counted"),
        [
            (0, 3, 2),  # the first 1% falls in the dead zone
            (1, 3, 3),  # all of it below the cap
            (8, 3, 1),  # only 1 of 3 fits under 9
            (9, 2, 0),  # already capped
            (10, 2, 0),  # beyond the cap
            (5, -2, -2),  # losing hit below the cap loses value
            (10, -2, -1),  # 10 -> 8: only the drop below 9 matters
        ],
    )
    def test_a_hard_cap(self, before: float, amount: float, counted: float) -> None:
        assert self.HARD.counted(before, amount) == pytest.approx(counted)

    @pytest.mark.parametrize(
        ("before", "amount", "counted"),
        [
            (8, 4, 2.5),  # 1 full + 3 at half
            (9, 2, 1.0),  # 2 at half
            (27, 3, 0.5),  # 1 at half, 2 beyond the soft cap end
            (30, 2, 0.0),
        ],
    )
    def test_a_soft_cap(self, before: float, amount: float, counted: float) -> None:
        assert self.SOFT.counted(before, amount) == pytest.approx(counted)

    def test_a_curve_must_be_ordered(self) -> None:
        with pytest.raises(ValueError, match="needs"):
            ValueCurve(dead_zone=5, full_until=2)
        with pytest.raises(ValueError, match="between 0 and 1"):
            ValueCurve(full_until=1, soft_multiplier=2)
