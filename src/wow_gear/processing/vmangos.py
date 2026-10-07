"""Normalizing VMaNGOS item rows into canonical items.

Every mapping is a table here, so a reader can check it: inventory types into slots, item
classes into armor and weapon types, class and race masks into restrictions, and equip-spell
auras into stats. An equip spell whose auras all map becomes stats; any other spell keeps its
tooltip text as an effect the calculator reports and does not score.

The phase heuristic (docs/research/DATA_SOURCES.md and the patch history at
https://warcraft.wiki.gg/wiki/Patches/1.x): an item that drops in a raid or from a world
boss takes the phase that content opened in; any other item takes the phase of the first
patch it exists in. Classic opened raids with their final (1.12) loot tables, so a Molten
Core item VMaNGOS dates to a later patch is still phase 1.
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from wow_gear.core.errors import DataValidationError
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
from wow_gear.models.item import (
    BonusDamage,
    EffectCondition,
    EffectTrigger,
    Item,
    ItemEffect,
    Provenance,
    WeaponStats,
)
from wow_gear.processing.codes import ARMOR_SUBCLASSES, RELIC_SUBCLASSES, WEAPON_SUBCLASSES

Row = Mapping[str, Any]

INVENTORY_SLOTS: dict[int, ItemSlot] = {
    1: ItemSlot.HEAD,
    2: ItemSlot.NECK,
    3: ItemSlot.SHOULDER,
    5: ItemSlot.CHEST,
    6: ItemSlot.WAIST,
    7: ItemSlot.LEGS,
    8: ItemSlot.FEET,
    9: ItemSlot.WRIST,
    10: ItemSlot.HANDS,
    11: ItemSlot.FINGER,
    12: ItemSlot.TRINKET,
    13: ItemSlot.ONE_HAND,
    14: ItemSlot.SHIELD,
    15: ItemSlot.RANGED,
    16: ItemSlot.BACK,
    17: ItemSlot.TWO_HAND,
    20: ItemSlot.CHEST,
    21: ItemSlot.MAIN_HAND,
    22: ItemSlot.OFF_HAND,
    23: ItemSlot.HELD_IN_OFF_HAND,
    25: ItemSlot.RANGED,
    26: ItemSlot.RANGED,
    28: ItemSlot.RELIC,
}
QUALITIES: dict[int, ItemQuality] = {
    0: ItemQuality.POOR,
    1: ItemQuality.COMMON,
    2: ItemQuality.UNCOMMON,
    3: ItemQuality.RARE,
    4: ItemQuality.EPIC,
    5: ItemQuality.LEGENDARY,
}
CLASS_BITS: dict[int, ClassName] = {
    1: ClassName.WARRIOR,
    2: ClassName.PALADIN,
    4: ClassName.HUNTER,
    8: ClassName.ROGUE,
    16: ClassName.PRIEST,
    64: ClassName.SHAMAN,
    128: ClassName.MAGE,
    256: ClassName.WARLOCK,
    1024: ClassName.DRUID,
}
RACE_BITS: dict[int, Race] = {
    1: Race.HUMAN,
    2: Race.ORC,
    4: Race.DWARF,
    8: Race.NIGHT_ELF,
    16: Race.UNDEAD,
    32: Race.TAUREN,
    64: Race.GNOME,
    128: Race.TROLL,
}
ITEM_STATS: dict[int, Stat] = {
    3: Stat.AGILITY,
    4: Stat.STRENGTH,
    5: Stat.INTELLECT,
    6: Stat.SPIRIT,
    7: Stat.STAMINA,
}
UNSCORED_ITEM_STATS = {0: "Mana", 1: "Health"}
DAMAGE_SCHOOLS: dict[int, DamageSchool] = {
    0: DamageSchool.PHYSICAL,
    1: DamageSchool.HOLY,
    2: DamageSchool.FIRE,
    3: DamageSchool.NATURE,
    4: DamageSchool.FROST,
    5: DamageSchool.SHADOW,
    6: DamageSchool.ARCANE,
}
RESISTANCE_COLUMNS: dict[str, Stat] = {
    "fire_res": Stat.FIRE_RESISTANCE,
    "nature_res": Stat.NATURE_RESISTANCE,
    "frost_res": Stat.FROST_RESISTANCE,
    "shadow_res": Stat.SHADOW_RESISTANCE,
    "arcane_res": Stat.ARCANE_RESISTANCE,
}
SCHOOL_BITS: dict[int, Stat] = {
    2: Stat.HOLY_SPELL_POWER,
    4: Stat.FIRE_SPELL_POWER,
    8: Stat.NATURE_SPELL_POWER,
    16: Stat.FROST_SPELL_POWER,
    32: Stat.SHADOW_SPELL_POWER,
    64: Stat.ARCANE_SPELL_POWER,
}
RESISTANCE_BITS: dict[int, Stat] = {
    1: Stat.ARMOR,
    4: Stat.FIRE_RESISTANCE,
    8: Stat.NATURE_RESISTANCE,
    16: Stat.FROST_RESISTANCE,
    32: Stat.SHADOW_RESISTANCE,
    64: Stat.ARCANE_RESISTANCE,
}
PRIMARY_STAT_INDEX: dict[int, Stat] = {
    0: Stat.STRENGTH,
    1: Stat.AGILITY,
    2: Stat.STAMINA,
    3: Stat.INTELLECT,
    4: Stat.SPIRIT,
}
SKILLS: dict[int, Stat] = {
    95: Stat.DEFENSE,
    43: Stat.SWORD_SKILL,
    55: Stat.TWO_HANDED_SWORD_SKILL,
    44: Stat.AXE_SKILL,
    172: Stat.TWO_HANDED_AXE_SKILL,
    54: Stat.MACE_SKILL,
    160: Stat.TWO_HANDED_MACE_SKILL,
    473: Stat.FIST_SKILL,
    229: Stat.POLEARM_SKILL,
    136: Stat.STAFF_SKILL,
    173: Stat.DAGGER_SKILL,
    45: Stat.BOW_SKILL,
    46: Stat.GUN_SKILL,
    226: Stat.CROSSBOW_SKILL,
}
CREATURE_BITS: dict[int, CreatureType] = {
    1: CreatureType.BEAST,
    2: CreatureType.DRAGONKIN,
    4: CreatureType.DEMON,
    8: CreatureType.ELEMENTAL,
    16: CreatureType.GIANT,
    32: CreatureType.UNDEAD,
    64: CreatureType.HUMANOID,
    256: CreatureType.MECHANICAL,
}
ALL_MAGIC = (124, 126, 127)
"""School masks meaning every magic school (124 leaves out Holy)."""
ALL_CLASSES_MASK = sum(CLASS_BITS)
ALL_RACES_MASK = sum(RACE_BITS)

RAID_PHASES: dict[int, int] = {409: 1, 249: 1, 469: 3, 309: 4, 509: 5, 531: 5, 533: 6}
"""Raid map id to the Classic phase it opened in (Molten Core, Onyxia's Lair, Blackwing
Lair, Zul'Gurub, Ruins and Temple of Ahn'Qiraj, Naxxramas)."""
WORLD_BOSS_PHASES: dict[int, int] = {6109: 2, 12397: 2, 14887: 4, 14888: 4, 14889: 4, 14890: 4}
"""World boss creature id to phase: Azuregos and Lord Kazzak (2), the Dragons of Nightmare (4)."""
PATCH_PHASES: dict[int, int] = {0: 1, 1: 2, 2: 2, 3: 3, 4: 3, 5: 4, 6: 4, 7: 5, 8: 5, 9: 6, 10: 6}
"""VMaNGOS patch index (0 = 1.2 ... 10 = 1.12) to the Classic phase that brought its content."""


@dataclass(frozen=True)
class SourceInfo:
    """Where an item comes from, reduced to what the phase heuristic needs."""

    raid_or_world_boss_phase: int | None = None


def phase_for(first_patch: int, source: SourceInfo) -> int:
    if source.raid_or_world_boss_phase is not None:
        return source.raid_or_world_boss_phase
    return PATCH_PHASES.get(first_patch, max(PATCH_PHASES.values()))


def _effect_value(spell: Row, index: int) -> float:
    base = spell.get(f"effectBasePoints{index}") or 0
    dice = spell.get(f"effectDieSides{index}") or 0
    return float(base + dice)


def render_description(spell: Row) -> str:
    """The spell's tooltip text with its numbers filled in."""
    text = str(spell.get("description") or "").strip()

    def value(match: re.Match[str]) -> str:
        divisor = match.group(1)
        index = int(match.group(3))
        number = abs(_effect_value(spell, index))
        if divisor:
            number /= float(divisor)
        return f"{number:g}"

    text = re.sub(r"\$(?:/(\d+);)?(\d+)?s([123])", value, text)
    text = re.sub(
        r"\$m([123])", lambda m: f"{abs(_effect_value(spell, int(m.group(1)))):g}", text, flags=re.I
    )
    text = text.replace("$h", f"{spell.get('procChance') or 0:g}")
    # Durations and totals over time live in client tables the snapshot does not have.
    text = re.sub(r"\$o[123]", "[amount]", text)
    text = re.sub(r"\$d(?![a-z])", "[duration]", text)
    return re.sub(r"\s+", " ", text) or str(spell.get("name") or "Unnamed effect")


