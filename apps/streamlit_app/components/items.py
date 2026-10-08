"""How an item is shown: a compact card with its type, stats as chips, what is not scored,
and where the data came from. Quality colour is secondary metadata, never the score signal."""

from __future__ import annotations

from html import escape

from components.html import chip, chips
from wow_gear.models.enums import Stat
from wow_gear.models.formatting import is_percent, stat_label
from wow_gear.models.item import Item
from wow_gear.models.labels import (
    ARMOR_LABELS,
    QUALITY_LABELS,
    RELIC_LABELS,
    SLOT_LABELS,
    weapon_label,
)
from wow_gear.models.ruleset import Ruleset

PROVIDER_LABELS = {
    "bundled": "Bundled dataset",
    "blizzard": "Blizzard API lookup",
    "manual": "Entered by hand",
    "file_import": "Imported file",
}


def type_label(item: Item) -> str:
    parts = [SLOT_LABELS[item.slot]]
    if item.armor_type is not None:
        parts.append(ARMOR_LABELS[item.armor_type])
    elif item.weapon_type is not None:
        parts.append(weapon_label(item.weapon_type))
    elif item.relic_type is not None:
        parts.append(RELIC_LABELS[item.relic_type])
    return ", ".join(parts)


def stat_text(stat: Stat, value: float, ruleset: Ruleset) -> str:
    """ "+18 Strength", "+2% Crit", "−5 Agility"."""
    sign = "+" if value >= 0 else "−"
    percent = "%" if is_percent(stat, ruleset) else ""
    return f"{sign}{abs(value):g}{percent} {stat_label(stat, ruleset)}"


def wowhead_url(item: Item) -> str | None:
    """A link for a human to check the item; the app never fetches from Wowhead."""
    game_id = item.external_ids.get("game")
    if not game_id or item.is_custom or not game_id.isdigit():
        return None
    return f"https://www.wowhead.com/classic/item={game_id}"


def summary(item: Item) -> str:
    """One line for lists: "Lionheart Helm · Head, Plate · Epic · Phase 1"."""
    bits = [item.name, type_label(item)]
    if item.quality is not None:
        bits.append(QUALITY_LABELS[item.quality])
    if item.phase is not None:
        bits.append(f"Phase {item.phase}")
    return " · ".join(bits)


def card(item: Item, ruleset: Ruleset) -> str:
    quality = item.quality.value if item.quality is not None else None
    dot = f'<span class="wg-dot wg-q-{quality}"></span>' if quality else ""
    meta = [type_label(item)]
    if item.quality is not None:
        meta.append(QUALITY_LABELS[item.quality])
    if item.phase is not None:
        meta.append(f"Phase {item.phase}")
    if item.required_level:
        meta.append(f"Requires level {item.required_level}")
    if item.allowed_classes:
        names = ", ".join(ruleset.class_def(name).label for name in item.allowed_classes)
        meta.append(f"Classes: {names}")
    if item.unique:
        meta.append("Unique")

    stat_chips = [chip(stat_text(stat, value, ruleset)) for stat, value in item.stats.items()]
    if item.weapon is not None:
        weapon = item.weapon
        stat_chips.insert(0, chip(f"{weapon.dps:.1f} damage per second", "gold"))
        stat_chips.insert(
            1, chip(f"{weapon.min_damage:g}–{weapon.max_damage:g} damage, {weapon.speed:.2f} speed")
        )

    lines = []
    for effect in item.equip_effects:
        if effect.stat is not None:
            lines.append(f"Counts when it applies: {effect.description}")
        else:
            lines.append(f"Not scored: {effect.description}")
    lines.extend(f"Not scored: {effect.description}" for effect in item.on_use_effects)
    if item.set_id is not None:
        name = item.set_name or f"item set {item.set_id}"
        lines.append(f"Part of {name}: set bonuses are not scored in version 1")
    effects = "".join(f'<div class="wg-small">{escape(line)}</div>' for line in lines)

    provenance = item.provenance
    source = PROVIDER_LABELS.get(provenance.provider, provenance.provider)
    if item.is_custom:
        source += " (theorycrafted)"
    source_bits = [escape(f"{source} · {provenance.data_version}")]
    url = wowhead_url(item)
    if url:
        source_bits.append(
            f'<a href="{escape(url)}" target="_blank" rel="noopener noreferrer">Wowhead ↗</a>'
        )
    stats_html = chips(stat_chips) or '<div class="wg-small">No stats.</div>'
    return (
        f'<div class="wg-item-name">{dot}{escape(item.name)}</div>'
        f'<div class="wg-item-meta">{escape(" · ".join(meta))}</div>'
        f"{stats_html}{effects}"
        f'<div class="wg-item-meta" style="margin-top:0.35rem">{" · ".join(source_bits)}</div>'
    )
