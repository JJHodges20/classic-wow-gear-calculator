"""Formulas the reviews do not reach: every class conversion rate, conversions applied,
fixed caps, a soft cap without an end, breakpoints already reached or lost, and how a cap
message splits an amount that starts below zero. Expected values are worked out by hand."""

from __future__ import annotations

import math
from pathlib import Path
from typing import Any

import pytest

from wow_gear.calculations.caps import resolve_cap
from wow_gear.calculations.conversions import derive
from wow_gear.calculations.curves import ValueCurve
from wow_gear.models.character import CharacterContext
from wow_gear.models.enums import ClassName, ContentMode, ItemSlot, Stat
from wow_gear.models.item import Item, Provenance
from wow_gear.models.profile import CapReference, DerivedStatRule, HardCap
from wow_gear.profiles.loader import load_profile
from wow_gear.rulesets.loader import RulesetRegistry
from wow_gear.scoring.engine import score_item

ROOT = Path(__file__).resolve().parents[2]
RULESETS = RulesetRegistry.from_directory(ROOT / "configs" / "rulesets")
RULESET = RULESETS.get("classic_era")
FURY = load_profile(ROOT / "data/fixtures/profiles/warrior/fixture_warrior_fury.yaml", RULESETS)
TANK = load_profile(ROOT / "data/fixtures/profiles/warrior/fixture_warrior_tank.yaml", RULESETS)
FIXTURE = Provenance(provider="fixture", source="Test", data_version="t-1", custom=True)

# Level-60 conversions as docs/research/STAT_CONVERSIONS.md records them from their sources:
# (kind, rate) - "per_point" gives that much of the target per point, "points_per_unit"
# takes that many points for one unit (1%) of the target.
RATES: dict[tuple[str, str], tuple[str, float]] = {
    ("warrior", "strength->attack_power"): ("per_point", 2),
    ("warrior", "agility->ranged_attack_power"): ("per_point", 1),
    ("warrior", "agility->crit"): ("points_per_unit", 20),
    ("warrior", "agility->dodge"): ("points_per_unit", 20),
    ("warrior", "agility->armor"): ("per_point", 2),
    ("warrior", "strength->block_value"): ("points_per_unit", 20),
    ("paladin", "strength->attack_power"): ("per_point", 2),
    ("paladin", "agility->crit"): ("points_per_unit", 20),
    ("paladin", "agility->dodge"): ("points_per_unit", 19.767),
    ("paladin", "agility->armor"): ("per_point", 2),
    ("paladin", "strength->block_value"): ("points_per_unit", 20),
    ("paladin", "intellect->spell_crit"): ("points_per_unit", 54),
    ("hunter", "strength->attack_power"): ("per_point", 1),
    ("hunter", "agility->attack_power"): ("per_point", 1),
    ("hunter", "agility->ranged_attack_power"): ("per_point", 2),
    ("hunter", "agility->crit"): ("points_per_unit", 53),
    ("hunter", "agility->dodge"): ("points_per_unit", 26.5),
    ("hunter", "agility->armor"): ("per_point", 2),
    ("rogue", "strength->attack_power"): ("per_point", 1),
    ("rogue", "agility->attack_power"): ("per_point", 1),
    ("rogue", "agility->ranged_attack_power"): ("per_point", 1),
    ("rogue", "agility->crit"): ("points_per_unit", 29),
    ("rogue", "agility->dodge"): ("points_per_unit", 14.5),
    ("rogue", "agility->armor"): ("per_point", 2),
    ("priest", "strength->attack_power"): ("per_point", 1),
    ("priest", "agility->crit"): ("points_per_unit", 20),
    ("priest", "agility->dodge"): ("points_per_unit", 20),
    ("priest", "agility->armor"): ("per_point", 2),
    ("priest", "intellect->spell_crit"): ("points_per_unit", 59.2),
    ("shaman", "strength->attack_power"): ("per_point", 2),
    ("shaman", "agility->crit"): ("points_per_unit", 20),
    ("shaman", "agility->dodge"): ("points_per_unit", 19.697),
    ("shaman", "agility->armor"): ("per_point", 2),
    ("shaman", "strength->block_value"): ("points_per_unit", 20),
    ("shaman", "intellect->spell_crit"): ("points_per_unit", 59.5),
    ("mage", "strength->attack_power"): ("per_point", 1),
    ("mage", "agility->armor"): ("per_point", 2),
    ("mage", "intellect->spell_crit"): ("points_per_unit", 59.5),
    ("warlock", "strength->attack_power"): ("per_point", 1),
    ("warlock", "agility->crit"): ("points_per_unit", 20),
    ("warlock", "agility->armor"): ("per_point", 2),
    ("warlock", "intellect->spell_crit"): ("points_per_unit", 60.6),
    ("druid", "strength->attack_power"): ("per_point", 2),
    ("druid", "agility->attack_power"): ("per_point", 1),
    ("druid", "agility->crit"): ("points_per_unit", 20),
    ("druid", "agility->dodge"): ("points_per_unit", 20),
    ("druid", "agility->armor"): ("per_point", 2),
    ("druid", "intellect->spell_crit"): ("points_per_unit", 60),
}