def _mask(value: int, bits: Mapping[int, Any]) -> list[Any]:
    return [entry for bit, entry in bits.items() if value & bit]


def _creatures(mask: int) -> tuple[CreatureType, ...]:
    return tuple(_mask(mask, CREATURE_BITS))


MappedStat = tuple[Stat, float, EffectCondition | None]


def map_spell(spell: Row) -> list[MappedStat] | None:
    """The stats an equip spell grants, or None when any of its effects is not a plain stat."""
    auras = {}
    for index in (1, 2, 3):
        aura = spell.get(f"effectApplyAuraName{index}") or 0
        if aura:
            auras[index] = (
                aura,
                spell.get(f"effectMiscValue{index}") or 0,
                _effect_value(spell, index),
            )
    if not auras:
        return None
    kinds = {aura for aura, _, _ in auras.values()}
    description = str(spell.get("description") or "").lower()
    mapped: list[MappedStat] = []
    damage = next((v for a, m, v in auras.values() if a == 13 and m in ALL_MAGIC), None)
    healing = next((v for a, _, v in auras.values() if a == 135), None)
    if damage is not None and healing is not None:
        # "Damage and healing by up to X": the shared amount is spell power; any excess
        # of one over the other counts for damage only or healing only.
        shared = min(damage, healing)
        mapped.append((Stat.SPELL_POWER, shared, None))
        if damage > shared:
            mapped.append((Stat.SPELL_DAMAGE, damage - shared, None))
        if healing > shared:
            mapped.append((Stat.HEALING_POWER, healing - shared, None))
        auras = {
            index: entry
            for index, entry in auras.items()
            if not (entry[0] == 135 or (entry[0] == 13 and entry[1] in ALL_MAGIC))
        }
    for aura, misc, value in auras.values():
        result = _map_aura(aura, misc, value, kinds, description)
        if result is None:
            return None
        mapped.extend(result)
    return mapped


