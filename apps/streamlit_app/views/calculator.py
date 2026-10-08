"""The calculator page (roadmap section 8): the context bar, the two items, the
recommendation, and the advanced tabs. It calls services only and does no game math."""

from __future__ import annotations

import streamlit as st

from components import advanced, exports, item_input, recommendation
from components.html import eyebrow, md
from state import session
from state.session import Slot
from views.common import setup
from wow_gear.models.comparison import ComparisonResult
from wow_gear.models.item import Item
from wow_gear.services.errors import DataValidationError, NotFoundError


def render() -> None:
    ready = setup()
    if ready is None:
        return
    ws, profile, ruleset = ready.workspace, ready.choice.profile, ready.choice.ruleset

    chosen: dict[Slot, Item | None] = {slot: session.item(slot) for slot in session.SLOTS}
    worn = [f"Item {slot}" for slot, item in chosen.items() if item is not None]
    session.keep_valid(session.EQUIPPED, [session.NEITHER, *worn], session.NEITHER)
    equipped = str(session.get(session.EQUIPPED, session.NEITHER))
    replacing = None
    if equipped != session.NEITHER:
        replacing = chosen.get("A" if equipped.endswith("A") else "B")

    st.write("")
    left, right = st.columns([1, 1.08], gap="large")
    with left:
        st.html(eyebrow("Items"))
        for slot in session.SLOTS:
            other = chosen["B" if slot == "A" else "A"]
            item_input.render(slot, ws, ruleset, other)

    result: ComparisonResult | None = None
    with right:
        st.html(eyebrow("Result"))
        picked = [item for item in chosen.values() if item is not None]
        if not picked or ready.context is None:
            recommendation.empty()
        elif len(picked) == 2 and picked[0].id == picked[1].id:
            st.info("Item A and item B are the same item: choose a different one to compare.")
        else:
            try:
                result = ws.calculator.compare(picked, ready.context, replacing=replacing)
            except (DataValidationError, NotFoundError) as error:
                st.error(md(f"These items cannot be compared: {error}"), icon=":material/error:")
            else:
                slots = {item.id: slot for slot, item in chosen.items() if item is not None}
                recommendation.render(result, slots)
                exports.comparison_downloads(result, ready.context, "calc_export")

    st.write("")
    st.html(eyebrow("Advanced"))
    advanced.render(
        profile,
        ruleset,
        result,
        ready.stats,
        ready.weapon_skill,
        {str(slot): item for slot, item in chosen.items()},
    )
