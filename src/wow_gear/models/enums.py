"""The controlled vocabularies: classes, roles, races, slots, item types, stats.

These are names, not mechanics. Which class may wear what, what a stat converts into and
where its caps lie are ruleset data (``configs/rulesets``), never constants here.
"""

from __future__ import annotations

from enum import StrEnum


class ClassName(StrEnum):
    WARRIOR = "warrior"
    PALADIN = "paladin"
    HUNTER = "hunter"
    ROGUE = "rogue"
    PRIEST = "priest"
    SHAMAN = "shaman"
    MAGE = "mage"
    WARLOCK = "warlock"
    DRUID = "druid"


class Role(StrEnum):
    TANK = "tank"
    HEALER = "healer"
    MELEE_DPS = "melee_dps"
    RANGED_DPS = "ranged_dps"
    CASTER_DPS = "caster_dps"


class Race(StrEnum):
    HUMAN = "human"
    DWARF = "dwarf"
    NIGHT_ELF = "night_elf"
    GNOME = "gnome"
    ORC = "orc"
    UNDEAD = "undead"
    TAUREN = "tauren"
    TROLL = "troll"


class Faction(StrEnum):
    ALLIANCE = "alliance"
    HORDE = "horde"


class ContentMode(StrEnum):
    RAID = "raid_pve"
    DUNGEON = "dungeon_pve"
    LEVELING = "leveling"
    SOLO = "solo"
    PVP = "pvp"


class CreatureType(StrEnum):
    BEAST = "beast"
    DEMON = "demon"
    DRAGONKIN = "dragonkin"
    ELEMENTAL = "elemental"
    GIANT = "giant"
    HUMANOID = "humanoid"
    MECHANICAL = "mechanical"
    UNDEAD = "undead"


class ItemQuality(StrEnum):
    POOR = "poor"
    COMMON = "common"
    UNCOMMON = "uncommon"
    RARE = "rare"
    EPIC = "epic"
    LEGENDARY = "legendary"


class ItemSlot(StrEnum):
    """Where an item is worn: the item's inventory type."""

    HEAD = "head"
    NECK = "neck"
    SHOULDER = "shoulder"
    BACK = "back"
    CHEST = "chest"
    WRIST = "wrist"
    HANDS = "hands"
    WAIST = "waist"
    LEGS = "legs"
    FEET = "feet"
    FINGER = "finger"
    TRINKET = "trinket"
    ONE_HAND = "one_hand"
    MAIN_HAND = "main_hand"
    OFF_HAND = "off_hand"
    """An off-hand-only weapon."""
    HELD_IN_OFF_HAND = "held_in_off_hand"
    SHIELD = "shield"
    TWO_HAND = "two_hand"
    RANGED = "ranged"
    """Bows, guns, crossbows, thrown weapons and wands."""
    RELIC = "relic"
    """Librams, idols and totems, worn in the ranged slot."""


class EquipmentSlot(StrEnum):
    """A place on the character where one item is equipped."""

    HEAD = "head"
    NECK = "neck"
    SHOULDER = "shoulder"
    BACK = "back"
    CHEST = "chest"
    WRIST = "wrist"
    HANDS = "hands"
    WAIST = "waist"
    LEGS = "legs"
    FEET = "feet"
    FINGER_1 = "finger_1"
    FINGER_2 = "finger_2"
    TRINKET_1 = "trinket_1"
    TRINKET_2 = "trinket_2"
    MAIN_HAND = "main_hand"
    OFF_HAND = "off_hand"
    RANGED = "ranged"


class ArmorType(StrEnum):
    CLOTH = "cloth"
    LEATHER = "leather"
    MAIL = "mail"
    PLATE = "plate"


class WeaponType(StrEnum):
    DAGGER = "dagger"
    SWORD = "sword"
    TWO_HANDED_SWORD = "two_handed_sword"
    AXE = "axe"
    TWO_HANDED_AXE = "two_handed_axe"
    MACE = "mace"
    TWO_HANDED_MACE = "two_handed_mace"
    FIST = "fist"
    POLEARM = "polearm"
    STAFF = "staff"
    BOW = "bow"
    GUN = "gun"
    CROSSBOW = "crossbow"
    THROWN = "thrown"
    WAND = "wand"


RANGED_WEAPON_TYPES = frozenset(
    {WeaponType.BOW, WeaponType.GUN, WeaponType.CROSSBOW, WeaponType.THROWN, WeaponType.WAND}
)
TWO_HANDED_WEAPON_TYPES = frozenset(
    {
        WeaponType.TWO_HANDED_SWORD,
        WeaponType.TWO_HANDED_AXE,
        WeaponType.TWO_HANDED_MACE,
        WeaponType.POLEARM,
        WeaponType.STAFF,
    }
)


