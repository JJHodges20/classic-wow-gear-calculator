"""Manual entry through the service: choices by slot, preview with validation, and the same
scoring path as a looked-up item."""

from __future__ import annotations

from pathlib import Path

from wow_gear.models.character import CharacterContext
from wow_gear.models.enums import ArmorType, ItemSlot, RelicType, Stat, WeaponType
from wow_gear.models.forms import ManualItemForm
from wow_gear.profiles.loader import ProfileRegistry
from wow_gear.rulesets.loader import RulesetRegistry
from wow_gear.scoring.engine import score_item
from wow_gear.services.item_entry import ItemEntryService

ROOT = Path(__file__).resolve().parents[2]
RULESETS = RulesetRegistry.from_directory(ROOT / "configs" / "rulesets")
RULESET = RULESETS.get("classic_era")
PROFILES = ProfileRegistry.from_directory(ROOT / "configs" / "profiles", RULESETS)
SERVICE = ItemEntryService(RULESET)


class TestChoices:
    def test_armor_slots_offer_armor_types(self) -> None:
        assert SERVICE.type_choices(ItemSlot.CHEST).armor_types == tuple(ArmorType)
        assert SERVICE.type_choices(ItemSlot.BACK).armor_types == (ArmorType.CLOTH,)

    def test_weapon_slots_offer_their_weapon_types(self) -> None:
        two_hand = SERVICE.type_choices(ItemSlot.TWO_HAND)
        assert two_hand.has_weapon_block and WeaponType.POLEARM in two_hand.weapon_types
        assert WeaponType.SWORD not in two_hand.weapon_types
        ranged = SERVICE.type_choices(ItemSlot.RANGED)
        assert set(ranged.weapon_types) == {
            WeaponType.BOW,
            WeaponType.GUN,
            WeaponType.CROSSBOW,
            WeaponType.THROWN,
            WeaponType.WAND,
        }
        assert WeaponType.DAGGER in SERVICE.type_choices(ItemSlot.ONE_HAND).weapon_types

    def test_jewelry_has_no_type_and_relics_their_own(self) -> None:
        ring = SERVICE.type_choices(ItemSlot.FINGER)
        assert not (ring.armor_types or ring.weapon_types or ring.has_weapon_block)
        assert SERVICE.type_choices(ItemSlot.RELIC).relic_types == tuple(RelicType)

    def test_stat_fields_follow_the_slot(self) -> None:
        shield_groups = [group.key for group in SERVICE.stat_groups(ItemSlot.SHIELD)]
        assert shield_groups[0] == "defense"
        all_stats = {f.stat for group in SERVICE.stat_groups(ItemSlot.HEAD) for f in group.fields}
        assert Stat.STRENGTH in all_stats and Stat.MELEE_WEAPON_DPS not in all_stats


class TestPreview:
    def test_a_clean_item_previews_as_usable(self) -> None:
        form = ManualItemForm(
            name="Custom Helm",
            slot=ItemSlot.HEAD,
            armor_type=ArmorType.PLATE,
            required_level=60,
            stats={Stat.STRENGTH: 25},
        )
        preview = SERVICE.preview(form)
        assert preview.item is not None and preview.usable and not preview.form_errors

    def test_implausible_custom_items_are_usable_with_warnings(self) -> None:
        form = ManualItemForm(
            name="Low Plate",
            slot=ItemSlot.HEAD,
            armor_type=ArmorType.PLATE,
            stats={Stat.STAMINA: 5},
        )
        preview = SERVICE.preview(form)
        assert preview.usable and any(i.code == "armor_level" for i in preview.issues)
        game_item = SERVICE.preview(form.model_copy(update={"custom": False}))
        assert not game_item.usable

    def test_form_errors_are_readable(self) -> None:
        form = ManualItemForm(
            name="Bad Ring",
            slot=ItemSlot.FINGER,
            min_damage=10,
            max_damage=20,
            speed=2.0,
        )
        preview = SERVICE.preview(form)
        assert preview.item is None and not preview.usable
        assert any("no weapon damage" in message for message in preview.form_errors)


def test_a_manual_item_takes_the_same_scoring_path() -> None:
    """A manual helm with Lionheart Helm's stats scores like the looked-up item would."""
    reading = SERVICE.read_tooltip(
        "Lionheart Helm\nHead  Plate\n565 Armor\n+18 Strength\nRequires Level 56\n"
        "Equip: Improves your chance to get a critical strike by 2%.\n"
        "Equip: Improves your chance to hit by 2%."
    )
    assert reading.form is not None
    preview = SERVICE.preview(reading.form)
    assert preview.item is not None and preview.usable
    profile = PROFILES.get("warrior_dps_fury")
    context = CharacterContext(
        ruleset="classic_era",
        phase=6,
        level=60,
        class_name="warrior",  # type: ignore[arg-type]
        role="melee_dps",  # type: ignore[arg-type]
        profile_id=profile.id,
        current_stats={Stat.HIT: 6},
    )
    result = score_item(preview.item, context, profile, RULESET)
    # 18 Strength x 2 = 36 AP; 2% crit x 20 = 40; 2% hit (6% -> 8%, under the cap) x 20 = 40.
    assert result.score == 116.0
