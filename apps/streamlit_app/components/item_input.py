"""Choosing an item for slot A or B: search the item data, or enter one by hand.

Search looks in the local data first; the online lookup is a toggle, and when it is off,
not configured or failing, the page says so and keeps the local results. A manual item is
previewed with its validation before it can be used, exactly as the roadmap's path A asks.
"""

from __future__ import annotations

import streamlit as st
from pydantic import ValidationError

from components import items
from components.html import eyebrow
from state import session
from state.session import Slot
from wow_gear.models.enums import (
    ArmorType,
    ItemQuality,
    ItemSlot,
    RelicType,
    Stat,
    WeaponType,
)
from wow_gear.models.forms import EffectRow, ManualItemForm
from wow_gear.models.item import Item
from wow_gear.models.labels import (
    ARMOR_LABELS,
    QUALITY_LABELS,
    RELIC_LABELS,
    SLOT_LABELS,
    weapon_label,
)
from wow_gear.models.ruleset import Ruleset
from wow_gear.services.item_entry import EntryPreview
from wow_gear.services.item_search import ItemFilters
from wow_gear.services.workspace import Workspace

SEARCH, MANUAL = "Search", "Enter manually"
ANY_SLOT = "any"
NOT_GIVEN = "not_given"
PRIMARY_GROUPS = 2
"""How many stat groups the manual form shows open; the rest sit in an expander."""


def render(slot: Slot, workspace: Workspace, ruleset: Ruleset, other: Item | None) -> None:
    chosen = session.item(slot)
    with st.container(border=True):
        top = st.container(
            horizontal=True, horizontal_alignment="distribute", vertical_alignment="center"
        )
        top.html(eyebrow(f"Item {slot}"), width="content")
        if chosen is not None:
            if top.button("Change", key=f"change_{slot}", icon=":material/swap_horiz:"):
                session.set_item(slot, None)
                st.rerun()
            st.html(items.card(chosen, ruleset))
            return
        mode = st.segmented_control(
            f"How to add item {slot}",
            [SEARCH, MANUAL],
            default=SEARCH,
            key=f"mode_{slot}",
            label_visibility="collapsed",
        )
        if mode == MANUAL:
            _manual(slot, workspace, ruleset)
        else:
            _search(slot, workspace, other)


# --- search ---------------------------------------------------------------------------


def _search(slot: Slot, workspace: Workspace, other: Item | None) -> None:
    search = workspace.search
    columns = st.columns([1.7, 1.0])
    query = columns[0].text_input(
        "Search items",
        key=f"search_{slot}",
        placeholder="Name or item id, e.g. Lionheart Helm",
    )
    slot_options: list[str] = [ANY_SLOT, *ItemSlot]
    filter_key, follows = f"slot_filter_{slot}", f"slot_filter_{slot}_follows"
    if other is not None and st.session_state.get(follows) != other.id:
        # A new other item: search its slot first; the player can still widen it.
        st.session_state[filter_key] = other.slot
        st.session_state[follows] = other.id
    session.default(filter_key, ANY_SLOT)
    slot_filter = columns[1].selectbox(
        "Slot",
        slot_options,
        format_func=lambda value: "Any slot" if value == ANY_SLOT else SLOT_LABELS[value],
        key=filter_key,
    )
    online = st.toggle(
        "Also look up online (Blizzard API)",
        key=f"online_{slot}",
        disabled=not search.online_available,
        help="Local data is searched first; an online lookup is cached for at most 30 days.",
    )
    if not search.online_available:
        st.caption(_offline_reason(search.online_state))

    text = " ".join(query.split())
    if not text:
        st.caption("Type part of a name - words in any order - or an item id.")
        return
    chosen_slot = None if slot_filter == ANY_SLOT else ItemSlot(slot_filter)
    filters = ItemFilters(slots=(chosen_slot,) if chosen_slot is not None else ())
    with st.spinner("Searching…"):
        outcome = search.search(text, filters, limit=25, online=online)
    for notice in outcome.notices:
        st.warning(notice, icon=":material/cloud_off:")
    if not outcome.hits:
        where = f" for {SLOT_LABELS[chosen_slot]}" if chosen_slot is not None else ""
        st.info(f'No items match "{text}"{where}.', icon=":material/search_off:")
        return
    hits = {hit.item.id: hit for hit in outcome.hits}

    def label(item_id: str) -> str:
        hit = hits[item_id]
        flag = " (cached lookup expired)" if hit.stale else ""
        return items.summary(hit.item) + flag

    picked = st.selectbox(
        f"{len(hits)} found",
        list(hits),
        index=None,
        placeholder="Choose an item…",
        format_func=label,
        key=f"pick_{slot}:{text.lower()}",
    )
    if picked is not None:
        session.set_item(slot, hits[picked].item)
        st.rerun()