class RelicType(StrEnum):
    LIBRAM = "libram"
    IDOL = "idol"
    TOTEM = "totem"


class DamageSchool(StrEnum):
    PHYSICAL = "physical"
    ARCANE = "arcane"
    FIRE = "fire"
    FROST = "frost"
    HOLY = "holy"
    NATURE = "nature"
    SHADOW = "shadow"


class ValidationStatus(StrEnum):
    """How far a profile or formula has been checked (roadmap section 10)."""

    DRAFT = "draft"
    EXPERIMENTAL = "experimental"
    VALIDATED = "validated"


class Stat(StrEnum):
    """Every numeric property the calculator knows by name.

    Item stats are flat equip bonuses as tooltips state them: points, percentages for hit,
    crit, dodge, parry and block, skill points for defense and weapon skills. The two
    weapon-DPS keys are not item stats: they are read from an item's weapon block so that a
    profile can weight weapon damage like any other property.
    """

    STRENGTH = "strength"
    AGILITY = "agility"
    STAMINA = "stamina"
    INTELLECT = "intellect"
    SPIRIT = "spirit"

    ARMOR = "armor"
    DEFENSE = "defense"
    DODGE = "dodge"
    PARRY = "parry"
    BLOCK = "block"
    BLOCK_VALUE = "block_value"

    ATTACK_POWER = "attack_power"
    RANGED_ATTACK_POWER = "ranged_attack_power"
    FERAL_ATTACK_POWER = "feral_attack_power"
    HIT = "hit"
    CRIT = "crit"

    DAGGER_SKILL = "dagger_skill"
    SWORD_SKILL = "sword_skill"
    TWO_HANDED_SWORD_SKILL = "two_handed_sword_skill"
    AXE_SKILL = "axe_skill"
    TWO_HANDED_AXE_SKILL = "two_handed_axe_skill"
    MACE_SKILL = "mace_skill"
    TWO_HANDED_MACE_SKILL = "two_handed_mace_skill"
    FIST_SKILL = "fist_skill"
    POLEARM_SKILL = "polearm_skill"
    STAFF_SKILL = "staff_skill"
    BOW_SKILL = "bow_skill"
    GUN_SKILL = "gun_skill"
    CROSSBOW_SKILL = "crossbow_skill"

    SPELL_POWER = "spell_power"
    SPELL_DAMAGE = "spell_damage"
    """Damage from spells of every school, without healing."""
    HEALING_POWER = "healing_power"
    ARCANE_SPELL_POWER = "arcane_spell_power"
    FIRE_SPELL_POWER = "fire_spell_power"
    FROST_SPELL_POWER = "frost_spell_power"
    HOLY_SPELL_POWER = "holy_spell_power"
    NATURE_SPELL_POWER = "nature_spell_power"
    SHADOW_SPELL_POWER = "shadow_spell_power"
    SPELL_HIT = "spell_hit"
    SPELL_CRIT = "spell_crit"
    SPELL_PENETRATION = "spell_penetration"

    MP5 = "mp5"
    HP5 = "hp5"

    ARCANE_RESISTANCE = "arcane_resistance"
    FIRE_RESISTANCE = "fire_resistance"
    FROST_RESISTANCE = "frost_resistance"
    NATURE_RESISTANCE = "nature_resistance"
    SHADOW_RESISTANCE = "shadow_resistance"

    MELEE_WEAPON_DPS = "melee_weapon_dps"
    RANGED_WEAPON_DPS = "ranged_weapon_dps"


WEAPON_DPS_STATS = frozenset({Stat.MELEE_WEAPON_DPS, Stat.RANGED_WEAPON_DPS})
"""Keys computed from an item's weapon block; never stored in ``Item.stats``."""

WEAPON_SKILL_STATS: dict[WeaponType, Stat] = {
    WeaponType.DAGGER: Stat.DAGGER_SKILL,
    WeaponType.SWORD: Stat.SWORD_SKILL,
    WeaponType.TWO_HANDED_SWORD: Stat.TWO_HANDED_SWORD_SKILL,
    WeaponType.AXE: Stat.AXE_SKILL,
    WeaponType.TWO_HANDED_AXE: Stat.TWO_HANDED_AXE_SKILL,
    WeaponType.MACE: Stat.MACE_SKILL,
    WeaponType.TWO_HANDED_MACE: Stat.TWO_HANDED_MACE_SKILL,
    WeaponType.FIST: Stat.FIST_SKILL,
    WeaponType.POLEARM: Stat.POLEARM_SKILL,
    WeaponType.STAFF: Stat.STAFF_SKILL,
    WeaponType.BOW: Stat.BOW_SKILL,
    WeaponType.GUN: Stat.GUN_SKILL,
    WeaponType.CROSSBOW: Stat.CROSSBOW_SKILL,
}
