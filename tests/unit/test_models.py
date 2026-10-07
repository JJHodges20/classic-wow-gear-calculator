"""The canonical models hold data and reject structurally impossible input."""

from __future__ import annotations

from typing import Any

import pytest
from pydantic import ValidationError

from wow_gear.models.character import CharacterContext
from wow_gear.models.enums import (
    ArmorType,
    ClassName,
    ContentMode,
    DamageSchool,
    ItemSlot,
    RelicType,
    Role,
    Stat,
    ValidationStatus,
    WeaponType,
)
from wow_gear.models.item import (
    BonusDamage,
    EffectCondition,
    EffectTrigger,
    Item,
    ItemEffect,
    Provenance,
    WeaponStats,
)
from wow_gear.models.profile import (
    BuildProfile,
    CapReference,
    DerivedStatRule,
    HardCap,
    SourceRef,
    StatWeight,
    WeightBasis,
)

FIXTURE = Provenance(provider="fixture", source="Test fixture", data_version="test-1", custom=True)


def item(**changes: Any) -> Item:
    data: dict[str, Any] = {
        "id": "custom:helm",
        "name": "Fixture Helm",
        "ruleset": "classic_era",
        "slot": ItemSlot.HEAD,
        "armor_type": ArmorType.PLATE,
        "stats": {Stat.STAMINA: 20, Stat.STRENGTH: 10},
        "provenance": FIXTURE,
    }
    data.update(changes)
    return Item(**data)


class TestItem:
    def test_zero_stats_are_dropped_and_the_rest_sorted(self) -> None:
        helm = item(stats={Stat.STAMINA: 20, Stat.HIT: 0, Stat.AGILITY: 5})
        assert list(helm.stats) == [Stat.AGILITY, Stat.STAMINA]

    def test_the_version_follows_properties_not_provenance(self) -> None:
        a = item()
        b = item(provenance=FIXTURE.model_copy(update={"data_version": "test-2"}))
        c = item(stats={Stat.STAMINA: 21, Stat.STRENGTH: 10})
        assert a.version == b.version
        assert a.version != c.version

    def test_a_ring_cannot_have_weapon_damage(self) -> None:
        with pytest.raises(ValidationError, match="no weapon damage"):
            item(
                slot=ItemSlot.FINGER,
                armor_type=None,
                weapon=WeaponStats(min_damage=1, max_damage=2, speed=2.0),
            )

    def test_a_ring_has_no_armor_type(self) -> None:
        with pytest.raises(ValidationError, match="no armor type"):
            item(slot=ItemSlot.FINGER, armor_type=ArmorType.PLATE)

    def test_only_a_relic_has_a_relic_type(self) -> None:
        with pytest.raises(ValidationError, match="relic"):
            item(relic_type=RelicType.LIBRAM)
        relic = item(slot=ItemSlot.RELIC, armor_type=None, relic_type=RelicType.LIBRAM)
        assert relic.relic_type == RelicType.LIBRAM

    def test_weapon_dps_is_not_an_item_stat(self) -> None:
        with pytest.raises(ValidationError, match="weapon block"):
            item(stats={Stat.MELEE_WEAPON_DPS: 50})

    def test_a_stat_must_be_finite(self) -> None:
        with pytest.raises(ValidationError, match="finite"):
            item(stats={Stat.STAMINA: float("nan")})

    def test_a_set_name_needs_its_set_id(self) -> None:
        with pytest.raises(ValidationError, match="set_id"):
            item(set_name="Battlegear of Might")
        assert item(set_id="209").set_name is None

    def test_an_on_use_effect_needs_the_use_trigger(self) -> None:
        effect = ItemEffect(trigger=EffectTrigger.EQUIP, description="Equip: something")
        with pytest.raises(ValidationError, match="use trigger"):
            item(on_use_effects=(effect,))

    def test_unknown_fields_are_rejected(self) -> None:
        with pytest.raises(ValidationError, match="sparkle"):
            item(sparkle=True)

    def test_ids_name_their_namespace(self) -> None:
        with pytest.raises(ValidationError):
            item(id="no-namespace")


class TestWeapon:
    def test_dps_is_average_damage_over_speed(self) -> None:
        weapon = WeaponStats(min_damage=100, max_damage=200, speed=2.5)
        assert weapon.average_damage == 150
        assert weapon.dps == pytest.approx(60.0)

    def test_bonus_damage_lines_count_toward_dps(self) -> None:
        weapon = WeaponStats(
            min_damage=60,
            max_damage=90,
            speed=1.5,
            bonus_damage=(BonusDamage(min_damage=3, max_damage=6, school=DamageSchool.FIRE),),
        )
        assert weapon.dps == pytest.approx((75 + 4.5) / 1.5)

    def test_minimum_above_maximum_is_rejected(self) -> None:
        with pytest.raises(ValidationError, match="below its minimum"):
            WeaponStats(min_damage=10, max_damage=5, speed=2.0)

    def test_speed_must_be_positive(self) -> None:
        with pytest.raises(ValidationError):
            WeaponStats(min_damage=1, max_damage=2, speed=0)

    def test_a_weapon_item(self) -> None:
        sword = item(
            id="custom:sword",
            slot=ItemSlot.ONE_HAND,
            armor_type=None,
            weapon_type=WeaponType.SWORD,
            weapon=WeaponStats(min_damage=50, max_damage=100, speed=2.0),
        )
        assert sword.is_weapon and sword.weapon is not None


