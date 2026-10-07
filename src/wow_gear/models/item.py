"""The canonical Item: the raw properties of one item, from any source.

An item never carries a score. Scores come from evaluating an item against a character
context and a build profile (``wow_gear.scoring``).

Structural rules live here (a ring has no weapon damage; a stat value is a finite number).
Game rules - plate below level 40, a stat a ruleset does not allow - are checked by
``wow_gear.processing`` against the ruleset, because they depend on the game version.
"""

from __future__ import annotations

import math
from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from wow_gear.core.hashing import content_hash
from wow_gear.models.enums import (
    WEAPON_DPS_STATS,
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

WEAPON_SLOTS = frozenset(
    {ItemSlot.ONE_HAND, ItemSlot.MAIN_HAND, ItemSlot.OFF_HAND, ItemSlot.TWO_HAND, ItemSlot.RANGED}
)
ARMOR_SLOTS = frozenset(
    {
        ItemSlot.HEAD,
        ItemSlot.SHOULDER,
        ItemSlot.BACK,
        ItemSlot.CHEST,
        ItemSlot.WRIST,
        ItemSlot.HANDS,
        ItemSlot.WAIST,
        ItemSlot.LEGS,
        ItemSlot.FEET,
    }
)
ITEM_ID_PATTERN = r"^[a-z][a-z0-9_]*:[A-Za-z0-9_.\-]+$"


class _Frozen(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class BonusDamage(_Frozen):
    """A second damage line on a weapon, such as "+3 - 6 Fire Damage"."""

    min_damage: float = Field(ge=0)
    max_damage: float = Field(ge=0)
    school: DamageSchool

    @model_validator(mode="after")
    def _ordered(self) -> BonusDamage:
        if self.max_damage < self.min_damage:
            raise ValueError("bonus damage maximum is below its minimum")
        return self


class WeaponStats(_Frozen):
    """A weapon's damage block. Speed is in seconds per swing."""

    min_damage: float = Field(ge=0)
    max_damage: float = Field(ge=0)
    speed: float = Field(gt=0, le=10)
    damage_school: DamageSchool = DamageSchool.PHYSICAL
    bonus_damage: tuple[BonusDamage, ...] = ()

    @model_validator(mode="after")
    def _ordered(self) -> WeaponStats:
        if self.max_damage < self.min_damage:
            raise ValueError("weapon maximum damage is below its minimum")
        return self

    @property
    def average_damage(self) -> float:
        """Average damage of one hit across every damage line on the tooltip."""
        extra = sum((line.min_damage + line.max_damage) / 2 for line in self.bonus_damage)
        return (self.min_damage + self.max_damage) / 2 + extra

    @property
    def dps(self) -> float:
        """Damage per second as the tooltip states it: average damage over speed."""
        return self.average_damage / self.speed


class EffectTrigger(StrEnum):
    EQUIP = "equip"
    USE = "use"
    CHANCE_ON_HIT = "chance_on_hit"


class EffectCondition(_Frozen):
    """When a stat effect applies. An empty condition means always."""

    target_creature_types: tuple[CreatureType, ...] = ()
    shapeshift_forms: tuple[str, ...] = ()
    note: str | None = None

    @property
    def is_empty(self) -> bool:
        return not (self.target_creature_types or self.shapeshift_forms)


class ItemEffect(_Frozen):
    """An equip, use or chance-on-hit line.

    A stat effect (``stat`` and ``value`` set) is something the scoring engine can value,
    when its condition holds. Every other effect - a proc, an on-use ability, a line the
    parser did not recognise - is kept with its tooltip text and reported as not scored:
    the calculator never invents a value for it.
    """

    trigger: EffectTrigger
    description: str = Field(min_length=1)
    stat: Stat | None = None
    value: float | None = None
    condition: EffectCondition | None = None
    proc_chance_percent: float | None = Field(default=None, ge=0, le=100)
    procs_per_minute: float | None = Field(default=None, ge=0)
    duration_seconds: float | None = Field(default=None, ge=0)
    cooldown_seconds: float | None = Field(default=None, ge=0)

    @model_validator(mode="after")
    def _stat_and_value_together(self) -> ItemEffect:
        if (self.stat is None) != (self.value is None):
            raise ValueError("a stat effect needs both a stat and a value")
        if self.value is not None and not math.isfinite(self.value):
            raise ValueError("effect value must be a finite number")
        if self.stat in WEAPON_DPS_STATS:
            raise ValueError(f"{self.stat} is read from the weapon block, not an effect")
        return self

    @property
    def is_stat_effect(self) -> bool:
        return self.stat is not None


class Provenance(_Frozen):
    """Where an item's data came from, so every score can name its inputs."""

    provider: str = Field(pattern=r"^[a-z][a-z0-9_]*$")
    source: str = Field(min_length=1)
    source_url: str | None = None
    data_version: str = Field(min_length=1)
    fetched_at: datetime | None = None
    license: str | None = None
    custom: bool = False
    """True for a theorycrafted item that is not claimed to exist in the game."""

    @field_validator("source_url")
    @classmethod
    def _web_address(cls, value: str | None) -> str | None:
        if value is not None and not value.startswith(("https://", "http://")):
            raise ValueError("source_url must be an http(s) address")
        return value


class Item(_Frozen):
    """One item, normalized. See docs/DATA_MODEL.md for each field."""

    id: str = Field(pattern=ITEM_ID_PATTERN)
    external_ids: dict[str, str] = Field(default_factory=dict)
    name: str = Field(min_length=1, max_length=120)
    ruleset: str = Field(min_length=1)
    phase: int | None = Field(default=None, ge=1)
    required_level: int = Field(default=0, ge=0)
    item_level: int | None = Field(default=None, ge=1)
    quality: ItemQuality | None = None
    slot: ItemSlot
    armor_type: ArmorType | None = None
    weapon_type: WeaponType | None = None
    relic_type: RelicType | None = None
    unique: bool = False
    allowed_classes: tuple[ClassName, ...] = ()
    allowed_races: tuple[Race, ...] = ()
    stats: dict[Stat, float] = Field(default_factory=dict)
    weapon: WeaponStats | None = None
    equip_effects: tuple[ItemEffect, ...] = ()
    on_use_effects: tuple[ItemEffect, ...] = ()
    set_id: str | None = None
    set_name: str | None = None
    provenance: Provenance

    @field_validator("stats")
    @classmethod
    def _clean_stats(cls, stats: dict[Stat, float]) -> dict[Stat, float]:
        cleaned: dict[Stat, float] = {}
        for stat, value in stats.items():
            if stat in WEAPON_DPS_STATS:
                raise ValueError(f"{stat} is read from the weapon block, not stored as a stat")
            if not math.isfinite(value):
                raise ValueError(f"{stat} must be a finite number")
            if value != 0:
                cleaned[stat] = float(value)
        return dict(sorted(cleaned.items()))

    @model_validator(mode="after")
    def _structure(self) -> Item:
        is_weapon_slot = self.slot in WEAPON_SLOTS
        if self.weapon is not None and not is_weapon_slot:
            raise ValueError(f"a {self.slot} item has no weapon damage")
        if self.weapon_type is not None and not is_weapon_slot:
            raise ValueError(f"a {self.slot} item has no weapon type")
        if self.armor_type is not None and self.slot not in ARMOR_SLOTS:
            raise ValueError(f"a {self.slot} item has no armor type")
        if (self.relic_type is not None) != (self.slot == ItemSlot.RELIC):
            raise ValueError("a relic, and only a relic, has a relic type")
        if self.set_name is not None and self.set_id is None:
            raise ValueError("a set_name needs the set_id it names")
        for effect in self.equip_effects:
            if effect.trigger == EffectTrigger.USE:
                raise ValueError("an equip effect cannot have the use trigger")
        for effect in self.on_use_effects:
            if effect.trigger != EffectTrigger.USE:
                raise ValueError("an on-use effect must have the use trigger")
        return self

    @property
    def is_weapon(self) -> bool:
        return self.weapon is not None or self.weapon_type is not None

    @property
    def is_custom(self) -> bool:
        return self.provenance.custom

    def properties(self) -> dict[str, Any]:
        """Everything that describes the item in game, without where or when it was fetched."""
        data = self.model_dump(mode="json")
        data.pop("provenance")
        data.pop("external_ids")
        return data

    @property
    def version(self) -> str:
        """A hash of the item's in-game properties: changes when, and only when, they do."""
        return content_hash(self.properties())
