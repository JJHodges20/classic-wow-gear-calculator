"""Input models: what the manual item form submits.

The form is shaped like the roadmap's Path A: the slot and item type first, then numeric
stats, an optional weapon block, and optional effect rows. It becomes a canonical Item in
``wow_gear.processing.manual`` - the same model every provider produces.
"""

from __future__ import annotations

import math
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from wow_gear.models.enums import (
    WEAPON_DPS_STATS,
    ArmorType,
    CreatureType,
    DamageSchool,
    ItemQuality,
    ItemSlot,
    RelicType,
    Stat,
    WeaponType,
)
from wow_gear.models.item import EffectTrigger


class EffectRow(BaseModel):
    """One optional effect row: a stat effect, possibly conditional, or a line of text."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    kind: Literal["stat", "conditional_stat", "text"]
    trigger: EffectTrigger = EffectTrigger.EQUIP
    stat: Stat | None = None
    value: float | None = None
    target_creature_types: tuple[CreatureType, ...] = ()
    text: str = ""

    @model_validator(mode="after")
    def _complete(self) -> EffectRow:
        if self.kind in ("stat", "conditional_stat"):
            if self.stat is None or self.value is None:
                raise ValueError("a stat effect row needs a stat and a value")
            if self.stat in WEAPON_DPS_STATS:
                raise ValueError("weapon damage per second comes from the weapon fields")
        if self.kind == "conditional_stat" and not self.target_creature_types:
            raise ValueError("a conditional stat row needs at least one creature type")
        if self.kind == "text" and not self.text.strip():
            raise ValueError("a text effect row needs its text")
        return self


class ManualItemForm(BaseModel):
    """Everything the manual entry form collects."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    name: str = Field(min_length=1, max_length=120)
    slot: ItemSlot
    armor_type: ArmorType | None = None
    weapon_type: WeaponType | None = None
    relic_type: RelicType | None = None
    quality: ItemQuality | None = None
    required_level: int = Field(default=0, ge=0)
    phase: int | None = Field(default=None, ge=1)
    stats: dict[Stat, float] = Field(default_factory=dict)
    min_damage: float | None = Field(default=None, ge=0)
    max_damage: float | None = Field(default=None, ge=0)
    speed: float | None = Field(default=None, gt=0)
    damage_school: DamageSchool = DamageSchool.PHYSICAL
    effects: tuple[EffectRow, ...] = ()
    set_name: str | None = None
    custom: bool = True
    """A theorycrafted item; uncheck when copying a real item's tooltip."""
    source_note: str | None = None

    @field_validator("name")
    @classmethod
    def _trim(cls, name: str) -> str:
        name = " ".join(name.split())
        if not name:
            raise ValueError("the item needs a name")
        return name

    @field_validator("stats")
    @classmethod
    def _finite(cls, stats: dict[Stat, float]) -> dict[Stat, float]:
        for stat, value in stats.items():
            if not math.isfinite(value):
                raise ValueError(f"{stat} must be a number")
        return stats

    @property
    def has_weapon_damage(self) -> bool:
        return None not in (self.min_damage, self.max_damage, self.speed)