def _map_aura(
    aura: int, misc: int, value: float, kinds: set[int], description: str
) -> list[MappedStat] | None:
    simple = {
        54: Stat.HIT,
        55: Stat.SPELL_HIT,
        57: Stat.SPELL_CRIT,
        49: Stat.DODGE,
        47: Stat.PARRY,
        51: Stat.BLOCK,
        158: Stat.BLOCK_VALUE,
    }
    if aura in simple:
        return [(simple[aura], value, None)]
    if aura == 52:  # crit; some spells restrict it to ranged ("missile") weapons
        return None if "missile" in description else [(Stat.CRIT, value, None)]
    if aura == 29:  # a primary stat; -1 means every one
        if misc == -1:
            return [(stat, value, None) for stat in PRIMARY_STAT_INDEX.values()]
        stat = PRIMARY_STAT_INDEX.get(misc)
        return [(stat, value, None)] if stat else None
    if aura == 22:  # armor or resistance by school mask
        stats = _mask(misc, RESISTANCE_BITS)
        return [(stat, value, None) for stat in stats] if stats else None
    if aura == 13:  # spell damage, all schools or one
        if misc in ALL_MAGIC:
            return [(Stat.SPELL_DAMAGE, value, None)]
        stats = _mask(misc, SCHOOL_BITS)
        return [(stat, value, None) for stat in stats] if len(stats) == 1 else None
    if aura == 135:  # healing only (with all-school damage it was handled above)
        return [(Stat.HEALING_POWER, value, None)]
    if aura == 71:  # spell crit by school
        return [(Stat.SPELL_CRIT, value, None)] if misc in ALL_MAGIC else None
    if aura == 99:  # melee attack power; alone, with a forms description, feral
        if 124 not in kinds and "cat" in description and "bear" in description:
            forms = EffectCondition(shapeshift_forms=("cat", "bear", "dire_bear"))
            return [(Stat.FERAL_ATTACK_POWER, value, forms)]
        return [(Stat.ATTACK_POWER, value, None)]
    if aura == 124:  # ranged attack power ("+X Attack Power" carries both 99 and 124)
        return [(Stat.RANGED_ATTACK_POWER, value, None)]
    if aura in (102, 131):  # melee (102) or ranged (131) attack power against creature types
        stat = Stat.ATTACK_POWER if aura == 102 else Stat.RANGED_ATTACK_POWER
        condition = EffectCondition(target_creature_types=_creatures(misc))
        return [(stat, value, condition)] if condition.target_creature_types else None
    if aura == 180:  # spell damage against creature types
        condition = EffectCondition(target_creature_types=_creatures(misc))
        return [(Stat.SPELL_DAMAGE, value, condition)] if condition.target_creature_types else None
    if aura == 30:  # defense or a weapon skill
        stat = SKILLS.get(misc)
        return [(stat, value, None)] if stat else None
    if aura == 85 and misc == 0:
        return [(Stat.MP5, value, None)]
    if aura == 161:
        return [(Stat.HP5, value, None)]
    if aura == 123:  # spell penetration (stored as a negative resistance change)
        return [(Stat.SPELL_PENETRATION, abs(value), None)] if misc in ALL_MAGIC else None
    return None


