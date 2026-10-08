"""How a gear set is shown: each slot with its item and what it is worth, the caps as bars,
where the value comes from, and a replacement's effect. Every number comes from the gear
analysis; nothing here computes a game value."""

from __future__ import annotations

from html import escape

from components import layout
from components.html import Tone, chip, eyebrow, signed, tone_of
from components.items import type_label
from wow_gear.models.enums import EquipmentSlot, Stat
from wow_gear.models.formatting import amount_text, stat_label
from wow_gear.models.gear import CapStatus, GearAnalysis, ReplacementResult, SlotValue
from wow_gear.models.item import Item
from wow_gear.models.labels import EQUIPMENT_SLOT_LABELS
from wow_gear.models.ruleset import Ruleset

STATE_LABELS = {"short": "Short", "reached": "Reached", "over": "Over"}
STATE_TONES: dict[str, Tone] = {"short": "gold", "reached": "good", "over": "bad"}


def slot_html(
    slot: EquipmentSlot, item: Item | None, worth: str = "", note: str | None = None
) -> str:
    """A slot: its name and what the piece is worth, then the item worn (or why there is none)."""
    head = f'<div class="wg-slot-top">{eyebrow(EQUIPMENT_SLOT_LABELS[slot])}{worth}</div>'
    if item is None:
        text = escape(note or "Empty")
        return (
            f'<div class="wg-slot">{head}<div class="wg-slot-name wg-slot-none">{text}</div></div>'
        )
    quality = item.quality.value if item.quality is not None else None
    dot = f'<span class="wg-dot wg-q-{quality}"></span>' if quality else ""
    meta = type_label(item)
    if item.item_level is not None:
        meta += f" · item level {item.item_level}"
    return (
        f'<div class="wg-slot">{head}<div class="wg-slot-name" title="{escape(item.name)}">'
        f"{dot}{escape(item.name)}</div>"
        f'<div class="wg-item-meta wg-slot-meta">{escape(meta)}</div></div>'
    )


def worth_chip(value: SlotValue | None, unit: str) -> str:
    if value is None:
        return ""
    if not value.eligible:
        return chip("Not usable", "bad", title="; ".join(value.reasons))
    tone: Tone = "gold" if value.score > 0.05 else "muted"
    return chip(
        f"{value.score:.1f} {unit}",
        tone,
        title="What the character would lose without it, with the rest of the gear as it is.",
    )


def _bar(status: CapStatus) -> str:
    share = 1.0 if status.target <= 0 else min(1.0, max(0.0, status.total / status.target))
    tone = STATE_TONES[status.state]
    return f'<div class="wg-bar wg-{tone}"><span style="width:{share * 100:.1f}%"></span></div>'


def caps_html(caps: tuple[CapStatus, ...]) -> str:
    if not caps:
        return (
            '<div class="wg-small">This profile has no cap or breakpoint: every point of a '
            "valued stat counts the same.</div>"
        )
    rows = []
    for status in caps:
        rows.append(
            '<div class="wg-cap"><div class="wg-cap-head">'
            f"<span><b>{escape(status.label)}</b> "
            f'<span class="wg-small">{escape(status.kind)}</span></span>'
            f"{chip(STATE_LABELS[status.state], STATE_TONES[status.state])}</div>"
            f"{_bar(status)}"
            f'<div class="wg-small">{escape(status.message)}</div></div>'
        )
    return "".join(rows)


def value_table(analysis: GearAnalysis, ruleset: Ruleset) -> str:
    """Where the gear's value comes from, largest first, with each part's share."""
    parts = [c for c in analysis.components if abs(c.contribution) > 0.005]
    if not parts:
        return '<div class="wg-small">Nothing in this gear is valued by the profile.</div>'
    total = sum(abs(c.contribution) for c in parts) or 1.0
    unit = escape(analysis.unit_abbreviation)
    rows = "".join(
        f"<tr><td>{escape(c.label)}"
        f'<div class="wg-bar wg-gold"><span style="width:{abs(c.contribution) / total * 100:.1f}%">'
        "</span></div></td>"
        f'<td class="wg-num">{escape(amount_text(c.stat, c.amount, ruleset))}</td>'
        f'<td class="wg-num"><b>{c.contribution:.1f}</b></td></tr>'
        for c in parts
    )
    return (
        '<table class="wg-table"><thead><tr><th>Component</th><th class="wg-num">Amount</th>'
        f'<th class="wg-num">Value ({unit})</th></tr></thead><tbody>{rows}</tbody></table>'
    )


def totals_table(totals: dict[Stat, float], ruleset: Ruleset) -> str:
    rows = "".join(
        f"<tr><td>{escape(stat_label(stat, ruleset))}</td>"
        f'<td class="wg-num">{escape(amount_text(stat, value, ruleset))}</td></tr>'
        for stat, value in totals.items()
    )
    return (
        '<table class="wg-table"><thead><tr><th>Stat</th><th class="wg-num">From gear</th>'
        f"</tr></thead><tbody>{rows}</tbody></table>"
    )


def replacement_html(result: ReplacementResult) -> str:
    """The verdict on a replacement for the whole character, before the why."""
    unit = result.unit_abbreviation
    better = result.eligible and result.outcome == "better"
    if not result.eligible:
        badge = chip("Not usable", "bad")
    elif result.outcome == "better":
        badge = chip("Better for the whole character", "gold")
    elif result.outcome == "worse":
        badge = chip("Worse for the whole character", "bad")
    else:
        badge = chip("Effectively the same", "muted")
    removed = " and ".join(result.removed) if result.removed else "nothing (the slot is empty)"
    tiles = layout.tiles_html(
        [
            layout.Tile("Change", signed(result.delta), unit, tone=tone_of(result.delta)),
            layout.Tile("Gear value now", f"{result.score_before:.1f}", unit),
            layout.Tile("With it", f"{result.score_after:.1f}", unit),
        ]
    )
    return (
        f'<div class="wg-verdict{"" if better else " wg-neutral"}">'
        f"{badge}"
        f'<div class="wg-winner">{escape(result.candidate_name)}</div>'
        f'<div class="wg-sub">In the {escape(EQUIPMENT_SLOT_LABELS[result.slot].lower())} slot, '
        f"replacing {escape(removed)}.</div></div>{tiles}"
    )


def cap_changes(result: ReplacementResult) -> list[str]:
    """How the replacement moves each cap: "Melee hit cap: 6% → 9%; 7% from gear (now short)"."""
    before = {(s.stat, s.label): s for s in result.caps_before}
    lines = []
    for after in result.caps_after:
        old = before.get((after.stat, after.label))
        if old is None:
            continue
        unit = "%" if after.percent else ""
        state = STATE_LABELS[after.state].lower()
        total_moved = abs(old.total - after.total) > 1e-9
        target_moved = abs(old.target - after.target) > 1e-9
        if target_moved and total_moved:
            lines.append(
                f"{after.label}: {old.target:g}{unit} → {after.target:g}{unit}; from gear "
                f"{old.total:g}{unit} → {after.total:g}{unit} (now {state})"
            )
        elif target_moved:
            lines.append(
                f"{after.label}: {old.target:g}{unit} → {after.target:g}{unit}; "
                f"{after.total:g}{unit} from gear (now {state})"
            )
        elif total_moved or old.state != after.state:
            lines.append(
                f"{after.label} ({after.target:g}{unit}): from gear {old.total:g}{unit} → "
                f"{after.total:g}{unit} (now {state})"
            )
    return lines