def _offline_reason(state: str) -> str:
    if state == "disabled":
        return "Online lookup is turned off in configs/providers.yaml; local data is used."
    if state == "failed":
        return "The online provider is not working right now; local data is used."
    return "Online lookup needs Blizzard API credentials (see .env.example); local data is used."


# --- manual entry ---------------------------------------------------------------------


def _key(slot: Slot, name: str) -> str:
    return f"manual_{slot}_{name}"


def _type_options(workspace: Workspace, item_slot: ItemSlot) -> tuple[str, list[object]]:
    choices = workspace.entry.type_choices(item_slot)
    if choices.armor_types:
        return "Armor type", list(choices.armor_types)
    if choices.weapon_types:
        return "Weapon type", list(choices.weapon_types)
    if choices.relic_types:
        return "Relic type", list(choices.relic_types)
    return "", []


def _type_label(value: object) -> str:
    if isinstance(value, ArmorType):
        return ARMOR_LABELS[value]
    if isinstance(value, WeaponType):
        return weapon_label(value)
    if isinstance(value, RelicType):
        return RELIC_LABELS[value]
    return str(value)


def _fill_from_tooltip(slot: Slot, workspace: Workspace) -> None:
    text = st.session_state.get(_key(slot, "tooltip"), "")
    custom = bool(st.session_state.get(_key(slot, "custom"), True))
    reading = workspace.entry.read_tooltip(text, custom=custom)
    st.session_state[_key(slot, "reading")] = (reading.unrecognized, reading.problems)
    form = reading.form
    if form is None:
        return
    st.session_state[_key(slot, "name")] = form.name
    st.session_state[_key(slot, "slot")] = form.slot
    st.session_state[_key(slot, "type")] = form.armor_type or form.weapon_type or form.relic_type
    st.session_state[_key(slot, "quality")] = form.quality or NOT_GIVEN
    st.session_state[_key(slot, "required_level")] = form.required_level
    for name in ("min_damage", "max_damage", "speed"):
        st.session_state[_key(slot, name)] = getattr(form, name)
    for stat in Stat:
        st.session_state.pop(_key(slot, f"stat_{stat.value}"), None)
    for stat, value in form.stats.items():
        st.session_state[_key(slot, f"stat_{stat.value}")] = float(value)
    st.session_state[_key(slot, "effects")] = form.effects
    st.session_state.pop(_key(slot, "preview"), None)