def context(profile: Any = FURY, **changes: Any) -> CharacterContext:
    data: dict[str, Any] = {
        "ruleset": "classic_era",
        "phase": 6,
        "level": 60,
        "class_name": ClassName.WARRIOR,
        "role": profile.role,
        "profile_id": profile.id,
        "content_mode": ContentMode.RAID,
    }
    data.update(changes)
    return CharacterContext(**data)


def ring(name: str, **stats: float) -> Item:
    return Item(
        id=f"custom:{name.lower().replace(' ', '-')}",
        name=name,
        ruleset="classic_era",
        slot=ItemSlot.FINGER,
        stats={Stat(stat): value for stat, value in stats.items()},
        provenance=FIXTURE,
    )


class TestConversionRates:
    @pytest.mark.parametrize(("key", "expected"), sorted(RATES.items()))
    def test_each_rate_is_the_cited_value(
        self, key: tuple[str, str], expected: tuple[str, float]
    ) -> None:
        class_name, name = key
        conversion = RULESET.conversion(ClassName(class_name), name)
        assert conversion is not None
        kind, rate = expected
        assert getattr(conversion, kind) == pytest.approx(rate)

    def test_no_rate_is_missing_from_this_table(self) -> None:
        listed = {
            (class_name.value, name)
            for class_name, rates in RULESET.conversions.by_class.items()
            for name in rates
        }
        assert listed == set(RATES)

    def test_conversions_apply_per_point_and_per_unit(self) -> None:
        rules = [
            DerivedStatRule(source=Stat.STRENGTH, target=Stat.ATTACK_POWER),
            DerivedStatRule(source=Stat.AGILITY, target=Stat.CRIT),
        ]
        amounts = {Stat.STRENGTH: 18.0, Stat.AGILITY: 29.0}
        warrior = {d.target: d.amount for d in derive(amounts, rules, RULESET, ClassName.WARRIOR)}
        rogue = {d.target: d.amount for d in derive(amounts, rules, RULESET, ClassName.ROGUE)}
        assert warrior == {Stat.ATTACK_POWER: 36.0, Stat.CRIT: pytest.approx(1.45)}
        assert rogue == {Stat.ATTACK_POWER: 18.0, Stat.CRIT: pytest.approx(1.0)}
        assert derive({}, rules, RULESET, ClassName.WARRIOR) == []


