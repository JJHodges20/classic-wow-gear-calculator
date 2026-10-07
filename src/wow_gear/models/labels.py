"""Human-readable names for the vocabularies, shared by services, reports and the app."""

from __future__ import annotations

from wow_gear.models.enums import (
    ArmorType,
    ContentMode,
    EquipmentSlot,
    ItemQuality,
    ItemSlot,
    RelicType,
    Role,
    WeaponType,
)

ROLE_LABELS: dict[Role, str] = {
    Role.TANK: "Tank",
    Role.HEALER: "Healer",
    Role.MELEE_DPS: "Melee DPS",
    Role.RANGED_DPS: "Ranged DPS",
    Role.CASTER_DPS: "Caster DPS",
}

CONTENT_MODE_LABELS: dict[ContentMode, str] = {
    ContentMode.RAID: "Raid PvE",
    ContentMode.DUNGEON: "Dungeon PvE",
    ContentMode.LEVELING: "Leveling",
    ContentMode.SOLO: "Solo",
    ContentMode.PVP: "PvP",
}

SLOT_LABELS: dict[ItemSlot, str] = {
    ItemSlot.HEAD: "Head",
    ItemSlot.NECK: "Neck",
    ItemSlot.SHOULDER: "Shoulder",
    ItemSlot.BACK: "Back",
    ItemSlot.CHEST: "Chest",
    ItemSlot.WRIST: "Wrist",
    ItemSlot.HANDS: "Hands",
    ItemSlot.WAIST: "Waist",
    ItemSlot.LEGS: "Legs",
    ItemSlot.FEET: "Feet",
    ItemSlot.FINGER: "Finger",
    ItemSlot.TRINKET: "Trinket",
    ItemSlot.ONE_HAND: "One-hand",
    ItemSlot.MAIN_HAND: "Main hand",
    ItemSlot.OFF_HAND: "Off hand",
    ItemSlot.HELD_IN_OFF_HAND: "Held in off-hand",
    ItemSlot.SHIELD: "Shield",
    ItemSlot.TWO_HAND: "Two-hand",
    ItemSlot.RANGED: "Ranged",
    ItemSlot.RELIC: "Relic",
}

EQUIPMENT_SLOT_LABELS: dict[EquipmentSlot, str] = {
    EquipmentSlot.HEAD: "Head",
    EquipmentSlot.NECK: "Neck",
    EquipmentSlot.SHOULDER: "Shoulder",
    EquipmentSlot.BACK: "Back",
    EquipmentSlot.CHEST: "Chest",
    EquipmentSlot.WRIST: "Wrist",
    EquipmentSlot.HANDS: "Hands",
    EquipmentSlot.WAIST: "Waist",
    EquipmentSlot.LEGS: "Legs",
    EquipmentSlot.FEET: "Feet",
    EquipmentSlot.FINGER_1: "Finger 1",
    EquipmentSlot.FINGER_2: "Finger 2",
    EquipmentSlot.TRINKET_1: "Trinket 1",
    EquipmentSlot.TRINKET_2: "Trinket 2",
    EquipmentSlot.MAIN_HAND: "Main hand",
    EquipmentSlot.OFF_HAND: "Off hand",
    EquipmentSlot.RANGED: "Ranged or relic",
}

ARMOR_LABELS: dict[ArmorType, str] = {
    ArmorType.CLOTH: "Cloth",
    ArmorType.LEATHER: "Leather",
    ArmorType.MAIL: "Mail",
    ArmorType.PLATE: "Plate",
}

WEAPON_LABELS: dict[WeaponType, tuple[str, str]] = {
    WeaponType.DAGGER: ("Dagger", "daggers"),
    WeaponType.SWORD: ("Sword", "swords"),
    WeaponType.TWO_HANDED_SWORD: ("Two-handed sword", "two-handed swords"),
    WeaponType.AXE: ("Axe", "axes"),
    WeaponType.TWO_HANDED_AXE: ("Two-handed axe", "two-handed axes"),
    WeaponType.MACE: ("Mace", "maces"),
    WeaponType.TWO_HANDED_MACE: ("Two-handed mace", "two-handed maces"),
    WeaponType.FIST: ("Fist weapon", "fist weapons"),
    WeaponType.POLEARM: ("Polearm", "polearms"),
    WeaponType.STAFF: ("Staff", "staves"),
    WeaponType.BOW: ("Bow", "bows"),
    WeaponType.GUN: ("Gun", "guns"),
    WeaponType.CROSSBOW: ("Crossbow", "crossbows"),
    WeaponType.THROWN: ("Thrown", "thrown weapons"),
    WeaponType.WAND: ("Wand", "wands"),
}

RELIC_LABELS: dict[RelicType, str] = {
    RelicType.LIBRAM: "Libram",
    RelicType.IDOL: "Idol",
    RelicType.TOTEM: "Totem",
}

QUALITY_LABELS: dict[ItemQuality, str] = {
    ItemQuality.POOR: "Poor",
    ItemQuality.COMMON: "Common",
    ItemQuality.UNCOMMON: "Uncommon",
    ItemQuality.RARE: "Rare",
    ItemQuality.EPIC: "Epic",
    ItemQuality.LEGENDARY: "Legendary",
}


def weapon_label(weapon_type: WeaponType, plural: bool = False) -> str:
    singular, many = WEAPON_LABELS[weapon_type]
    return many if plural else singular
