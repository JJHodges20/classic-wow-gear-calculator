"""VMaNGOS rows into canonical items: every mapping table, on hand-built rows.

The rows imitate VMaNGOS's item_template and spell_template columns; no snapshot is needed.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import pytest

from wow_gear.models.enums import (
    ArmorType,
    ClassName,
    CreatureType,
    DamageSchool,
    ItemQuality,
    ItemSlot,
    Race,
    RelicType,
    Stat,
    WeaponType,
)
from wow_gear.models.item import EffectTrigger
from wow_gear.processing.vmangos import (
    SourceInfo,
    map_spell,
    normalize_item,
    phase_for,
    render_description,
    source_info,
    vmangos_provenance,
)

PROVENANCE = vmangos_provenance("db-test", datetime(2026, 10, 7, tzinfo=UTC))


def spell(entry: int, description: str, *effects: tuple[int, int, int]) -> dict[str, Any]:
    """A spell row; each effect is (aura, misc value, base points) with one die side."""
    row: dict[str, Any] = {"entry": entry, "name": f"Spell {entry}", "description": description}
    for index, (aura, misc, base) in enumerate(effects, start=1):
        row[f"effectApplyAuraName{index}"] = aura
        row[f"effectMiscValue{index}"] = misc
        row[f"effectBasePoints{index}"] = base
        row[f"effectDieSides{index}"] = 1
    return row


SPELLS = {
    7598: spell(7598, "Improves your chance to get a critical strike by $s1%.", (52, 0, 1)),
    15465: spell(15465, "Improves your chance to hit by $s1%.", (54, 0, 1)),
    9331: spell(9331, "+$s1 Attack Power.", (99, 0, 19), (124, 0, 19)),
    17319: spell(17319, "+$s1 Attack Power when fighting Undead.", (102, 32, 80), (131, 32, 80)),
    15715: spell(
        15715,
        "Increases damage and healing done by magical spells and effects by up to $s1.",
        (13, 126, 24),
        (135, 126, 24),
    ),
    28155: spell(
        28155,
        "Increases your spell damage by up to 120 and your healing by up to 300.",
        (13, 126, 119),
        (135, 126, 299),
    ),
    28717: spell(28717, "+$s1 Attack Power in Cat, Bear, and Dire Bear forms only.", (99, 0, 119)),
    7527: spell(7527, "Increased Swords +$s1.", (30, 43, 6)),
    13385: spell(13385, "Increased Defense +$s1.", (30, 95, 6)),
    21596: spell(21596, "Restores $s1 health per 5 sec.", (161, 0, 9)),
    18378: spell(18378, "Restores $s1 mana per 5 sec.", (85, 0, 6)),
    28799: spell(
        28799, "Decreases the magical resistances of your spell targets by $s1.", (123, 124, -26)
    ),
    21352: spell(21352, "Decreases your chance to parry an attack by $s1%.", (47, 0, -2)),
    15600: spell(15600, "2% chance on melee hit to gain 1 extra attack.", (42, 0, 0)),
    24252: spell(24252, "Increases the damage of Moonfire by $s1.", (107, 0, 19)),
    21162: spell(
        21162, "Blasts your enemy with lightning, dealing $s1 Nature damage.", (0, 0, 299)
    ),
}


def row(**changes: Any) -> dict[str, Any]:
    data: dict[str, Any] = {
        "entry": 12640,
        "name": "Lionheart Helm",
        "quality": 4,
        "item_level": 61,
        "required_level": 56,
        "inventory_type": 1,
        "class": 4,
        "subclass": 4,
        "allowable_class": -1,
        "allowable_race": -1,
        "armor": 565,
        "block": 0,
        "stat_type1": 4,
        "stat_value1": 18,
        "spellid_1": 7598,
        "spelltrigger_1": 1,
        "spellid_2": 15465,
        "spelltrigger_2": 1,
        "first_patch": 0,
        "max_count": 0,
        "set_id": 0,
        "delay": 0,
        "dmg_min1": 0,
        "dmg_max1": 0,
    }
    data.update(changes)
    return data


def normalize(**changes: Any):  # type: ignore[no-untyped-def]
    return normalize_item(row(**changes), SPELLS, source=SourceInfo(), provenance=PROVENANCE)


class TestItems:
    def test_a_plate_helm_with_equip_stats(self) -> None:
        helm = normalize()
        assert helm.id == "classic_era:12640" and helm.external_ids["vmangos"] == "12640"
        assert (helm.slot, helm.armor_type, helm.quality) == (
            ItemSlot.HEAD,
            ArmorType.PLATE,
            ItemQuality.EPIC,
        )
        assert helm.stats == {Stat.ARMOR: 565, Stat.CRIT: 2, Stat.HIT: 2, Stat.STRENGTH: 18}
        assert helm.equip_effects == () and helm.phase == 1
        assert helm.provenance.provider == "bundled"

    def test_a_weapon_with_bonus_damage(self) -> None:
        sword = normalize(
            entry=19019,
            name="Thunderfury",
            inventory_type=13,
            **{"class": 2},
            subclass=7,
            armor=0,
            delay=1900,
            dmg_min1=44,
            dmg_max1=115,
            dmg_type1=0,
            dmg_min2=16,
            dmg_max2=30,
            dmg_type2=3,
            spellid_1=21162,
            spelltrigger_1=2,
            spellppmrate_1=6.0,
            spellid_2=0,
        )
        assert (sword.slot, sword.weapon_type) == (ItemSlot.ONE_HAND, WeaponType.SWORD)
        assert sword.weapon is not None and sword.weapon.speed == pytest.approx(1.9)
        assert sword.weapon.bonus_damage[0].school == DamageSchool.NATURE
        proc = sword.equip_effects[0]
        assert proc.trigger == EffectTrigger.CHANCE_ON_HIT and proc.procs_per_minute == 6.0
        assert (
            proc.description
            == "Chance on hit: Blasts your enemy with lightning, dealing 300 Nature damage."
        )

    def test_restrictions_from_class_and_race_masks(self) -> None:
        token = normalize(allowable_class=16 | 128, allowable_race=2 | 128)
        assert set(token.allowed_classes) == {ClassName.PRIEST, ClassName.MAGE}
        assert set(token.allowed_races) == {Race.ORC, Race.TROLL}
        assert normalize(allowable_class=32767).allowed_classes == ()

    def test_relics_and_off_hands(self) -> None:
        idol = normalize(inventory_type=28, subclass=8, armor=0, stat_type1=0, stat_value1=0)
        assert (idol.slot, idol.relic_type, idol.armor_type) == (
            ItemSlot.RELIC,
            RelicType.IDOL,
            None,
        )
        frill = normalize(inventory_type=23, subclass=0, armor=0)
        assert (frill.slot, frill.armor_type) == (ItemSlot.HELD_IN_OFF_HAND, None)

    def test_conditional_attack_power_stays_an_effect(self) -> None:
        seal = normalize(inventory_type=12, subclass=0, armor=0, spellid_1=17319, spellid_2=0)
        assert seal.stats == {Stat.STRENGTH: 18}
        stats = {effect.stat for effect in seal.equip_effects}
        assert stats == {Stat.ATTACK_POWER, Stat.RANGED_ATTACK_POWER}
        condition = seal.equip_effects[0].condition
        assert condition is not None and condition.target_creature_types == (CreatureType.UNDEAD,)

    def test_unmappable_spells_keep_their_text(self) -> None:
        trinket = normalize(inventory_type=12, armor=0, spellid_1=15600, spellid_2=9331)
        assert trinket.stats[Stat.ATTACK_POWER] == 20
        assert trinket.equip_effects[0].description.startswith("Equip: 2% chance on melee hit")
        assert trinket.equip_effects[0].stat is None

    def test_health_and_holy_resistance_are_kept_as_text(self) -> None:
        item = normalize(stat_type2=1, stat_value2=40, holy_res=10)
        assert {e.description for e in item.equip_effects} == {"+40 Health", "+10 Holy Resistance"}

    def test_a_use_effect_with_the_spell_cooldown(self) -> None:
        item = normalize(spellid_1=18378, spelltrigger_1=0, spellcooldown_1=-1, spellid_2=0)
        effect = item.on_use_effects[0]
        assert effect.trigger == EffectTrigger.USE and effect.cooldown_seconds is None


class TestSpellMapping:
    @pytest.mark.parametrize(
        ("spell_id", "expected"),
        [
            (9331, {Stat.ATTACK_POWER: 20, Stat.RANGED_ATTACK_POWER: 20}),
            (15715, {Stat.SPELL_POWER: 25}),
            (28155, {Stat.SPELL_POWER: 120, Stat.HEALING_POWER: 180}),
            (7527, {Stat.SWORD_SKILL: 7}),
            (13385, {Stat.DEFENSE: 7}),
            (21596, {Stat.HP5: 10}),
            (18378, {Stat.MP5: 7}),
            (28799, {Stat.SPELL_PENETRATION: 25}),
            (21352, {Stat.PARRY: -1}),
        ],
    )
    def test_auras_into_stats(self, spell_id: int, expected: dict[Stat, float]) -> None:
        mapped = map_spell(SPELLS[spell_id])
        assert mapped is not None
        assert {stat: value for stat, value, _ in mapped} == expected

    def test_feral_attack_power_needs_a_form(self) -> None:
        mapped = map_spell(SPELLS[28717])
        assert mapped is not None
        stat, value, condition = mapped[0]
        assert (stat, value) == (Stat.FERAL_ATTACK_POWER, 120)
        assert condition is not None and "cat" in condition.shapeshift_forms

    @pytest.mark.parametrize("spell_id", [15600, 24252, 21162])
    def test_procs_and_spell_specific_bonuses_are_not_stats(self, spell_id: int) -> None:
        assert map_spell(SPELLS[spell_id]) is None

    def test_descriptions_are_rendered_with_their_numbers(self) -> None:
        assert render_description(SPELLS[15465]) == "Improves your chance to hit by 2%."
        assert render_description(SPELLS[28799]).endswith("by 25.")
        bleed = spell(1, "Wounds the target for $o1 damage over $d.", (3, 0, 9))
        assert render_description(bleed) == "Wounds the target for [amount] damage over [duration]."

    def test_a_proc_takes_its_numbers_from_the_spell_it_triggers(self) -> None:
        proc = spell(18815, "A 3% chance of stealing $18817s1 life.", (42, 0, 0))
        drain = spell(18817, "Drains life.", (9, 0, 34))
        flame = {
            **spell(18818, "Fire damage.", (2, 0, 74)),
            "effectDieSides1": 51,
        }
        nova = spell(18816, "A 1% chance of dealing $18818s1 Fire damage.", (42, 0, 0))
        spells = {18817: drain, 18818: flame}
        assert render_description(proc, spells) == "A 3% chance of stealing 35 life."
        assert render_description(nova, spells) == "A 1% chance of dealing 75 to 125 Fire damage."
        assert render_description(proc) == "A 3% chance of stealing [amount] life."

    def test_periods_word_forms_and_unknown_durations(self) -> None:
        regen = {
            **spell(1, "Restores 10 health every $t1 sec.", (8, 0, 9)),
            "effectAmplitude1": 5000,
        }
        assert render_description(regen) == "Restores 10 health every 5 sec."
        cure = spell(2, "Cures 1 poison $leffect:effects; for $d1.", (0, 0, 0))
        assert render_description(cure) == "Cures 1 poison effects for [duration]."
        freeze = spell(3, "Freezes them for $18798d and lowers $ghis:her; armor.", (0, 0, 0))
        assert render_description(freeze) == "Freezes them for [duration] and lowers his/her armor."
        scaled = spell(4, "Lasts $/1000;S1 sec longer.", (0, 0, 499))
        assert render_description(scaled) == "Lasts 0.5 sec longer."


class TestPhases:
    def test_raid_drops_take_the_raid_phase(self) -> None:
        class Loot:
            def __init__(self, map_id: int, kind: str = "creature", entry: int = 1) -> None:
                self.map_id, self.source_kind, self.source_entry = map_id, kind, entry

        assert source_info([Loot(409)]).raid_or_world_boss_phase == 1  # Molten Core
        assert source_info([Loot(469), Loot(409)]).raid_or_world_boss_phase == 1
        assert source_info([Loot(533)]).raid_or_world_boss_phase == 6  # Naxxramas
        assert source_info([Loot(1, entry=6109)]).raid_or_world_boss_phase == 2  # Azuregos
        assert source_info([Loot(230)]).raid_or_world_boss_phase is None  # a dungeon

    def test_otherwise_the_first_patch_decides(self) -> None:
        assert phase_for(3, SourceInfo(raid_or_world_boss_phase=1)) == 1
        assert phase_for(0, SourceInfo()) == 1  # 1.2
        assert phase_for(1, SourceInfo()) == 2  # 1.3: Dire Maul
        assert phase_for(8, SourceInfo()) == 5  # 1.10: Tier 0.5
        assert phase_for(9, SourceInfo()) == 6  # 1.11: Naxxramas