class TestFixedCapsAndOpenSoftCaps:
    def test_a_fixed_cap_less_what_the_build_provides(self) -> None:
        evaluated = resolve_cap(CapReference(fixed=8, reduced_by=2), RULESET, context())
        assert (evaluated.cap, evaluated.dead_zone) == (6.0, 0.0)
        assert evaluated.derivation == "fixed at 8; 2 already provided by the build"
        assert resolve_cap(CapReference(fixed=2, reduced_by=3), RULESET, context()).cap == 0.0

    def test_a_fixed_hard_cap_in_a_score(self) -> None:
        profile = FURY.model_copy(
            update={
                "soft_caps": (),
                "hard_caps": (HardCap(stat=Stat.HIT, cap=CapReference(fixed=5)),),
            }
        )
        result = score_item(
            ring("Hit Ring", hit=3), context(current_stats={Stat.HIT: 4}), profile, RULESET
        )
        assert result.score == pytest.approx(10.0)  # 4% to the 5% cap at 10; the rest wasted
        assert "fixed at 5" in result.capped_stats[0].message

    def test_a_soft_cap_without_an_end_keeps_counting_at_its_multiplier(self) -> None:
        soft = FURY.soft_caps[0].model_copy(update={"ends_at": None})
        profile = FURY.model_copy(update={"soft_caps": (soft,)})
        result = score_item(
            ring("Huge Hit Ring", hit=40), context(current_stats={}), profile, RULESET
        )
        # 1% suppressed; 1% to 9% at 10 = 80; 9% to 40% at half, 5 a point = 155.
        assert result.score == pytest.approx(235.0)


class TestBreakpoints:
    def score(self, current_defense: float, item_defense: float) -> Any:
        item = ring("Defense Ring", defense=item_defense)
        ctx = context(TANK, current_stats={Stat.DEFENSE: current_defense})
        return score_item(item, ctx, TANK, RULESET)

    def test_reaching_exactly_the_breakpoint_counts(self) -> None:
        result = self.score(135, 5)
        assert result.score == pytest.approx(5 + 50)  # 5 defense at 1, and the 50 bonus
        assert result.threshold_events[0].reached

    def test_just_short_of_it_does_not(self) -> None:
        result = self.score(134, 5)
        assert result.score == pytest.approx(5)
        assert result.threshold_events[0].message.startswith("1 short of Crit immunity")

    def test_already_reached_adds_no_bonus(self) -> None:
        result = self.score(150, 5)
        assert result.score == pytest.approx(5)
        event = result.threshold_events[0]
        assert event.reached and event.bonus == 0.0
        assert event.message.startswith("Crit immunity is already reached with current gear")

    def test_dropping_below_it_takes_the_bonus_away(self) -> None:
        result = self.score(142, -5)
        assert result.score == pytest.approx(-5 - 50)
        event = result.threshold_events[0]
        assert not event.reached and event.bonus == -50.0
        assert event.message.startswith("Drops below Crit immunity")


class TestCurveSegments:
    def test_below_zero_with_a_dead_zone_counts_as_dead(self) -> None:
        curve = ValueCurve(dead_zone=1, full_until=9)
        pieces = curve.segments(-2, 3)
        assert curve.counted(-2, 3) == 0.0
        assert (pieces.dead, pieces.full, pieces.soft, pieces.beyond) == (3.0, 0.0, 0.0, 0.0)

    def test_below_zero_without_a_dead_zone_counts_in_full(self) -> None:
        curve = ValueCurve(full_until=9)
        pieces = curve.segments(-2, 3)
        assert curve.counted(-2, 3) == 3.0
        assert (pieces.dead, pieces.full) == (0.0, 3.0)

    def test_the_segments_add_up_to_the_amount(self) -> None:
        curve = ValueCurve(dead_zone=1, full_until=9, soft_multiplier=0.5, soft_until=28)
        for before, amount in ((-3, 40), (0, 0.5), (8, 25), (30, -35)):
            pieces = curve.segments(before, amount)
            total = pieces.dead + pieces.full + pieces.soft + pieces.beyond
            assert total == pytest.approx(amount)
            counted = pieces.full + pieces.soft * curve.soft_multiplier
            assert counted == pytest.approx(curve.counted(before, amount))
            assert not math.isnan(total)
