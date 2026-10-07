"""Game item codes shared by every source that uses the client's numbering.

Item class 2 is weapons and 4 armor; their subclass numbers are the same in the game client,
VMaNGOS and Blizzard's Game Data API.
"""

from __future__ import annotations

from wow_gear.models.enums import ArmorType, ItemQuality, RelicType, WeaponType

WEAPON_CLASS = 2
ARMOR_CLASS = 4

WEAPON_SUBCLASSES: dict[int, WeaponType] = {
    0: WeaponType.AXE,
    1: WeaponType.TWO_HANDED_AXE,
    2: WeaponType.BOW,
    3: WeaponType.GUN,
    4: WeaponType.MACE,
    5: WeaponType.TWO_HANDED_MACE,
    6: WeaponType.POLEARM,
    7: WeaponType.SWORD,
    8: WeaponType.TWO_HANDED_SWORD,
    10: WeaponType.STAFF,
    13: WeaponType.FIST,
    15: WeaponType.DAGGER,
    16: WeaponType.THROWN,
    18: WeaponType.CROSSBOW,
    19: WeaponType.WAND,
}
ARMOR_SUBCLASSES: dict[int, ArmorType] = {
    1: ArmorType.CLOTH,
    2: ArmorType.LEATHER,
    3: ArmorType.MAIL,
    4: ArmorType.PLATE,
}
RELIC_SUBCLASSES: dict[int, RelicType] = {
    7: RelicType.LIBRAM,
    8: RelicType.IDOL,
    9: RelicType.TOTEM,
}
QUALITY_NAMES: dict[str, ItemQuality] = {quality.name: quality for quality in ItemQuality}
"""Quality by upper-case name, as Blizzard's API writes it ("EPIC")."""
