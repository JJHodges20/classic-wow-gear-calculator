"""Comparing items: ranking, outcomes, the explanation, slot footprints and replacement.

Items are constructed; the fixture Fury profile's round weights make every number checkable
by hand: 1 point per attack power, 2 attack power per Strength, 20 per 1% crit, 10 per 1% hit
up to the 9% cap (the first 1% suppressed) and half that up to 28%.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from wow_gear.comparison.compare import (
    compare_items,
    explain,
    footprint_note,
    is_tie,
    unit_abbreviation,
)
from wow_gear.core import DataValidationError
from wow_gear.models.character import CharacterContext
from wow_gear.models.enums import ClassName, ContentMode, ItemSlot, Role, Stat, WeaponType
from wow_gear.models.item import EffectTrigger, Item, ItemEffect, Provenance, WeaponStats
from wow_gear.profiles.loader import load_profile
from wow_gear.rulesets.loader import RulesetRegistry
from wow_gear.scoring.engine import score_item

ROOT = Path(__file__).resolve().parents[2]
RULESETS = RulesetRegistry.from_directory(ROOT / "configs" / "rulesets")
RULESET = RULESETS.get("classic_era")
FURY = load_profile(ROOT / "data/fixtures/profiles/warrior/fixture_warrior_fury.yaml", RULESETS)
FIXTURE = Provenance(provider="fixture", source="Test", data_version="t-1", custom=True)


def context(hit: float | None = 5, **changes: Any) -> CharacterContext:
    data: dict[str, Any] = {
        "ruleset": "classic_era",
        "phase": 6,
        "level": 60,
        "class_name": ClassName.WARRIOR,
        "role": Role.MELEE_DPS,
        "profile_id": FURY.id,
        "content_mode": ContentMode.RAID,
        "current_stats": None if hit is None else {Stat.HIT: hit},
    }
    data.update(changes)
    return CharacterContext(**data)


def ring(name: str, **stats: float) -> Item:
    return item(name, stats={Stat(stat): value for stat, value in stats.items()})


def item(name: str, **changes: Any) -> Item:
    data: dict[str, Any] = {
        "id": f"custom:{name.lower().replace(' ', '-')}",
        "name": name,
        "ruleset": "classic_era",
        "slot": ItemSlot.FINGER,
        "provenance": FIXTURE,
    }
    data.update(changes)
    return Item(**data)


def weapon(name: str, slot: ItemSlot) -> Item:
    weapon_type = WeaponType.TWO_HANDED_SWORD if slot == ItemSlot.TWO_HAND else WeaponType.SWORD
    return item(
        name,
        slot=slot,
        weapon_type=weapon_type,
        weapon=WeaponStats(min_damage=50, max_damage=100, speed=2.5),
    )


def compare(items: list[Item], **kwargs: Any) -> Any:
    ctx = kwargs.pop("ctx", None) or context()
    return compare_items(items, ctx, FURY, RULESET, **kwargs)


class TestRanking:
    def test_usable_items_rank_first_then_by_score(self) -> None:
        strong = ring("Strong", strength=10)  # 20 points
        weak = ring("Weak", strength=5)  # 10
        mages = item("Mage Ring", stats={Stat.STRENGTH: 20}, allowed_classes=[ClassName.MAGE])
        result = compare([mages, weak, strong])
        assert [r.item_name for r in result.results] == ["Strong", "Weak", "Mage Ring"]
        assert [r.rank for r in result.results] == [1, 2, 3]
        assert [r.recommendation_label for r in result.results] == [
            "Recommended under this profile",
            "-10.0 fixture points",
            "Not usable",
        ]
        assert result.outcome == "winner"
        assert (result.winner_id, result.first_id, result.second_id) == (
            strong.id,
            strong.id,
            weak.id,
        )
        assert result.score_delta == pytest.approx(10.0)
        assert "Mage Ring is not usable: Restricted to Mage." in result.notes

    def test_equal_scores_are_a_tie_without_a_winner(self) -> None:
        result = compare([ring("Strength", strength=10), ring("Crit", crit=1)])
        assert result.outcome == "tie"
        assert result.winner_id is None
        assert {r.recommendation_label for r in result.results} == {"Effectively tied"}
        assert "effectively equal" in result.headline

    @pytest.mark.parametrize(
        ("first", "second", "tied"),
        [(100, 100.4, True), (100, 100.6, False), (0, 0.04, True), (0, 0.06, False)],
    )
    def test_the_tie_margin(self, first: float, second: float, tied: bool) -> None:
        assert is_tie(first, second) is tied

    def test_the_only_usable_item_is_recommended_and_measured_against_the_best_other(
        self,
    ) -> None:
        usable = ring("Usable", strength=10)  # 20
        better = item("Better", stats={Stat.STRENGTH: 50}, allowed_classes=[ClassName.MAGE])
        result = compare([better, usable])
        assert result.outcome == "only_usable"
        assert result.winner_id == usable.id
        assert result.score_delta == pytest.approx(20.0 - 100.0)
        assert "only usable choice" in result.headline

    def test_nothing_usable(self) -> None:
        mage_only = {"allowed_classes": [ClassName.MAGE], "stats": {Stat.STRENGTH: 5}}
        result = compare([item("One", **mage_only), item("Two", **mage_only)])
        assert result.outcome == "none_usable"
        assert result.winner_id is None and result.lines == ()
        assert result.headline == "None of these items is usable by this character."

    def test_a_single_item_is_scored(self) -> None:
        result = compare([ring("Alone", strength=10, stamina=7)])
        assert result.outcome == "single"
        assert result.results[0].recommendation_label == "Scored"
        assert result.headline == "Alone scores 20.0 fixture points for Fixture Fury."
        assert result.not_valued == ("Stamina",)

    def test_bad_input_is_refused(self) -> None:
        with pytest.raises(DataValidationError, match="nothing"):
            compare([])
        twice = ring("Twice", strength=1)
        with pytest.raises(DataValidationError, match="twice"):
            compare([twice, twice])


class TestExplanation:
    def test_the_lines_add_up_to_the_score_delta(self) -> None:
        first = ring("First", strength=10, crit=1)  # 20 + 20 = 40
        second = ring("Second", hit=2)  # 5% to 7%: 20
        result = compare([first, second])
        deltas = {line.key: line.delta for line in result.lines}
        assert deltas == pytest.approx(
            {"derived:strength->attack_power": 20.0, "stat:crit": 20.0, "stat:hit": -20.0}
        )
        assert sum(deltas.values()) == pytest.approx(result.score_delta)
        assert [line.key for line in result.lines] == [
            "stat:crit",
            "stat:hit",
            "derived:strength->attack_power",
        ]  # equal sizes in label order: Crit, Hit, Strength into attack power
        assert result.why == (
            "+20.0 from crit, -20.0 from hit and +20.0 from strength into attack power"
        )

    def test_a_stat_wasted_past_the_cap_is_part_of_the_answer(self) -> None:
        result = compare([ring("Crit", crit=1), ring("Hit", hit=2)], ctx=context(hit=28))
        hit = next(line for line in result.lines if line.key == "stat:hit")
        assert hit.delta == 0 and hit.second_amount == 2
        assert hit.text == "0 from hit (Hit: none of its 2 counts)"
        assert result.why == "+20.0 from crit and 0 from hit (Hit: none of its 2 counts)"

    def test_part_of_a_stat_past_the_cap(self) -> None:
        result = compare([ring("Crit", crit=1), ring("Hit", hit=2)], ctx=context(hit=9))
        hit = next(line for line in result.lines if line.key == "stat:hit")
        assert hit.second_value == pytest.approx(10.0)  # 2% past the cap at half value
        assert hit.note == "Hit: 1 of its 2 counts"

    def test_unvalued_stats_and_unscored_effects_are_listed_not_explained(self) -> None:
        proc = ItemEffect(trigger=EffectTrigger.CHANCE_ON_HIT, description="Chance on hit: Zap.")
        first = item("Zapper", stats={Stat.STRENGTH: 10, Stat.STAMINA: 9}, equip_effects=[proc])
        second = ring("Plain", strength=5, armor=40)
        result = compare([first, second])
        assert {line.key for line in result.lines} == {"derived:strength->attack_power"}
        assert set(result.not_valued) == {"Stamina", "Armor"}
        assert result.not_scored == ("Zapper: Chance on hit: Zap.",)
        assert result.confidence.level == "low"  # an experimental profile, an unscored effect

    def test_explain_compares_any_two_results(self) -> None:
        a = score_item(ring("A", crit=2), context(), FURY, RULESET)
        b = score_item(ring("B", crit=1), context(), FURY, RULESET)
        lines, not_valued, not_scored = explain(a, b)
        assert [(line.key, line.delta) for line in lines] == [("stat:crit", 20.0)]
        assert lines[0].text == "+20.0 from crit"
        assert not_valued == () and not_scored == ()


class TestFootprints:
    def test_a_two_hander_against_a_one_hander(self) -> None:
        note = footprint_note(
            [weapon("Big", ItemSlot.TWO_HAND), weapon("Small", ItemSlot.ONE_HAND)]
        )
        assert note is not None and "Big is a two-handed weapon" in note

    def test_items_for_different_slots(self) -> None:
        note = footprint_note(
            [item("Hat", slot=ItemSlot.HEAD), item("Gloves", slot=ItemSlot.HANDS)]
        )
        assert note is not None and "different slots (Hands, Head)" in note

    def test_the_equipped_item_counts(self) -> None:
        assert footprint_note([ring("A")], replacing=item("Hat", slot=ItemSlot.HEAD)) is not None

    @pytest.mark.parametrize(
        ("first", "second"),
        [
            (ItemSlot.ONE_HAND, ItemSlot.OFF_HAND),
            (ItemSlot.ONE_HAND, ItemSlot.MAIN_HAND),
            (ItemSlot.SHIELD, ItemSlot.HELD_IN_OFF_HAND),
            (ItemSlot.FINGER, ItemSlot.FINGER),
        ],
    )
    def test_alternatives_for_one_slot(self, first: ItemSlot, second: ItemSlot) -> None:
        assert footprint_note([item("A", slot=first), item("B", slot=second)]) is None


class TestReplacing:
    def test_upgrades_are_measured_from_the_gear_without_the_equipped_item(self) -> None:
        equipped = ring("Equipped", hit=2)  # current 8% includes it: from 6% it is worth 20
        more_hit = ring("More Hit", hit=3)  # 6% to 9%: 30
        crit = ring("Crit", crit=1)  # 20
        result = compare([more_hit, crit], ctx=context(hit=8), replacing=equipped)
        assert result.replaced is not None
        assert result.replaced.score == pytest.approx(20.0)
        assert {u.item_name: u.delta for u in result.upgrades} == pytest.approx(
            {"More Hit": 10.0, "Crit": 0.0}
        )


class TestReproducibility:
    def test_the_same_comparison_gives_the_same_result_in_any_order(self) -> None:
        a, b = ring("A", strength=10, hit=1), ring("B", crit=1)
        first = compare([a, b])
        assert compare([a, b]) == first
        reversed_order = compare([b, a])
        assert [r.item_id for r in reversed_order.results] == [r.item_id for r in first.results]
        assert reversed_order.fingerprint == first.fingerprint

    def test_the_fingerprint_follows_the_context(self) -> None:
        a, b = ring("A", strength=10, hit=1), ring("B", crit=1)
        assert compare([a, b]).fingerprint != compare([a, b], ctx=context(hit=7)).fingerprint


def test_unit_abbreviation() -> None:
    assert unit_abbreviation("attack power equivalents (AP)") == "AP"
    assert unit_abbreviation("tank points (TP)") == "TP"
    assert unit_abbreviation("fixture points") == "fixture points"
