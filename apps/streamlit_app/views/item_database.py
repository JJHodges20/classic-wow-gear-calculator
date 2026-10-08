"""The Item Database page (roadmap section 8): browse the local item data - the bundled
dataset, online lookups and your own items - with where each item came from."""

from __future__ import annotations

from html import escape

import streamlit as st

from components import items, layout
from components.html import eyebrow
from state import session
from views.common import open_workspace
from wow_gear.models.enums import ArmorType, ItemQuality, ItemSlot, WeaponType
from wow_gear.models.labels import ARMOR_LABELS, QUALITY_LABELS, SLOT_LABELS, weapon_label
from wow_gear.models.ruleset import Ruleset
from wow_gear.services.item_search import ItemFilters, SearchHit

PAGE_SIZE = 50
CALCULATOR = "pages/calculator.py"
ANY = "any"
ORIGINS = {"bundled": "Bundled dataset", "cache": "Online lookups", "user": "Your own items"}
QUALITY_RANK = {quality: rank for rank, quality in enumerate(ItemQuality)}
KINDS: dict[str, str] = {
    ANY: "Any type",
    **{f"armor:{a.value}": ARMOR_LABELS[a] for a in ArmorType},
    **{f"weapon:{w.value}": weapon_label(w) for w in WeaponType},
}


FILTER_DEFAULTS: dict[str, object] = {
    "db_text": "",
    "db_slot": ANY,
    "db_kind": ANY,
    "db_origin": ANY,
    "db_phase": ANY,
    "db_level": None,
    "db_quality": ANY,
}


def _clear_filters() -> None:
    """Every filter back to "any". The values are set rather than removed, so the widgets on
    screen show them too."""
    for key, value in FILTER_DEFAULTS.items():
        st.session_state[key] = value


def _filters() -> tuple[str, ItemFilters]:
    top = st.columns([2.2, 1, 1, 1], vertical_alignment="bottom")
    text = top[0].text_input("Name contains", key="db_text", placeholder="e.g. of Wrath")
    slot = top[1].selectbox(
        "Slot",
        [ANY, *ItemSlot],
        format_func=lambda v: "Any slot" if v == ANY else SLOT_LABELS[v],
        key="db_slot",
    )
    kind = top[2].selectbox("Type", list(KINDS), format_func=KINDS.__getitem__, key="db_kind")
    origin = top[3].selectbox(
        "Source",
        [ANY, *ORIGINS],
        format_func=lambda v: "All sources" if v == ANY else ORIGINS[v],
        key="db_origin",
    )
    second = st.columns([1.1, 1.1, 1, 1, 1], vertical_alignment="bottom")
    phase = second[0].selectbox(
        "Up to phase",
        [ANY, "1", "2", "3", "4", "5", "6"],
        format_func=lambda v: "Any phase" if v == ANY else f"Phase {v}",
        key="db_phase",
    )
    level = second[1].number_input(
        "Up to required level",
        min_value=0,
        max_value=60,
        value=None,
        step=1,
        key="db_level",
        placeholder="Any",
    )
    quality = second[2].selectbox(
        "At least",
        [ANY, *ItemQuality],
        format_func=lambda v: "Any quality" if v == ANY else QUALITY_LABELS[ItemQuality(v)],
        key="db_quality",
    )
    second[4].button(
        "Clear filters",
        key="db_clear",
        on_click=_clear_filters,
        icon=":material/filter_alt_off:",
        type="tertiary",
        width="stretch",
    )
    kind_family, _, kind_value = (kind or ANY).partition(":")
    filters = ItemFilters(
        slots=(ItemSlot(slot),) if slot and slot != ANY else (),
        armor_types=(ArmorType(kind_value),) if kind_family == "armor" else (),
        weapon_types=(WeaponType(kind_value),) if kind_family == "weapon" else (),
        max_phase=int(phase) if phase and phase != ANY else None,
        max_required_level=int(level) if level is not None else None,
        min_quality_rank=QUALITY_RANK[ItemQuality(quality)] if quality and quality != ANY else None,
        origins=tuple(o for o in ("bundled", "cache", "user") if o == origin),
    )
    return " ".join(text.split()), filters


def _row(hit: SearchHit) -> dict[str, object]:
    item = hit.item
    stats = ", ".join(
        f"{value:g} {stat.value.replace('_', ' ')}" for stat, value in list(item.stats.items())[:6]
    )
    return {
        "Name": item.name,
        "Slot and type": items.type_label(item),
        "Quality": QUALITY_LABELS[item.quality] if item.quality is not None else "",
        "Phase": item.phase,
        "Level": item.required_level or None,
        "Stats": stats,
        "Source": ORIGINS[hit.origin] + (" (expired)" if hit.stale else ""),
    }


