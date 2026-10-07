"""Manual entry: a submitted form into a canonical Item, and a pasted tooltip into a form.

A manual item takes the same path as a looked-up one: it becomes an ``Item`` here and is
validated by ``wow_gear.processing.validation`` before anything scores it.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from wow_gear.core.hashing import content_hash
from wow_gear.models.enums import (
    ArmorType,
    DamageSchool,
    ItemSlot,
    RelicType,
    Stat,
    WeaponType,
)
from wow_gear.models.forms import EffectRow, ManualItemForm
from wow_gear.models.item import (
    EffectCondition,
    EffectTrigger,
    Item,
    ItemEffect,
    Provenance,
    WeaponStats,
)
from wow_gear.processing.tooltip import parse_line

MANUAL_DATA_VERSION = "manual-1"


def _slug(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")[:40] or "item"


def _effect(row: EffectRow) -> ItemEffect:
    if row.kind == "text":
        text = row.text.strip()
        return ItemEffect(trigger=row.trigger, description=text)
    assert row.stat is not None and row.value is not None
    condition = (
        EffectCondition(target_creature_types=row.target_creature_types)
        if row.kind == "conditional_stat"
        else None
    )
    description = row.text.strip() or f"+{row.value:g} {row.stat.value.replace('_', ' ')}"
    return ItemEffect(
        trigger=row.trigger,
        description=description,
        stat=row.stat,
        value=row.value,
        condition=condition,
    )


def form_to_item(form: ManualItemForm, ruleset_id: str, *, provider: str = "manual") -> Item:
    """The canonical item a form describes. Same form, same id: entering it twice is harmless."""
    stats = dict(form.stats)
    equip: list[ItemEffect] = []
    use: list[ItemEffect] = []
    for row in form.effects:
        if row.kind == "stat" and row.trigger == EffectTrigger.EQUIP:
            assert row.stat is not None and row.value is not None
            stats[row.stat] = stats.get(row.stat, 0.0) + row.value
        elif row.trigger == EffectTrigger.USE:
            use.append(_effect(row))
        else:
            equip.append(_effect(row))
    weapon = None
    if form.has_weapon_damage:
        assert (
            form.min_damage is not None and form.max_damage is not None and form.speed is not None
        )
        weapon = WeaponStats(
            min_damage=form.min_damage,
            max_damage=form.max_damage,
            speed=form.speed,
            damage_school=form.damage_school,
        )
    fingerprint = content_hash(form.model_dump(mode="json"), length=10)
    return Item(
        id=f"custom:{_slug(form.name)}-{fingerprint}",
        name=form.name,
        ruleset=ruleset_id,
        phase=form.phase,
        required_level=form.required_level,
        quality=form.quality,
        slot=form.slot,
        armor_type=form.armor_type,
        weapon_type=form.weapon_type,
        relic_type=form.relic_type,
        stats=stats,
        weapon=weapon,
        equip_effects=tuple(equip),
        on_use_effects=tuple(use),
        set_id=f"custom:{_slug(form.set_name)}" if form.set_name else None,
        set_name=form.set_name,
        provenance=Provenance(
            provider=provider,
            source=form.source_note or ("Custom item" if form.custom else "Entered by hand"),
            data_version=MANUAL_DATA_VERSION,
            custom=form.custom,
        ),
    )


# --- pasted tooltips -----------------------------------------------------------------------

_SLOT_WORDS: dict[str, ItemSlot] = {
    "head": ItemSlot.HEAD,
    "neck": ItemSlot.NECK,
    "shoulder": ItemSlot.SHOULDER,
    "back": ItemSlot.BACK,
    "chest": ItemSlot.CHEST,
    "wrist": ItemSlot.WRIST,
    "hands": ItemSlot.HANDS,
    "waist": ItemSlot.WAIST,
    "legs": ItemSlot.LEGS,
    "feet": ItemSlot.FEET,
    "finger": ItemSlot.FINGER,
    "trinket": ItemSlot.TRINKET,
    "one-hand": ItemSlot.ONE_HAND,
    "main hand": ItemSlot.MAIN_HAND,
    "off hand": ItemSlot.OFF_HAND,
    "held in off-hand": ItemSlot.HELD_IN_OFF_HAND,
    "two-hand": ItemSlot.TWO_HAND,
    "ranged": ItemSlot.RANGED,
    "thrown": ItemSlot.RANGED,
    "relic": ItemSlot.RELIC,
}
_ARMOR_WORDS = {
    "cloth": ArmorType.CLOTH,
    "leather": ArmorType.LEATHER,
    "mail": ArmorType.MAIL,
    "plate": ArmorType.PLATE,
}
_WEAPON_WORDS = {
    "dagger": WeaponType.DAGGER,
    "sword": WeaponType.SWORD,
    "axe": WeaponType.AXE,
    "mace": WeaponType.MACE,
    "fist weapon": WeaponType.FIST,
    "polearm": WeaponType.POLEARM,
    "staff": WeaponType.STAFF,
    "bow": WeaponType.BOW,
    "gun": WeaponType.GUN,
    "crossbow": WeaponType.CROSSBOW,
    "thrown": WeaponType.THROWN,
    "wand": WeaponType.WAND,
}
_TWO_HANDED = {
    WeaponType.SWORD: WeaponType.TWO_HANDED_SWORD,
    WeaponType.AXE: WeaponType.TWO_HANDED_AXE,
    WeaponType.MACE: WeaponType.TWO_HANDED_MACE,
}
_RELIC_WORDS = {"libram": RelicType.LIBRAM, "idol": RelicType.IDOL, "totem": RelicType.TOTEM}
_IGNORED = re.compile(
    r"^(soulbound|binds when (picked up|equipped|used)|unique|durability \d+ / \d+|"
    r"classes: .*|races: .*|item level \d+|sell price.*|\(\d+(\.\d+)? damage per second\)|<.*>)$",
    re.IGNORECASE,
)


@dataclass
class TooltipReading:
    """What a pasted tooltip says, and the lines the reader could not place."""

    form: ManualItemForm | None
    unrecognized: list[str] = field(default_factory=list)
    problems: list[str] = field(default_factory=list)


def _slot_line(
    line: str,
) -> tuple[ItemSlot, ArmorType | None, WeaponType | None, RelicType | None] | None:
    words = re.split(r"\s{2,}|\t", line.strip().lower())
    slot = _SLOT_WORDS.get(words[0])
    if slot is None:
        return None
    kind = words[1] if len(words) > 1 else ""
    armor = _ARMOR_WORDS.get(kind)
    weapon = _WEAPON_WORDS.get(kind)
    relic = _RELIC_WORDS.get(kind)
    if slot == ItemSlot.OFF_HAND and kind == "shield":
        slot = ItemSlot.SHIELD
    if slot == ItemSlot.TWO_HAND and weapon in _TWO_HANDED:
        weapon = _TWO_HANDED[weapon]
    if words[0] == "thrown":
        weapon = WeaponType.THROWN
    return slot, armor, weapon, relic


def read_tooltip(text: str, *, custom: bool = False) -> TooltipReading:
    """Best-effort reading of a copied tooltip into a form. The first line is the name."""
    lines = [line.strip() for line in text.replace("\r", "").split("\n") if line.strip()]
    if not lines:
        return TooltipReading(form=None, problems=["The tooltip is empty."])
    name, rest = lines[0], lines[1:]
    reading = TooltipReading(form=None)
    slot_info = None
    stats: dict[Stat, float] = {}
    effects: list[EffectRow] = []
    weapon: dict[str, float] = {}
    school = DamageSchool.PHYSICAL
    required_level = 0
    for line in rest:
        if slot_info is None and (found := _slot_line(line)) is not None:
            slot_info = found
            continue
        damage = re.match(
            r"^(\d+(?:\.\d+)?)\s*-\s*(\d+(?:\.\d+)?)\s+(?:(\w+)\s+)?damage\s+speed\s+(\d+(?:\.\d+)?)$",
            line,
            re.IGNORECASE,
        )
        if damage:
            weapon = {
                "min": float(damage.group(1)),
                "max": float(damage.group(2)),
                "speed": float(damage.group(4)),
            }
            if damage.group(3) and damage.group(3).lower() in {s.value for s in DamageSchool}:
                school = DamageSchool(damage.group(3).lower())
            continue
        level = re.match(r"^requires level (\d+)$", line, re.IGNORECASE)
        if level:
            required_level = int(level.group(1))
            continue
        if _IGNORED.match(line):
            continue
        parsed = parse_line(line)
        if parsed.recognized and len(parsed.stats) >= 1:
            conditional = [s for s in parsed.stats if s.condition is not None]
            if conditional:
                for stat_line in conditional:
                    condition = stat_line.condition
                    assert condition is not None
                    if condition.target_creature_types:
                        effects.append(
                            EffectRow(
                                kind="conditional_stat",
                                stat=stat_line.stat,
                                value=stat_line.value,
                                target_creature_types=condition.target_creature_types,
                                text=line,
                            )
                        )
                    else:
                        effects.append(EffectRow(kind="text", text=line))
            else:
                for stat_line in parsed.stats:
                    stats[stat_line.stat] = stats.get(stat_line.stat, 0.0) + stat_line.value
            continue
        if parsed.trigger is not None:
            effects.append(EffectRow(kind="text", trigger=parsed.trigger, text=line))
            continue
        reading.unrecognized.append(line)
    if slot_info is None:
        reading.problems.append('No slot line (such as "Head  Plate") was found; choose the slot.')
        return reading
    slot, armor, weapon_type, relic = slot_info
    reading.form = ManualItemForm(
        name=name,
        slot=slot,
        armor_type=armor,
        weapon_type=weapon_type,
        relic_type=relic,
        required_level=required_level,
        stats=stats,
        min_damage=weapon.get("min"),
        max_damage=weapon.get("max"),
        speed=weapon.get("speed"),
        damage_school=school,
        effects=tuple(effects),
        custom=custom,
        source_note="Pasted tooltip",
    )
    return reading