def _restrictions(mask: int, bits: Mapping[int, Any], everyone: int) -> tuple[Any, ...]:
    if mask <= 0 or (mask & everyone) == everyone:
        return ()
    return tuple(_mask(mask, bits))


def _types(row: Row) -> tuple[ItemSlot, ArmorType | None, WeaponType | None, RelicType | None]:
    slot = INVENTORY_SLOTS[row["inventory_type"]]
    item_class, subclass = row["class"], row["subclass"]
    armor = weapon = relic = None
    if item_class == 2:
        weapon = WEAPON_SUBCLASSES.get(subclass)
    elif item_class == 4:
        if slot == ItemSlot.RELIC:
            relic = RELIC_SUBCLASSES.get(subclass)
        elif slot in (
            ItemSlot.HEAD,
            ItemSlot.SHOULDER,
            ItemSlot.BACK,
            ItemSlot.CHEST,
            ItemSlot.WRIST,
            ItemSlot.HANDS,
            ItemSlot.WAIST,
            ItemSlot.LEGS,
            ItemSlot.FEET,
        ):
            armor = ARMOR_SUBCLASSES.get(subclass)
    return slot, armor, weapon, relic


def _weapon(row: Row) -> WeaponStats | None:
    if not row.get("delay") or not row.get("dmg_max1"):
        return None
    bonus = []
    for index in range(2, 6):
        low, high = row.get(f"dmg_min{index}") or 0, row.get(f"dmg_max{index}") or 0
        if high:
            bonus.append(
                BonusDamage(
                    min_damage=low,
                    max_damage=high,
                    school=DAMAGE_SCHOOLS.get(
                        row.get(f"dmg_type{index}") or 0, DamageSchool.PHYSICAL
                    ),
                )
            )
    return WeaponStats(
        min_damage=row["dmg_min1"],
        max_damage=row["dmg_max1"],
        speed=row["delay"] / 1000.0,
        damage_school=DAMAGE_SCHOOLS.get(row.get("dmg_type1") or 0, DamageSchool.PHYSICAL),
        bonus_damage=tuple(bonus),
    )


def _cooldown(milliseconds: object) -> float | None:
    """A use cooldown in seconds; VMaNGOS writes -1 for \"the spell's own cooldown\"."""
    if isinstance(milliseconds, int | float) and milliseconds > 0:
        return float(milliseconds) / 1000
    return None


