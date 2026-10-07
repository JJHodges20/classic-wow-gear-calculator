"""Normalizing Blizzard Game Data API item responses into canonical items.

The API gives primary stats and resistances as typed entries, armor and weapon damage as
blocks, and equip effects as tooltip text - which ``wow_gear.processing.tooltip`` reads, so
an item looked up online and the same item entered by hand produce the same stats.
"""

from __future__ import annotations

from datetime import datetime

from wow_gear.core.errors import DataValidationError
from wow_gear.models.enums import (
    ArmorType,
    ClassName,
    DamageSchool,
    ItemSlot,
    Race,
    RelicType,
    Stat,
    WeaponType,
)
from wow_gear.models.item import (
    EffectTrigger,
    Item,
    ItemEffect,
    Provenance,
    WeaponStats,
)
from wow_gear.models.providers.blizzard import BlizzardItem, PreviewItem
from wow_gear.processing.codes import (
    ARMOR_CLASS,
    ARMOR_SUBCLASSES,
    QUALITY_NAMES,
    RELIC_SUBCLASSES,
    WEAPON_CLASS,
    WEAPON_SUBCLASSES,
)
from wow_gear.processing.tooltip import parse_line

INVENTORY_TYPES: dict[str, ItemSlot] = {
    "HEAD": ItemSlot.HEAD,
    "NECK": ItemSlot.NECK,
    "SHOULDER": ItemSlot.SHOULDER,
    "CHEST": ItemSlot.CHEST,
    "ROBE": ItemSlot.CHEST,
    "WAIST": ItemSlot.WAIST,
    "LEGS": ItemSlot.LEGS,
    "FEET": ItemSlot.FEET,
    "WRIST": ItemSlot.WRIST,
    "HAND": ItemSlot.HANDS,
    "FINGER": ItemSlot.FINGER,
    "TRINKET": ItemSlot.TRINKET,
    "CLOAK": ItemSlot.BACK,
    "WEAPON": ItemSlot.ONE_HAND,
    "WEAPONMAINHAND": ItemSlot.MAIN_HAND,
    "WEAPONOFFHAND": ItemSlot.OFF_HAND,
    "HOLDABLE": ItemSlot.HELD_IN_OFF_HAND,
    "SHIELD": ItemSlot.SHIELD,
    "TWOHWEAPON": ItemSlot.TWO_HAND,
    "RANGED": ItemSlot.RANGED,
    "RANGEDRIGHT": ItemSlot.RANGED,
    "THROWN": ItemSlot.RANGED,
    "RELIC": ItemSlot.RELIC,
}
STAT_TYPES: dict[str, Stat] = {
    "STRENGTH": Stat.STRENGTH,
    "AGILITY": Stat.AGILITY,
    "STAMINA": Stat.STAMINA,
    "INTELLECT": Stat.INTELLECT,
    "SPIRIT": Stat.SPIRIT,
    "FIRE_RESISTANCE": Stat.FIRE_RESISTANCE,
    "NATURE_RESISTANCE": Stat.NATURE_RESISTANCE,
    "FROST_RESISTANCE": Stat.FROST_RESISTANCE,
    "SHADOW_RESISTANCE": Stat.SHADOW_RESISTANCE,
    "ARCANE_RESISTANCE": Stat.ARCANE_RESISTANCE,
}
DAMAGE_CLASSES: dict[str, DamageSchool] = {school.name: school for school in DamageSchool}
PLAYABLE_CLASSES: dict[int, ClassName] = {
    1: ClassName.WARRIOR,
    2: ClassName.PALADIN,
    3: ClassName.HUNTER,
    4: ClassName.ROGUE,
    5: ClassName.PRIEST,
    7: ClassName.SHAMAN,
    8: ClassName.MAGE,
    9: ClassName.WARLOCK,
    11: ClassName.DRUID,
}
PLAYABLE_RACES: dict[int, Race] = {
    1: Race.HUMAN,
    2: Race.ORC,
    3: Race.DWARF,
    4: Race.NIGHT_ELF,
    5: Race.UNDEAD,
    6: Race.TAUREN,
    7: Race.GNOME,
    8: Race.TROLL,
}
LICENSE = (
    "Data from Blizzard Entertainment under the Blizzard Developer API Terms of Use; "
    "kept for at most 30 days"
)


def _types(
    item: BlizzardItem, preview: PreviewItem
) -> tuple[ItemSlot, ArmorType | None, WeaponType | None, RelicType | None]:
    inventory = preview.inventory_type or item.inventory_type
    code = inventory.type if inventory else None
    if code not in INVENTORY_TYPES:
        raise DataValidationError(f"Blizzard item {item.id} is not equippable ({code})")
    slot = INVENTORY_TYPES[code]
    item_class = preview.item_class or item.item_class
    subclass = preview.item_subclass or item.item_subclass
    class_id = item_class.id if item_class else None
    subclass_id = subclass.id if subclass else None
    armor = weapon = relic = None
    if class_id == WEAPON_CLASS and subclass_id is not None:
        weapon = WEAPON_SUBCLASSES.get(subclass_id)
    elif class_id == ARMOR_CLASS and subclass_id is not None:
        if slot == ItemSlot.RELIC:
            relic = RELIC_SUBCLASSES.get(subclass_id)
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
            armor = ARMOR_SUBCLASSES.get(subclass_id)
    return slot, armor, weapon, relic


