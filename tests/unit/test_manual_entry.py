"""Manual entry: forms into items, pasted tooltips into forms, and validation against the ruleset."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError

from wow_gear.models.enums import (
    ArmorType,
    CreatureType,
    ItemSlot,
    Stat,
    WeaponType,
)
from wow_gear.models.forms import EffectRow, ManualItemForm
from wow_gear.models.item import EffectTrigger
from wow_gear.processing.manual import form_to_item, read_tooltip
from wow_gear.processing.validation import validate_item
from wow_gear.rulesets.loader import load_ruleset

RULESET = load_ruleset(Path(__file__).resolve().parents[2] / "configs/rulesets/classic_era.yaml")


def form(**changes: Any) -> ManualItemForm:
    data: dict[str, Any] = {
        "name": "Test Helm",
        "slot": ItemSlot.HEAD,
        "armor_type": ArmorType.PLATE,
        "required_level": 60,
        "stats": {Stat.STRENGTH: 20, Stat.STAMINA: 15},
    }
    data.update(changes)
    return ManualItemForm(**data)


class TestFormToItem:
    def test_a_simple_item(self) -> None:
        item = form_to_item(form(), "classic_era")
        assert item.id.startswith("custom:test-helm-")
        assert item.stats == {Stat.STAMINA: 15, Stat.STRENGTH: 20}
        assert item.provenance.provider == "manual" and item.is_custom

    def test_the_same_form_gives_the_same_id(self) -> None:
        assert form_to_item(form(), "classic_era").id == form_to_item(form(), "classic_era").id
        assert (
            form_to_item(form(), "classic_era").id
            != form_to_item(form(stats={Stat.STRENGTH: 21}), "classic_era").id
        )

    def test_stat_effect_rows_fold_into_stats(self) -> None:
        rows = (EffectRow(kind="stat", stat=Stat.HIT, value=1),)
        item = form_to_item(form(effects=rows), "classic_era")
        assert item.stats[Stat.HIT] == 1 and item.equip_effects == ()

    def test_conditional_and_text_rows_stay_effects(self) -> None:
        rows = (
            EffectRow(
                kind="conditional_stat",
                stat=Stat.ATTACK_POWER,
                value=81,
                target_creature_types=(CreatureType.UNDEAD,),
            ),
            EffectRow(kind="text", trigger=EffectTrigger.USE, text="Use: Something powerful."),
        )
        item = form_to_item(
            form(slot=ItemSlot.TRINKET, armor_type=None, effects=rows), "classic_era"
        )
        assert item.equip_effects[0].condition is not None
        assert item.on_use_effects[0].description == "Use: Something powerful."

    def test_a_weapon_needs_all_three_damage_fields(self) -> None:
        sword = form(
            name="Test Sword",
            slot=ItemSlot.ONE_HAND,
            armor_type=None,
            weapon_type=WeaponType.SWORD,
            min_damage=50,
            max_damage=100,
            speed=2.0,
        )
        item = form_to_item(sword, "classic_era")
        assert item.weapon is not None and item.weapon.dps == pytest.approx(37.5)
        no_speed = form_to_item(sword.model_copy(update={"speed": None}), "classic_era")
        assert no_speed.weapon is None

    def test_incomplete_rows_are_rejected(self) -> None:
        with pytest.raises(ValidationError, match="stat and a value"):
            EffectRow(kind="stat", stat=Stat.HIT)
        with pytest.raises(ValidationError, match="creature type"):
            EffectRow(kind="conditional_stat", stat=Stat.ATTACK_POWER, value=5)
        with pytest.raises(ValidationError, match="name"):
            form(name="   ")


class TestValidation:
    def codes(self, **changes: Any) -> set[str]:
        item = form_to_item(form(**changes), "classic_era")
        return {issue.code for issue in validate_item(item, RULESET).issues}

    def test_a_normal_item_is_clean(self) -> None:
        report = validate_item(form_to_item(form(), "classic_era"), RULESET)
        assert report.ok and not report.warnings
        assert report.usable(custom=False)

    def test_plate_below_level_40_is_implausible(self) -> None:
        assert "armor_level" in self.codes(required_level=30)

    def test_a_sword_is_not_two_handed(self) -> None:
        codes = self.codes(
            slot=ItemSlot.TWO_HAND,
            armor_type=None,
            weapon_type=WeaponType.SWORD,
            min_damage=1,
            max_damage=2,
            speed=3.0,
        )
        assert "slot_type" in codes

    def test_odd_weapon_speed_and_missing_damage(self) -> None:
        fast = self.codes(
            slot=ItemSlot.ONE_HAND,
            armor_type=None,
            weapon_type=WeaponType.DAGGER,
            min_damage=1,
            max_damage=2,
            speed=0.5,
        )
        assert "weapon_speed" in fast
        bare = self.codes(slot=ItemSlot.ONE_HAND, armor_type=None, weapon_type=WeaponType.DAGGER)
        assert "weapon_damage_missing" in bare

    def test_a_large_percentage_is_double_checked(self) -> None:
        assert "large_percent" in self.codes(stats={Stat.HIT: 10})

    def test_negative_stats_are_flagged(self) -> None:
        assert "negative_stat" in self.codes(stats={Stat.SPIRIT: -10})

    def test_errors_block_and_warnings_block_only_game_items(self) -> None:
        item = form_to_item(form(phase=9), "classic_era")
        report = validate_item(item, RULESET)
        assert not report.ok and "phase" in {i.code for i in report.errors}
        odd = validate_item(form_to_item(form(required_level=30), "classic_era"), RULESET)
        assert odd.ok and odd.usable(custom=True) and not odd.usable(custom=False)

    def test_an_empty_item(self) -> None:
        assert "empty" in self.codes(stats={}, slot=ItemSlot.FINGER, armor_type=None)


class TestPastedTooltips:
    HELM = """Lionheart Helm
