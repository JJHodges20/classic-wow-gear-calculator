"""The Item Database page (roadmap section 8): browse the local item data - the bundled
dataset, online lookups and your own items - with where each item came from."""

from __future__ import annotations

from html import escape

import streamlit as st

from components import items
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


def _filters() -> tuple[str, ItemFilters]:
    top = st.columns([2.2, 1, 1, 1])
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
    second = st.columns([1, 1, 1, 1.2])
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
    with st.container(border=True):
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
            f"<tr><td>{escape(name)}</td><td>{escape(value)}</td></tr>" for name, value in facts
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
            if column.button(f"Compare as item {slot}", key=f"db_use_{slot}"):
                session.set_item(slot, item)
                st.switch_page(CALCULATOR)


def render() -> None:
    ws = open_workspace()
    if ws is None:
        return
    counts = ws.search.counts()
    st.caption(
        f"{sum(counts.values()):,} items here: {counts.get('bundled', 0):,} from the bundled "
        f"dataset, {counts.get('cache', 0):,} looked up online, {counts.get('user', 0):,} of "
        "your own."
    )
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
    if not hits:
        st.info("No items match these filters.", icon=":material/search_off:")
        return
    left, right = st.columns([1.7, 1], gap="large")
    with left:
        event = st.dataframe(
            [_row(hit) for hit in hits],
            key="db_table",
            on_select="rerun",
            selection_mode="single-row",
            hide_index=True,
            width="stretch",
            height=560,
        )
        nav = st.columns([1, 2, 1], vertical_alignment="center")
        if nav[0].button("Previous", disabled=page == 0, icon=":material/chevron_left:"):
            st.session_state["db_page"] = page - 1
            st.rerun()
        nav[1].caption(
            f"{total:,} found" if text else f"Page {page + 1} of {pages} · {total:,} items"
        )
        if nav[2].button("Next", disabled=page + 1 >= pages, icon=":material/chevron_right:"):
            st.session_state["db_page"] = page + 1
            st.rerun()
    with right:
        rows = event.selection.rows if event is not None else []
        if rows and rows[0] < len(hits):
            _detail(hits[rows[0]], ws.ruleset)
        else:
            st.html(
                '<div class="wg-empty"><b>Select a row</b> to see the item, where its data '
                "came from, and to compare it in the calculator.</div>"
            )