class TestEffects:
    def test_a_stat_effect_needs_both_stat_and_value(self) -> None:
        with pytest.raises(ValidationError, match="both a stat and a value"):
            ItemEffect(trigger=EffectTrigger.EQUIP, description="x", stat=Stat.ATTACK_POWER)

    def test_a_conditional_stat_effect(self) -> None:
        effect = ItemEffect(
            trigger=EffectTrigger.EQUIP,
            description="Equip: +81 Attack Power when fighting Undead.",
            stat=Stat.ATTACK_POWER,
            value=81,
            condition=EffectCondition(target_creature_types=("undead",)),  # type: ignore[arg-type]
        )
        assert effect.is_stat_effect and effect.condition is not None
        assert not effect.condition.is_empty

    def test_a_proc_is_kept_as_text(self) -> None:
        effect = ItemEffect(
            trigger=EffectTrigger.CHANCE_ON_HIT,
            description="Chance on hit: Blasts your enemy with lightning.",
            procs_per_minute=1.0,
        )
        assert not effect.is_stat_effect


class TestProvenance:
    def test_a_source_url_must_be_a_web_address(self) -> None:
        with pytest.raises(ValidationError, match="http"):
            Provenance(provider="x", source="x", data_version="1", source_url="file:///etc")


class TestCharacterContext:
    def test_gear_totals_drop_zeros_and_change_the_fingerprint(self) -> None:
        base = {
            "ruleset": "classic_era",
            "phase": 6,
            "level": 60,
            "class_name": ClassName.WARRIOR,
            "role": Role.TANK,
            "profile_id": "warrior_tank_deep_prot",
            "content_mode": ContentMode.RAID,
        }
        without = CharacterContext(**base)
        with_stats = CharacterContext(**base, current_stats={Stat.HIT: 5, Stat.CRIT: 0})
        assert with_stats.current_stats == {Stat.HIT: 5.0}
        assert with_stats.current(Stat.HIT) == 5 and without.current(Stat.HIT) == 0
        assert not without.has_current_stats and with_stats.has_current_stats
        assert without.fingerprint != with_stats.fingerprint


def profile(**changes: Any) -> BuildProfile:
    data: dict[str, Any] = {
        "id": "test_profile",
        "version": "1.0.0",
        "label": "Test",
        "class_name": ClassName.WARRIOR,
        "role": Role.MELEE_DPS,
        "specialization": "Fury",
        "summary": "A test profile.",
        "ruleset": "classic_era",
        "target_level": 60,
        "default_content_mode": ContentMode.RAID,
        "score_unit": "AP equivalents",
        "stat_weights": (
            StatWeight(stat=Stat.ATTACK_POWER, weight=1.0, basis=WeightBasis.ASSUMPTION),
            StatWeight(stat=Stat.HIT, weight=20.0, basis=WeightBasis.ASSUMPTION),
        ),
        "validation_status": ValidationStatus.DRAFT,
    }
    data.update(changes)
    return BuildProfile(**data)


class TestProfile:
    def test_a_minimal_profile(self) -> None:
        assert profile().weight_of(Stat.HIT) == 20.0
        assert profile().weight_of(Stat.SPIRIT) == 0.0

    def test_a_stat_weighted_twice(self) -> None:
        weights = (
            StatWeight(stat=Stat.HIT, weight=1, basis=WeightBasis.ASSUMPTION),
            StatWeight(stat=Stat.HIT, weight=2, basis=WeightBasis.ASSUMPTION),
        )
        with pytest.raises(ValidationError, match="weighted twice"):
            profile(stat_weights=weights)

    def test_a_sourced_weight_must_cite(self) -> None:
        weights = (StatWeight(stat=Stat.HIT, weight=1, basis=WeightBasis.SOURCED),)
        with pytest.raises(ValidationError, match="cites no source"):
            profile(stat_weights=weights)

    def test_a_citation_must_be_listed(self) -> None:
        weights = (
            StatWeight(stat=Stat.HIT, weight=1, basis=WeightBasis.SOURCED, sources=("guide",)),
        )
        with pytest.raises(ValidationError, match="guide"):
            profile(stat_weights=weights)
        listed = SourceRef(
            id="guide", title="A guide", url="https://example.org", retrieved="2026-10-07"
        )
        assert profile(stat_weights=weights, sources=(listed,)).sources[0].id == "guide"

    def test_a_cap_on_an_unvalued_stat(self) -> None:
        cap = HardCap(stat=Stat.SPELL_HIT, cap=CapReference(fixed=16))
        with pytest.raises(ValidationError, match="does not value"):
            profile(hard_caps=(cap,))

    def test_a_cap_is_a_formula_or_a_number(self) -> None:
        with pytest.raises(ValidationError, match="either"):
            CapReference(ruleset_cap="melee_hit", fixed=9)
        with pytest.raises(ValidationError, match="either"):
            CapReference()

    def test_a_stat_cannot_convert_into_itself(self) -> None:
        rule = DerivedStatRule(source=Stat.AGILITY, target=Stat.AGILITY)
        with pytest.raises(ValidationError, match="itself"):
            profile(derived_stats=(rule,))

    def test_the_hash_follows_the_content(self) -> None:
        assert profile().content_hash == profile().content_hash
        assert profile().content_hash != profile(version="1.0.1").content_hash