def normalize_item(
    row: Row,
    spells: Mapping[int, Row],
    *,
    source: SourceInfo,
    provenance: Provenance,
) -> Item:
    """One VMaNGOS ``item_template`` row (with ``first_patch``) as a canonical item."""
    if row["inventory_type"] not in INVENTORY_SLOTS:
        raise DataValidationError(f"item {row['entry']} is not equippable")
    quality = QUALITIES.get(row["quality"])
    if quality is None:
        raise DataValidationError(f"item {row['entry']} has quality {row['quality']}")
    slot, armor_type, weapon_type, relic_type = _types(row)
    stats: dict[Stat, float] = {}
    equip: list[ItemEffect] = []
    use: list[ItemEffect] = []

    def add(stat: Stat, value: float) -> None:
        stats[stat] = stats.get(stat, 0.0) + value

    for index in range(1, 11):
        kind, value = row.get(f"stat_type{index}"), row.get(f"stat_value{index}") or 0
        if not value or kind is None:
            continue
        if kind in ITEM_STATS:
            add(ITEM_STATS[kind], value)
        elif kind in UNSCORED_ITEM_STATS:
            equip.append(
                ItemEffect(
                    trigger=EffectTrigger.EQUIP,
                    description=f"+{value} {UNSCORED_ITEM_STATS[kind]}",
                )
            )
    if row.get("armor"):
        add(Stat.ARMOR, row["armor"])
    if row.get("block"):
        add(Stat.BLOCK_VALUE, row["block"])
    for column, stat in RESISTANCE_COLUMNS.items():
        if row.get(column):
            add(stat, row[column])
    if row.get("holy_res"):
        equip.append(
            ItemEffect(
                trigger=EffectTrigger.EQUIP, description=f"+{row['holy_res']} Holy Resistance"
            )
        )

    for index in range(1, 6):
        spell_id, trigger = row.get(f"spellid_{index}") or 0, row.get(f"spelltrigger_{index}")
        if not spell_id:
            continue
        spell = spells.get(spell_id)
        text = render_description(spell) if spell else f"Spell {spell_id}"
        if trigger == 0:
            use.append(
                ItemEffect(
                    trigger=EffectTrigger.USE,
                    description=f"Use: {text}",
                    cooldown_seconds=_cooldown(row.get(f"spellcooldown_{index}")),
                )
            )
            continue
        if trigger == 2:
            ppm = row.get(f"spellppmrate_{index}") or None
            equip.append(
                ItemEffect(
                    trigger=EffectTrigger.CHANCE_ON_HIT,
                    description=f"Chance on hit: {text}",
                    procs_per_minute=ppm,
                )
            )
            continue
        mapped = map_spell(spell) if spell else None
        if mapped is None:
            equip.append(ItemEffect(trigger=EffectTrigger.EQUIP, description=f"Equip: {text}"))
            continue
        for stat, value, condition in mapped:
            if condition is None:
                add(stat, value)
            else:
                equip.append(
                    ItemEffect(
                        trigger=EffectTrigger.EQUIP,
                        description=f"Equip: {text}",
                        stat=stat,
                        value=value,
                        condition=condition,
                    )
                )

    entry = int(row["entry"])
    return Item(
        id=f"classic_era:{entry}",
        external_ids={"game": str(entry), "vmangos": str(entry)},
        name=str(row["name"]).strip(),
        ruleset="classic_era",
        phase=phase_for(int(row.get("first_patch") or 0), source),
        required_level=int(row.get("required_level") or 0),
        item_level=int(row["item_level"]) if row.get("item_level") else None,
        quality=quality,
        slot=slot,
        armor_type=armor_type,
        weapon_type=weapon_type,
        relic_type=relic_type,
        unique=row.get("max_count") == 1,
        allowed_classes=_restrictions(
            int(row.get("allowable_class") or -1), CLASS_BITS, ALL_CLASSES_MASK
        ),
        allowed_races=_restrictions(
            int(row.get("allowable_race") or -1), RACE_BITS, ALL_RACES_MASK
        ),
        stats=stats,
        weapon=_weapon(row)
        if slot
        in (
            ItemSlot.ONE_HAND,
            ItemSlot.MAIN_HAND,
            ItemSlot.OFF_HAND,
            ItemSlot.TWO_HAND,
            ItemSlot.RANGED,
        )
        else None,
        equip_effects=tuple(equip),
        on_use_effects=tuple(use),
        set_id=str(row["set_id"]) if row.get("set_id") else None,
        provenance=provenance,
    )


def source_info(
    loot: Iterable[Any], *, world_boss_phases: Mapping[int, int] = WORLD_BOSS_PHASES
) -> SourceInfo:
    """Reduce an item's loot sources to the earliest raid or world-boss phase, if any."""
    phases = []
    for source in loot:
        if source.map_id in RAID_PHASES:
            phases.append(RAID_PHASES[source.map_id])
        elif source.source_kind == "creature" and source.source_entry in world_boss_phases:
            phases.append(world_boss_phases[source.source_entry])
    return SourceInfo(raid_or_world_boss_phase=min(phases) if phases else None)


def vmangos_provenance(snapshot: str, built_at: datetime) -> Provenance:
    return Provenance(
        provider="bundled",
        source=f"VMaNGOS world database, development snapshot {snapshot} (patch 1.12 rows)",
        source_url="https://github.com/vmangos/core/releases/tag/db_latest",
        data_version=f"classic_era-vmangos-{snapshot}",
        fetched_at=built_at,
        license="VMaNGOS is GPL-2.0; the game data is Blizzard Entertainment's",
    )
