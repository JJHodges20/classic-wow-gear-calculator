"""GearSet: the items a character wears, by equipment slot. Used from milestone 9."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from wow_gear.models.enums import EquipmentSlot, ItemSlot

EQUIPMENT_SLOTS: dict[ItemSlot, tuple[EquipmentSlot, ...]] = {
    ItemSlot.HEAD: (EquipmentSlot.HEAD,),
    ItemSlot.NECK: (EquipmentSlot.NECK,),
    ItemSlot.SHOULDER: (EquipmentSlot.SHOULDER,),
    ItemSlot.BACK: (EquipmentSlot.BACK,),
    ItemSlot.CHEST: (EquipmentSlot.CHEST,),
    ItemSlot.WRIST: (EquipmentSlot.WRIST,),
    ItemSlot.HANDS: (EquipmentSlot.HANDS,),
    ItemSlot.WAIST: (EquipmentSlot.WAIST,),
    ItemSlot.LEGS: (EquipmentSlot.LEGS,),
    ItemSlot.FEET: (EquipmentSlot.FEET,),
    ItemSlot.FINGER: (EquipmentSlot.FINGER_1, EquipmentSlot.FINGER_2),
    ItemSlot.TRINKET: (EquipmentSlot.TRINKET_1, EquipmentSlot.TRINKET_2),
    ItemSlot.ONE_HAND: (EquipmentSlot.MAIN_HAND, EquipmentSlot.OFF_HAND),
    ItemSlot.MAIN_HAND: (EquipmentSlot.MAIN_HAND,),
    ItemSlot.OFF_HAND: (EquipmentSlot.OFF_HAND,),
    ItemSlot.HELD_IN_OFF_HAND: (EquipmentSlot.OFF_HAND,),
    ItemSlot.SHIELD: (EquipmentSlot.OFF_HAND,),
    ItemSlot.TWO_HAND: (EquipmentSlot.MAIN_HAND,),
    ItemSlot.RANGED: (EquipmentSlot.RANGED,),
    ItemSlot.RELIC: (EquipmentSlot.RANGED,),
}
"""Where an item of each slot type can be equipped. A two-handed weapon is equipped in the
main hand and also leaves the off hand empty (``BLOCKS_OFF_HAND``)."""

BLOCKS_OFF_HAND = frozenset({ItemSlot.TWO_HAND})


class GearSet(BaseModel):
    """Item ids by equipment slot. Empty slots are simply absent."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    name: str = Field(default="Current gear", min_length=1, max_length=80)
    items: dict[EquipmentSlot, str] = Field(default_factory=dict)
