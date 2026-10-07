"""GearSet: the items a character wears, by equipment slot. Used from milestone 9."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from wow_gear.models.enums import EquipmentSlot


class GearSet(BaseModel):
    """Item ids by equipment slot. Empty slots are simply absent."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    name: str = Field(default="Current gear", min_length=1, max_length=80)
    items: dict[EquipmentSlot, str] = Field(default_factory=dict)