def _manual(slot: Slot, workspace: Workspace, ruleset: Ruleset) -> None:
    with st.expander("Fill from a tooltip", icon=":material/content_paste:"):
        st.text_area(
            "Paste the item's tooltip text",
            key=_key(slot, "tooltip"),
            height=150,
            placeholder="Lionheart Helm\nBinds when equipped\nHead    Plate\n565 Armor\n+18 Strength\n…",
        )
        st.button(
            "Read tooltip",
            key=_key(slot, "read"),
            on_click=_fill_from_tooltip,
            args=(slot, workspace),
            icon=":material/auto_fix_high:",
        )
        unrecognized, problems = st.session_state.get(_key(slot, "reading"), ([], []))
        for problem in problems:
            st.warning(problem)
        if unrecognized:
            st.caption("Lines the reader could not place (add them below if they matter):")
            st.code("\n".join(unrecognized), language=None)

    st.text_input("Name", key=_key(slot, "name"), placeholder="My theorycrafted helm")
    first = st.columns(2)
    item_slot = first[0].selectbox(
        "Slot",
        list(ItemSlot),
        format_func=lambda value: SLOT_LABELS[value],
        key=_key(slot, "slot"),
    )
    if item_slot is None:
        return
    type_name, type_options = _type_options(workspace, item_slot)
    item_type: object | None = None
    if type_options:
        session.keep_valid(_key(slot, "type"), type_options, type_options[0])
        item_type = first[1].selectbox(
            type_name, type_options, format_func=_type_label, key=_key(slot, "type")
        )
    second = st.columns(3)
    quality_choice = second[0].selectbox(
        "Quality",
        [NOT_GIVEN, *ItemQuality],
        format_func=lambda value: "Not given" if value == NOT_GIVEN else QUALITY_LABELS[value],
        key=_key(slot, "quality"),
    )
    quality = None if quality_choice == NOT_GIVEN else ItemQuality(quality_choice)
    required_level = second[1].number_input(
        "Required level",
        min_value=0,
        max_value=ruleset.max_level,
        step=1,
        key=_key(slot, "required_level"),
    )
    custom = second[2].toggle(
        "Theorycrafted",
        value=True,
        key=_key(slot, "custom"),
        help="On: an item you are imagining, allowed to break the usual patterns. Off: a copy "
        "of a real item, which must look like one.",
    )

    if workspace.entry.type_choices(item_slot).has_weapon_block:
        weapon = st.columns(3)
        for column, (name, label) in zip(
            weapon,
            (("min_damage", "Min damage"), ("max_damage", "Max damage"), ("speed", "Speed")),
            strict=True,
        ):
            column.number_input(
                label,
                min_value=0.0,
                value=None,
                step=0.1 if name == "speed" else 1.0,
                format="%.2f" if name == "speed" else "%.0f",
                key=_key(slot, name),
            )

    groups = workspace.entry.stat_groups(item_slot)
    stats: dict[Stat, float] = {}

    def fields(group_index: int) -> None:
        group = groups[group_index]
        st.caption(group.label)
        columns = st.columns(3)
        for index, field in enumerate(group.fields):
            value = columns[index % 3].number_input(
                field.label + (" (%)" if field.unit == "percent" else ""),
                value=None,
                step=1.0,
                format="%g",
                key=_key(slot, f"stat_{field.stat.value}"),
                help=field.description,
            )
            if value:
                stats[field.stat] = float(value)

    for index in range(min(PRIMARY_GROUPS, len(groups))):
        fields(index)
    if len(groups) > PRIMARY_GROUPS:
        with st.expander(
            "More stats: " + ", ".join(g.label.lower() for g in groups[PRIMARY_GROUPS:])
        ):
            for index in range(PRIMARY_GROUPS, len(groups)):
                fields(index)

    effects: tuple[EffectRow, ...] = st.session_state.get(_key(slot, "effects"), ())
    if effects:
        st.caption(
            "Effects from the tooltip: " + "; ".join(row.text or str(row.stat) for row in effects)
        )

    if st.button("Check item", key=_key(slot, "check"), icon=":material/fact_check:"):
        st.session_state[_key(slot, "preview")] = _preview(
            slot,
            workspace,
            item_slot,
            item_type,
            quality,
            int(required_level),
            custom,
            stats,
            effects,
        )
    preview: EntryPreview | None = st.session_state.get(_key(slot, "preview"))
    if preview is not None:
        _show_preview(slot, preview, ruleset)


def _preview(
    slot: Slot,
    workspace: Workspace,
    item_slot: ItemSlot,
    item_type: object | None,
    quality: ItemQuality | None,
    required_level: int,
    custom: bool,
    stats: dict[Stat, float],
    effects: tuple[EffectRow, ...],
) -> EntryPreview:
    values: dict[str, object] = {
        "name": st.session_state.get(_key(slot, "name"), ""),
        "slot": item_slot,
        "quality": quality,
        "required_level": required_level,
        "stats": stats,
        "effects": effects,
        "custom": custom,
    }
    if isinstance(item_type, ArmorType):
        values["armor_type"] = item_type
    elif isinstance(item_type, WeaponType):
        values["weapon_type"] = item_type
    elif isinstance(item_type, RelicType):
        values["relic_type"] = item_type
    if workspace.entry.type_choices(item_slot).has_weapon_block:
        for name in ("min_damage", "max_damage", "speed"):
            values[name] = st.session_state.get(_key(slot, name))
    try:
        form = ManualItemForm.model_validate(values)
    except ValidationError as error:
        messages = tuple(
            f"{'.'.join(str(part) for part in issue['loc']) or 'item'}: {issue['msg']}"
            for issue in error.errors()
        )
        return EntryPreview(item=None, issues=(), form_errors=messages, usable=False)
    return workspace.entry.preview(form)


def _show_preview(slot: Slot, preview: EntryPreview, ruleset: Ruleset) -> None:
    for message in preview.form_errors:
        st.error(message, icon=":material/error:")
    for issue in preview.issues:
        if issue.severity == "error":
            st.error(issue.message, icon=":material/error:")
        elif issue.severity == "warning":
            st.warning(issue.message, icon=":material/warning:")
        else:
            st.caption(issue.message)
    if preview.item is None:
        return
    st.html('<div class="wg-small">Preview</div>' + items.card(preview.item, ruleset))
    if preview.usable:
        if st.button(f"Use as item {slot}", key=_key(slot, "use"), type="primary"):
            session.set_item(slot, preview.item)
            st.session_state.pop(_key(slot, "preview"), None)
            st.rerun()
    else:
        st.caption(
            "Fix the problems above to use this item, or mark it theorycrafted if it breaks "
            "a pattern on purpose."
        )