def _weapon(preview: PreviewItem) -> WeaponStats | None:
    weapon = preview.weapon
    if weapon is None or weapon.damage is None or weapon.attack_speed is None:
        return None
    damage = weapon.damage
    if damage.min_value is None or damage.max_value is None or not weapon.attack_speed.value:
        return None
    school_type = damage.damage_class.type if damage.damage_class else None
    return WeaponStats(
        min_damage=damage.min_value,
        max_damage=damage.max_value,
        speed=weapon.attack_speed.value / 1000.0,
        damage_school=DAMAGE_CLASSES.get(school_type or "PHYSICAL", DamageSchool.PHYSICAL),
    )


def normalize_blizzard_item(
    payload: BlizzardItem, *, namespace: str, region: str, fetched_at: datetime
) -> Item:
    """A Blizzard item response as a canonical item."""
    preview = payload.preview_item or PreviewItem()
    slot, armor_type, weapon_type, relic_type = _types(payload, preview)
    stats: dict[Stat, float] = {}
    equip: list[ItemEffect] = []
    use: list[ItemEffect] = []

    def add(stat: Stat, value: float) -> None:
        stats[stat] = stats.get(stat, 0.0) + value

    for entry in preview.stats:
        value = -abs(entry.value) if entry.is_negated else entry.value
        stat = STAT_TYPES.get(entry.type.type or "")
        if stat is not None:
            add(stat, value)
            continue
        text = entry.display.display_string if entry.display else None
        parsed = parse_line(text) if text else None
        if parsed is not None and parsed.recognized:
            for line in parsed.stats:
                add(line.stat, line.value)
        else:
            equip.append(
                ItemEffect(
                    trigger=EffectTrigger.EQUIP,
                    description=text or f"{entry.type.name or entry.type.type}: {value:g}",
                )
            )
    if preview.armor is not None and preview.armor.value:
        add(Stat.ARMOR, preview.armor.value)
    if preview.shield_block is not None and preview.shield_block.value:
        add(Stat.BLOCK_VALUE, preview.shield_block.value)

    for spell in preview.spells:
        text = (spell.description or "").strip()
        if not text:
            continue
        parsed = parse_line(text)
        trigger = parsed.trigger or EffectTrigger.EQUIP
        if trigger == EffectTrigger.USE:
            use.append(ItemEffect(trigger=trigger, description=text))
            continue
        if not parsed.recognized:
            equip.append(ItemEffect(trigger=trigger, description=text))
            continue
        for line in parsed.stats:
            if line.condition is None or line.condition.is_empty:
                add(line.stat, line.value)
            else:
                equip.append(
                    ItemEffect(
                        trigger=trigger,
                        description=text,
                        stat=line.stat,
                        value=line.value,
                        condition=line.condition,
                    )
                )

    requirements = preview.requirements
    classes = tuple(
        PLAYABLE_CLASSES[link.id]
        for link in (
            requirements.playable_classes.links
            if requirements and requirements.playable_classes
            else []
        )
        if link.id in PLAYABLE_CLASSES
    )
    races = tuple(
        PLAYABLE_RACES[link.id]
        for link in (
            requirements.playable_races.links
            if requirements and requirements.playable_races
            else []
        )
        if link.id in PLAYABLE_RACES
    )
    required_level = payload.required_level
    if required_level is None and requirements and requirements.level and requirements.level.value:
        required_level = int(requirements.level.value)
    item_set = preview.set.item_set if preview.set else None
    quality_type = preview.quality or payload.quality
    quality = QUALITY_NAMES.get(quality_type.type or "") if quality_type else None
    return Item(
        id=f"classic_era:{payload.id}",
        external_ids={"game": str(payload.id), "blizzard": str(payload.id)},
        name=payload.name.strip(),
        ruleset="classic_era",
        required_level=required_level or 0,
        item_level=payload.level or None,
        quality=quality,
        slot=slot,
        armor_type=armor_type,
        weapon_type=weapon_type,
        relic_type=relic_type,
        unique=bool(preview.unique_equipped),
        allowed_classes=classes,
        allowed_races=races,
        stats=stats,
        weapon=_weapon(preview),
        equip_effects=tuple(equip),
        on_use_effects=tuple(use),
        set_id=str(item_set.id) if item_set and item_set.id else None,
        set_name=item_set.name if item_set and item_set.id else None,
        provenance=Provenance(
            provider="blizzard",
            source=f"Blizzard Battle.net Game Data API ({namespace})",
            source_url=f"https://{region}.api.blizzard.com/data/wow/item/{payload.id}?namespace={namespace}",
            data_version=f"blizzard-{namespace}",
            fetched_at=fetched_at,
            license=LICENSE,
        ),
    )
