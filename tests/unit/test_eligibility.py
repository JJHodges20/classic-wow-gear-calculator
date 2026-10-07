"""Weapon and armor eligibility rules, from the ruleset's class definitions."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from wow_gear.models.character import CharacterContext
from wow_gear.models.enums import (
    ArmorType,
    ClassName,
    ContentMode,
    ItemSlot,
    Race,
    RelicType,
    Role,
    WeaponType,
)
from wow_gear.models.item import Item, Provenance, WeaponStats
from wow_gear.rulesets.eligibility import eligibility
from wow_gear.rulesets.loader import load_ruleset

RULESET = load_ruleset(Path(__file__).resolve().parents[2] / "configs/rulesets/classic_era.yaml")
FIXTURE = Provenance(provider="fixture", source="Test fixture", data_version="test-1", custom=True)
SWORD = WeaponStats(min_damage=50, max_damage=100, speed=2.0)


def context(class_name: ClassName, level: int = 60, **changes: Any) -> CharacterContext:
    data: dict[str, Any] = {
        "ruleset": "classic_era",
        "phase": 6,
        "level": level,
        "class_name": class_name,
        "role": Role.MELEE_DPS,
        "profile_id": "x",
        "content_mode": ContentMode.RAID,
    }
    data.update(changes)
    return CharacterContext(**data)


def item(**changes: Any) -> Item:
    data: dict[str, Any] = {
        "id": "custom:thing",
        "name": "Thing",
        "ruleset": "classic_era",
        "slot": ItemSlot.CHEST,
        "provenance": FIXTURE,
    }
    data.update(changes)
    return Item(**data)


def reasons(target: Item, who: CharacterContext) -> tuple[str, ...]:
    return eligibility(target, who, RULESET).reasons


class TestArmor:
    def test_plate_from_level_40_for_warriors(self) -> None:
        plate = item(armor_type=ArmorType.PLATE)
        assert reasons(plate, context(ClassName.WARRIOR)) == ()
        assert reasons(plate, context(ClassName.WARRIOR, level=39)) == (
            "Warriors wear plate armor from level 40",
        )

    def test_mail_from_level_40_for_hunters(self) -> None:
        mail = item(armor_type=ArmorType.MAIL)
        assert eligibility(mail, context(ClassName.HUNTER), RULESET).eligible
        assert not eligibility(mail, context(ClassName.HUNTER, level=30), RULESET).eligible

    @pytest.mark.parametrize("class_name", [ClassName.MAGE, ClassName.PRIEST, ClassName.WARLOCK])
    def test_casters_wear_cloth_only(self, class_name: ClassName) -> None:
        assert reasons(item(armor_type=ArmorType.LEATHER), context(class_name))
        assert not reasons(item(armor_type=ArmorType.CLOTH), context(class_name))

    def test_rogues_never_wear_mail(self) -> None:
        assert reasons(item(armor_type=ArmorType.MAIL), context(ClassName.ROGUE)) == (
            "Rogues cannot wear mail armor",
        )


class TestWeapons:
    def test_mages_cannot_use_maces(self) -> None:
        mace = item(slot=ItemSlot.ONE_HAND, weapon_type=WeaponType.MACE, weapon=SWORD)
        assert reasons(mace, context(ClassName.MAGE)) == ("Mages cannot use maces",)
        assert not reasons(mace, context(ClassName.PRIEST))

    def test_druids_cannot_use_polearms(self) -> None:
        polearm = item(slot=ItemSlot.TWO_HAND, weapon_type=WeaponType.POLEARM, weapon=SWORD)
        assert reasons(polearm, context(ClassName.DRUID)) == ("Druids cannot use polearms",)

    def test_only_casters_use_wands(self) -> None:
        wand = item(slot=ItemSlot.RANGED, weapon_type=WeaponType.WAND, weapon=SWORD)
        assert not reasons(wand, context(ClassName.WARLOCK))
        assert reasons(wand, context(ClassName.WARRIOR)) == ("Warriors cannot use wands",)

    def test_two_handed_swords_read_naturally(self) -> None:
        sword = item(slot=ItemSlot.TWO_HAND, weapon_type=WeaponType.TWO_HANDED_SWORD, weapon=SWORD)
        assert reasons(sword, context(ClassName.ROGUE)) == ("Rogues cannot use two-handed swords",)

    def test_off_hand_weapons_need_dual_wield(self) -> None:
        off_hand = item(slot=ItemSlot.OFF_HAND, weapon_type=WeaponType.SWORD, weapon=SWORD)
        assert not reasons(off_hand, context(ClassName.ROGUE, level=10))
        assert reasons(off_hand, context(ClassName.WARRIOR, level=19)) == (
            "Warriors dual wield from level 20",
        )
        assert "Shamans cannot dual wield" in reasons(
            item(slot=ItemSlot.OFF_HAND, weapon_type=WeaponType.AXE, weapon=SWORD),
            context(ClassName.SHAMAN),
        )


class TestOffHandItems:
    def test_shields(self) -> None:
        shield = item(slot=ItemSlot.SHIELD)
        assert not reasons(shield, context(ClassName.SHAMAN))
        assert reasons(shield, context(ClassName.DRUID)) == ("Druids cannot use shields",)

    def test_relics_belong_to_one_class(self) -> None:
        libram = item(slot=ItemSlot.RELIC, relic_type=RelicType.LIBRAM)
        assert not reasons(libram, context(ClassName.PALADIN))
        assert reasons(libram, context(ClassName.DRUID)) == ("A libram is not a Druid relic",)


class TestRestrictions:
    def test_required_level_and_phase(self) -> None:
        ring = item(slot=ItemSlot.FINGER, required_level=60, phase=3)
        found = reasons(ring, context(ClassName.MAGE, level=58, phase=2))
        assert found == (
            "Requires level 60; the character is 58",
            "Available from phase 3; phase 2 is selected",
        )

    def test_class_and_race_restrictions(self) -> None:
        token = item(allowed_classes=(ClassName.PRIEST, ClassName.MAGE))
        assert reasons(token, context(ClassName.WARLOCK)) == ("Restricted to Priest, Mage",)
        horde = item(allowed_races=(Race.ORC, Race.TROLL))
        assert reasons(horde, context(ClassName.ROGUE, race=Race.HUMAN)) == (
            "Restricted to Orc, Troll",
        )
        assert not reasons(horde, context(ClassName.ROGUE))  # race unknown: not ruled out

    def test_several_reasons_are_all_listed(self) -> None:
        plate = item(armor_type=ArmorType.PLATE, required_level=60)
        assert len(reasons(plate, context(ClassName.PRIEST, level=50))) == 2
