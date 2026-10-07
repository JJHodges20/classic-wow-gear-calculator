"""A whole set of gear: its value, each piece's worth, caps, weak pieces and replacements.

Items are constructed. The fixture Fury profile's round weights make every number checkable
by hand: 2 points per Strength, 20 per 1% crit, 10 per 1% hit from 1% (the first 1% is
suppressed against a level 63 boss without racial skill) to the 9% cap, and half that up to
28%. A Human with a sword has 305 skill: the cap is 6%, nothing suppressed, half value to 25%.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from wow_gear.comparison.gear import (
    analyse_gear,
    cap_status,
    check_gear,
    displaced,
    replacement,
    set_label,
    set_pieces,
)
from wow_gear.core import DataValidationError
from wow_gear.models.character import CharacterContext
from wow_gear.models.enums import (
    ClassName,
    ContentMode,
    EquipmentSlot,
    ItemSlot,
    Race,
    Stat,
    WeaponType,
)
from wow_gear.models.item import EffectTrigger, Item, ItemEffect, Provenance, WeaponStats
from wow_gear.models.profile import CapReference, HardCap
from wow_gear.profiles.loader import load_profile
from wow_gear.rulesets.loader import RulesetRegistry
from wow_gear.scoring.gear import evaluate_gear, gear_totals

ROOT = Path(__file__).resolve().parents[2]
RULESETS = RulesetRegistry.from_directory(ROOT / "configs" / "rulesets")
RULESET = RULESETS.get("classic_era")
FURY = load_profile(ROOT / "data/fixtures/profiles/warrior/fixture_warrior_fury.yaml", RULESETS)
TANK = load_profile(ROOT / "data/fixtures/profiles/warrior/fixture_warrior_tank.yaml", RULESETS)
FIXTURE = Provenance(provider="fixture", source="Test", data_version="t-1", custom=True)
S = EquipmentSlot


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


def piece(name: str, slot: ItemSlot = ItemSlot.FINGER, **changes: Any) -> Item:
    stats = {Stat(key): value for key, value in changes.pop("stats", {}).items()}
    data: dict[str, Any] = {
        "id": f"custom:{name.lower().replace(' ', '-')}",
        "name": name,
        "ruleset": "classic_era",
        "slot": slot,
        "stats": stats,
        "provenance": FIXTURE,
    }
    data.update(changes)
    return Item(**data)


def weapon(
    name: str,
    slot: ItemSlot = ItemSlot.ONE_HAND,
    kind: WeaponType = WeaponType.SWORD,
    **changes: Any,
) -> Item:
    return piece(
        name,
        slot,
        weapon_type=kind,
        weapon=WeaponStats(min_damage=50, max_damage=100, speed=2.5),
        **changes,
    )


def analyse(gear: dict[EquipmentSlot, Item], profile: Any = FURY, **changes: Any) -> Any:
    return analyse_gear(gear, context(profile, **changes), profile, RULESET)


def value_of(gear: dict[EquipmentSlot, Item], profile: Any = FURY, **changes: Any) -> float:
    return evaluate_gear(gear, context(profile, **changes), profile, RULESET).score


HELM = piece("Helm", ItemSlot.HEAD, stats={"strength": 10, "hit": 3})
RING = piece("Hit Ring", stats={"hit": 4})
BAND = piece("Crit Band", stats={"crit": 1})


class TestTheWholeGear:
    def test_totals_add_every_item_without_weapon_damage(self) -> None:
        gear = {S.HEAD: HELM, S.FINGER_1: RING, S.MAIN_HAND: weapon("Blade")}
        totals = gear_totals(gear.values(), context(), FURY, RULESET)
        assert totals == {Stat.HIT: 7.0, Stat.STRENGTH: 10.0}

    def test_the_value_counts_caps_once_for_the_whole_gear(self) -> None:
        # Hit 7: the first 1% is suppressed, 6% count at 10 = 60; Strength 20; crit 20.
        gear = {S.HEAD: HELM, S.FINGER_1: RING, S.FINGER_2: BAND}
        assert value_of(gear) == pytest.approx(100.0)

    def test_the_breakdown_adds_up_to_the_value(self) -> None:
        gear = {S.HEAD: HELM, S.FINGER_1: RING, S.FINGER_2: BAND}
        analysis = analyse(gear)
        assert sum(c.contribution for c in analysis.components) == pytest.approx(analysis.score)
        hit = next(c for c in analysis.components if c.stat == Stat.HIT)
        assert (hit.amount, hit.effective_amount) == (pytest.approx(7.0), pytest.approx(6.0))

    def test_a_piece_is_worth_what_the_gear_loses_without_it(self) -> None:
        gear = {
            S.HEAD: HELM,
            S.FINGER_1: RING,
            S.FINGER_2: BAND,
            S.MAIN_HAND: weapon("Blade"),
            S.HANDS: piece("Skill Gloves", ItemSlot.HANDS, stats={"sword_skill": 5}),
        }
        analysis = analyse(gear, race=Race.ORC)
        whole = value_of(gear, race=Race.ORC)
        for slot_value in analysis.slots:
            rest = {slot: item for slot, item in gear.items() if slot != slot_value.slot}
            expected = whole - value_of(rest, race=Race.ORC)
            assert slot_value.score == pytest.approx(expected), slot_value.item_name

    def test_hit_past_the_cap_makes_a_hit_ring_worth_less(self) -> None:
        # With the helm's 3% the ring's 4% is fully valued: 40. With 9% from elsewhere it
        # lands past the cap at half value: 20.
        alone = analyse({S.HEAD: HELM, S.FINGER_1: RING})
        capped = analyse(
            {S.HEAD: piece("Hit Helm", ItemSlot.HEAD, stats={"hit": 9}), S.FINGER_1: RING}
        )
        assert alone.slots[1].score == pytest.approx(40.0)
        assert capped.slots[1].score == pytest.approx(20.0)

    def test_empty_gear_is_worth_nothing_and_every_slot_is_empty(self) -> None:
        analysis = analyse({})
        assert analysis.score == 0
        assert analysis.empty == tuple(EquipmentSlot)
        assert analysis.notes[0].startswith("Empty: Head, Neck")

    def test_a_two_hander_leaves_the_off_hand_taken_not_empty(self) -> None:
        analysis = analyse(
            {S.MAIN_HAND: weapon("Greatsword", ItemSlot.TWO_HAND, WeaponType.TWO_HANDED_SWORD)}
        )
        assert S.OFF_HAND not in analysis.empty
        assert S.HEAD in analysis.empty

    def test_the_fingerprint_follows_the_inputs(self) -> None:
        gear = {S.HEAD: HELM}
        assert analyse(gear).fingerprint == analyse(gear).fingerprint
        assert analyse(gear).fingerprint != analyse({S.HEAD: HELM, S.FINGER_1: RING}).fingerprint
        assert analyse(gear).fingerprint != analyse(gear, race=Race.ORC).fingerprint


class TestCaps:
    def test_short_of_the_cap_says_what_reaching_it_is_worth(self) -> None:
        status = analyse({S.FINGER_1: piece("Ring", stats={"hit": 5})}).caps[0]
        assert (status.state, status.target, status.total) == ("short", 9.0, 5.0)
        assert status.worth == pytest.approx(40.0)  # 4% more at 10
        assert "4% short of the melee hit cap (9%)" in status.message
        assert status.message in analyse({S.FINGER_1: piece("Ring", stats={"hit": 5})}).under_served

    def test_hit_inside_the_suppressed_first_percent_is_pointed_out(self) -> None:
        status = analyse({S.FINGER_1: piece("Ring", stats={"hit": 0.5})}).caps[0]
        assert status.worth == pytest.approx(80.0)  # 1% to 9% at 10; the first 1% counts nothing
        assert "The first 1% counts for nothing on this target." in status.message

    def test_inside_the_soft_band_more_counts_at_its_multiplier(self) -> None:
        status = analyse({S.FINGER_1: piece("Ring", stats={"hit": 12})}).caps[0]
        assert status.state == "reached"
        assert "more counts at 50% of its value up to 28%" in status.message
        assert status.worth is None

    def test_past_the_end_of_the_soft_band_is_wasted(self) -> None:
        status = analyse({S.FINGER_1: piece("Ring", stats={"hit": 30})}).caps[0]
        assert status.state == "over"
        assert "2% past the dual-wield hit cap (28%) counts for nothing" in status.message

    def test_a_hard_cap_reached_exactly_and_passed(self) -> None:
        hard = FURY.model_copy(
            update={
                "soft_caps": (),
                "hard_caps": (HardCap(stat=Stat.HIT, cap=CapReference(ruleset_cap="melee_hit")),),
            }
        )
        exact = analyse({S.FINGER_1: piece("Ring", stats={"hit": 9})}, hard).caps[0]
        over = analyse({S.FINGER_1: piece("Ring", stats={"hit": 10})}, hard).caps[0]
        assert (exact.kind, exact.state) == ("hard cap", "reached")
        assert over.state == "over"
        assert "1% past the melee hit cap (9%) counts for nothing" in over.message

    def test_racial_weapon_skill_from_the_worn_weapon_moves_the_cap(self) -> None:
        gear = {S.MAIN_HAND: weapon("Blade"), S.FINGER_1: piece("Ring", stats={"hit": 5})}
        human = analyse(gear, race=Race.HUMAN).caps[0]
        orc = analyse(gear, race=Race.ORC).caps[0]
        assert (human.target, human.state) == (6.0, "short")
        assert orc.target == 9.0

    def test_a_breakpoint_short_and_reached(self) -> None:
        short = analyse({S.HEAD: piece("Helm", ItemSlot.HEAD, stats={"defense": 130})}, TANK)
        status = next(s for s in short.caps if s.kind == "breakpoint")
        assert (status.label, status.state, status.target) == ("Crit immunity", "short", 140.0)
        assert status.worth == pytest.approx(50.0 + 10.0)  # the bonus and 10 defense at 1
        reached = analyse({S.HEAD: piece("Helm", ItemSlot.HEAD, stats={"defense": 140})}, TANK)
        assert next(s for s in reached.caps if s.kind == "breakpoint").state == "reached"

    def test_cap_status_reads_the_evaluated_gear(self) -> None:
        evaluation = evaluate_gear({S.FINGER_1: RING}, context(), FURY, RULESET)
        assert [status.total for status in cap_status(evaluation, FURY, RULESET)] == [4.0]


class TestWhatTheGearLacksAndWastes:
    def test_stats_the_profile_does_not_value_are_listed(self) -> None:
        gear = {S.FINGER_1: piece("Ring", stats={"stamina": 12, "intellect": 5, "strength": 3})}
        assert analyse(gear).not_valued == ("Stamina 12", "Intellect 5")

    def test_weapon_skill_is_not_listed_for_a_profile_with_hit_caps(self) -> None:
        gear = {
            S.MAIN_HAND: weapon("Blade"),
            S.HANDS: piece("Gloves", ItemSlot.HANDS, stats={"sword_skill": 5}),
        }
        assert analyse(gear).not_valued == ()

    def test_a_piece_worth_nothing_is_among_the_weakest(self) -> None:
        gear = {S.FINGER_1: piece("Stamina Ring", stats={"stamina": 12}), S.FINGER_2: BAND}
        weakest = analyse(gear).weakest
        assert [(w.slot, w.reason) for w in weakest] == [
            (S.FINGER_1, "adds nothing under this profile")
        ]

    def test_a_piece_worth_nothing_but_its_proc_says_so(self) -> None:
        proc = ItemEffect(trigger=EffectTrigger.CHANCE_ON_HIT, description="Chance on hit: Zap.")
        gear = {S.TRINKET_1: piece("Zapper", ItemSlot.TRINKET, equip_effects=[proc])}
        analysis = analyse(gear)
        assert "proc or on-use effect is not valued" in analysis.weakest[0].reason
        assert analysis.not_scored == ("Zapper: Chance on hit: Zap.",)

    def test_a_piece_far_below_the_gear_s_item_level_is_among_the_weakest(self) -> None:
        gear = {
            slot: piece(f"Piece {index}", item_slot, stats={"strength": 5}, item_level=60)
            for index, (slot, item_slot) in enumerate(
                [
                    (S.HEAD, ItemSlot.HEAD),
                    (S.CHEST, ItemSlot.CHEST),
                    (S.LEGS, ItemSlot.LEGS),
                    (S.FEET, ItemSlot.FEET),
                ]
            )
        }
        gear[S.WRIST] = piece("Old Bracers", ItemSlot.WRIST, stats={"strength": 5}, item_level=45)
        weakest = analyse(gear).weakest
        assert [(w.slot, w.reason) for w in weakest] == [
            (S.WRIST, "item level 45, 15 below the median of this gear (60)")
        ]

    def test_an_unusable_piece_is_noted(self) -> None:
        robe = piece(
            "Robe", ItemSlot.CHEST, stats={"strength": 5}, allowed_classes=[ClassName.MAGE]
        )
        analysis = analyse({S.CHEST: robe})
        assert not analysis.slots[0].eligible
        assert any(note.startswith("Robe is not usable") for note in analysis.notes)


class TestSets:
    def test_a_set_is_named_from_its_pieces(self) -> None:
        assert set_label(["Helm of Wrath", "Pauldrons of Wrath"]) == "Wrath"
        assert set_label(["Devilsaur Gauntlets", "Devilsaur Leggings"]) == "Devilsaur"
        assert set_label(["Lonely Helm"]) is None
        assert set_label(["Alpha Helm", "Beta Boots"]) is None

    def test_only_sets_with_two_pieces_worn_are_listed(self) -> None:
        gloves = piece("Devilsaur Gauntlets", ItemSlot.HANDS, set_id="143")
        legs = piece("Devilsaur Leggings", ItemSlot.LEGS, set_id="143")
        chest = piece("Savage Gladiator Chain", ItemSlot.CHEST, set_id="1")
        sets = set_pieces([gloves, legs, chest])
        assert [(s.set_id, s.label, len(s.items)) for s in sets] == [("143", "Devilsaur", 2)]

    def test_set_bonuses_are_noted_once_not_per_piece(self) -> None:
        gloves = piece("Devilsaur Gauntlets", ItemSlot.HANDS, set_id="143")
        legs = piece("Devilsaur Leggings", ItemSlot.LEGS, set_id="143")
        analysis = analyse({S.HANDS: gloves, S.LEGS: legs})
        assert "Set bonuses are not scored in version 1: Devilsaur (2 pieces)." in analysis.notes
        assert analysis.not_scored == ()


class TestWearingTogether:
    def test_an_item_in_a_slot_it_does_not_fit_is_refused(self) -> None:
        with pytest.raises(DataValidationError, match="cannot be worn in the finger 1 slot"):
            check_gear({S.FINGER_1: HELM})

    def test_a_two_hander_with_an_off_hand_is_refused(self) -> None:
        gear = {
            S.MAIN_HAND: weapon("Greatsword", ItemSlot.TWO_HAND, WeaponType.TWO_HANDED_SWORD),
            S.OFF_HAND: weapon("Dirk", kind=WeaponType.DAGGER),
        }
        with pytest.raises(DataValidationError, match="the off hand must be empty"):
            check_gear(gear)

    def test_a_unique_item_is_worn_once(self) -> None:
        ring = piece("Unique Ring", unique=True)
        with pytest.raises(DataValidationError, match="unique"):
            check_gear({S.FINGER_1: ring, S.FINGER_2: ring})
        check_gear({S.FINGER_1: RING, S.FINGER_2: RING})  # not unique: two are fine

    def test_what_comes_off(self) -> None:
        pair = {S.MAIN_HAND: weapon("Blade"), S.OFF_HAND: weapon("Dirk", kind=WeaponType.DAGGER)}
        greatsword = weapon("Greatsword", ItemSlot.TWO_HAND, WeaponType.TWO_HANDED_SWORD)
        assert displaced(pair, S.MAIN_HAND, greatsword) == (S.MAIN_HAND, S.OFF_HAND)
        assert displaced({S.MAIN_HAND: greatsword}, S.OFF_HAND, weapon("Dirk")) == (S.MAIN_HAND,)
        assert displaced({}, S.HEAD, HELM) == ()


class TestReplacement:
    def test_the_change_is_the_whole_gear_with_it_less_without_it(self) -> None:
        gear = {S.HEAD: HELM, S.FINGER_1: RING, S.FINGER_2: BAND}
        candidate = piece("Better Band", stats={"crit": 2, "hit": 2})
        result = replacement(gear, S.FINGER_2, candidate, context(), FURY, RULESET)
        after = {**gear, S.FINGER_2: candidate}
        assert result.delta == pytest.approx(value_of(after) - value_of(gear))
        assert result.delta == pytest.approx(40.0)  # +1% crit (20) and +2% hit (20)
        assert sum(line.delta for line in result.lines) == pytest.approx(result.delta)
        assert result.removed == ("Crit Band",)
        assert result.after[Stat.HIT] == 9.0

    def test_hit_past_the_cap_counts_against_the_candidate(self) -> None:
        gear = {S.HEAD: piece("Hit Helm", ItemSlot.HEAD, stats={"hit": 8}), S.FINGER_1: BAND}
        candidate = piece("Hit Ring", stats={"hit": 3})
        result = replacement(gear, S.FINGER_1, candidate, context(), FURY, RULESET)
        # 8% -> 11%: 1% to the cap at 10, 2% past it at 5 each = 20; the crit band's 20 goes.
        assert result.delta == pytest.approx(0.0)
        hit = next(line for line in result.lines if line.stat == Stat.HIT)
        assert hit.note is not None and "counts" in hit.note

    def test_a_two_hander_replaces_both_weapons(self) -> None:
        gear = {S.MAIN_HAND: weapon("Blade"), S.OFF_HAND: weapon("Dirk", kind=WeaponType.DAGGER)}
        greatsword = weapon("Greatsword", ItemSlot.TWO_HAND, WeaponType.TWO_HANDED_SWORD)
        result = replacement(gear, S.MAIN_HAND, greatsword, context(), FURY, RULESET)
        assert result.removed == ("Blade", "Dirk")
        assert result.notes[0] == "Greatsword is a two-handed weapon: it replaces Blade and Dirk."
        assert result.delta == pytest.approx(value_of({S.MAIN_HAND: greatsword}) - value_of(gear))

    def test_an_off_hand_takes_a_two_hander_off(self) -> None:
        greatsword = weapon("Greatsword", ItemSlot.TWO_HAND, WeaponType.TWO_HANDED_SWORD)
        result = replacement(
            {S.MAIN_HAND: greatsword}, S.OFF_HAND, weapon("Dirk"), context(), FURY, RULESET
        )
        assert result.removed == ("Greatsword",)
        assert "the main hand is left empty" in result.notes[0]

    def test_a_weapon_of_another_type_moves_the_cap_and_says_so(self) -> None:
        gear = {S.MAIN_HAND: weapon("Blade"), S.FINGER_1: piece("Ring", stats={"hit": 6})}
        axe = weapon("Axe", ItemSlot.MAIN_HAND, WeaponType.AXE)
        result = replacement(gear, S.MAIN_HAND, axe, context(race=Race.HUMAN), FURY, RULESET)
        assert (result.caps_before[0].target, result.caps_after[0].target) == (6.0, 9.0)
        assert any("is 9% instead of 6%" in note for note in result.notes)
        # 6% hit was all valued at the 6% cap; at the axe's 9% cap the first 1% is suppressed.
        hit = next(line for line in result.lines if line.stat == Stat.HIT)
        assert hit.delta == pytest.approx(-10.0)

    def test_an_empty_slot_takes_nothing_off(self) -> None:
        result = replacement({}, S.FINGER_1, RING, context(), FURY, RULESET)
        assert result.removed == ()
        assert result.delta == pytest.approx(30.0)  # 4% hit, the first 1% suppressed
        assert "nothing comes off" in result.notes[0]

    def test_an_unusable_candidate_is_flagged(self) -> None:
        robe = piece(
            "Robe", ItemSlot.CHEST, stats={"strength": 5}, allowed_classes=[ClassName.MAGE]
        )
        result = replacement({}, S.CHEST, robe, context(), FURY, RULESET)
        assert not result.eligible
        assert any(note.startswith("Robe is not usable") for note in result.notes)

    def test_a_candidate_that_does_not_fit_or_is_worn_twice_is_refused(self) -> None:
        with pytest.raises(DataValidationError, match="cannot be worn"):
            replacement({}, S.FINGER_1, HELM, context(), FURY, RULESET)
        ring = piece("Unique Ring", unique=True)
        with pytest.raises(DataValidationError, match="unique"):
            replacement({S.FINGER_2: ring}, S.FINGER_1, ring, context(), FURY, RULESET)