def _detail(hit: SearchHit, ruleset: Ruleset) -> None:
    item = hit.item
    provenance = item.provenance
    with layout.card("detail"):
        st.html(eyebrow("Item") + items.card(item, ruleset))
        facts = [
            ("Id", item.id),
            ("Provider", items.PROVIDER_LABELS.get(provenance.provider, provenance.provider)),
            ("Source", provenance.source),
            ("Data version", provenance.data_version),
            (
                "Fetched",
                f"{provenance.fetched_at:%Y-%m-%d %H:%M}" if provenance.fetched_at else "-",
            ),
            ("License", provenance.license or "-"),
            ("Kept as", ORIGINS[hit.origin]),
            ("Stored", f"{hit.stored_at:%Y-%m-%d %H:%M}" if hit.stored_at else "-"),
            ("Expires", f"{hit.expires_at:%Y-%m-%d %H:%M}" if hit.expires_at else "Never"),
        ]
        rows = "".join(
            f'<tr><td class="wg-label">{escape(name)}</td><td>{escape(value)}</td></tr>'
            for name, value in facts
        )
        link = (
            f'<a href="{escape(provenance.source_url)}" target="_blank" '
            'rel="noopener noreferrer">Source page ↗</a>'
            if provenance.source_url
            else ""
        )
        st.html(f'<table class="wg-table"><tbody>{rows}</tbody></table>{link}')
        buttons = st.columns(2)
        for column, slot in zip(buttons, session.SLOTS, strict=True):
            if column.button(f"Compare as item {slot}", key=f"db_use_{slot}", width="stretch"):
                session.set_item(slot, item)
                st.switch_page(CALCULATOR)


def render() -> None:
    layout.page_header(
        "Item database",
        "Browse every item the calculator knows and where its data came from, and send one to "
        "the calculator.",
        "items",
    )
    ws = open_workspace()
    if ws is None:
        return
    counts = ws.search.counts()
    with layout.card("filters"):
        text, filters = _filters()
    query = repr((text, filters))
    if st.session_state.get("db_last_query") != query:
        st.session_state["db_last_query"] = query
        st.session_state["db_page"] = 0
    page = int(st.session_state.get("db_page", 0))
    if text:
        hits = list(ws.search.search(text, filters, limit=200).hits)
        total, pages = len(hits), 1
    else:
        hits, total = ws.search.browse(filters, offset=page * PAGE_SIZE, limit=PAGE_SIZE)
        pages = max(1, -(-total // PAGE_SIZE))
    layout.section(
        "Items",
        f"{sum(counts.values()):,} items here: {counts.get('bundled', 0):,} from the bundled "
        f"dataset, {counts.get('cache', 0):,} looked up online, {counts.get('user', 0):,} of "
        "your own.",
        aside=f"{total:,} found" if text else f"Page {page + 1} of {pages} · {total:,} items",
    )
    if not hits:
        layout.empty_state(
            "No items match these filters.",
            "Widen a filter, or clear them all to see every item.",
            glyph="search",
        )
        return
    left, right = layout.split([2, 1], key="items")
    with left:
        event = st.dataframe(
            [_row(hit) for hit in hits],
            key="db_table",
            on_select="rerun",
            selection_mode="single-row",
            hide_index=True,
            width="stretch",
            # A short list is as tall as its rows; a long one scrolls inside a fixed height.
            height=560 if len(hits) > 15 else "content",
            placeholder="-",
            column_config={
                "Name": st.column_config.TextColumn(width="medium"),
                "Slot and type": st.column_config.TextColumn(width=150),
                "Quality": st.column_config.TextColumn(width=90),
                "Phase": st.column_config.NumberColumn(width=64),
                "Level": st.column_config.NumberColumn(width=64),
                "Stats": st.column_config.TextColumn(width="large"),
                "Source": st.column_config.TextColumn(width="small"),
            },
        )
        if not text:
            pager = st.container(
                horizontal=True, horizontal_alignment="distribute", vertical_alignment="center"
            )
            if pager.button(
                "Previous", disabled=page == 0, icon=":material/chevron_left:", key="db_previous"
            ):
                st.session_state["db_page"] = page - 1
                st.rerun()
            pager.html(f'<div class="wg-small">Page {page + 1} of {pages}</div>', width="content")
            if pager.button(
                "Next", disabled=page + 1 >= pages, icon=":material/chevron_right:", key="db_next"
            ):
                st.session_state["db_page"] = page + 1
                st.rerun()
    with right:
        rows = event.selection.rows if event is not None else []
        if rows and rows[0] < len(hits):
            _detail(hits[rows[0]], ws.ruleset)
        else:
            layout.empty_state(
                "Select a row",
                "to see the item, where its data came from, and to compare it in the calculator.",
                glyph="items",
            )