Binds when equipped
Head  Plate
565 Armor
+18 Strength
Durability 100 / 100
Requires Level 56
Equip: Improves your chance to get a critical strike by 2%.
Equip: Improves your chance to hit by 2%."""

    def test_a_plate_helm(self) -> None:
        reading = read_tooltip(self.HELM)
        assert reading.form is not None and not reading.unrecognized
        item = form_to_item(reading.form, "classic_era")
        assert (item.name, item.slot, item.armor_type, item.required_level) == (
            "Lionheart Helm",
            ItemSlot.HEAD,
            ArmorType.PLATE,
            56,
        )
        assert item.stats == {Stat.ARMOR: 565, Stat.CRIT: 2, Stat.HIT: 2, Stat.STRENGTH: 18}
        assert not item.is_custom

    def test_a_two_handed_weapon(self) -> None:
        tooltip = """Some Greatsword
Two-Hand  Sword
150 - 220 Damage  Speed 3.40
(54.4 damage per second)
+20 Strength
Chance on hit: Does something."""
        reading = read_tooltip(tooltip)
        assert reading.form is not None
        item = form_to_item(reading.form, "classic_era")
        assert item.weapon_type == WeaponType.TWO_HANDED_SWORD
        assert item.weapon is not None and item.weapon.speed == 3.4
        assert item.equip_effects[0].trigger == EffectTrigger.CHANCE_ON_HIT

    def test_a_shield(self) -> None:
        reading = read_tooltip("Test Shield\nOff Hand  Shield\n2893 Armor\n73 Block\n+23 Stamina")
        assert reading.form is not None and reading.form.slot == ItemSlot.SHIELD
        assert reading.form.stats[Stat.BLOCK_VALUE] == 73

    def test_lines_it_cannot_place_are_listed(self) -> None:
        reading = read_tooltip("Odd Ring\nFinger\n+5 Stamina\nGlows faintly.")
        assert reading.unrecognized == ["Glows faintly."]

    def test_without_a_slot_line_the_player_chooses(self) -> None:
        reading = read_tooltip("Mystery Item\n+5 Stamina")
        assert reading.form is None and reading.problems

    def test_an_empty_paste(self) -> None:
        assert read_tooltip("   ").problems == ["The tooltip is empty."]


class TestTooltipsThatMakeNoItem:
    def test_a_name_too_long_is_a_problem_not_a_crash(self) -> None:
        text = "A" * 130 + chr(10) + "Head" + chr(9) + "Plate" + chr(10) + "+5 Strength"
        reading = read_tooltip(text)
        assert reading.form is None
        assert reading.problems[0].startswith("The tooltip does not make a valid item: name")

    def test_a_weapon_with_no_speed_is_a_problem_not_a_crash(self) -> None:
        lines = [
            "Broken Blade",
            "One-Hand" + chr(9) + "Sword",
            "10 - 20 Damage" + chr(9) + "Speed 0.00",
        ]
        reading = read_tooltip(chr(10).join(lines))
        assert reading.form is None
        assert any("speed" in problem for problem in reading.problems)
