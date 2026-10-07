"""The calculator page (roadmap section 8): the context bar, the two items, the
recommendation, and the advanced tabs. It calls services only and does no game math."""

from __future__ import annotations

import streamlit as st

from components import advanced, context_bar, item_input, recommendation
from components.html import eyebrow
from state import session
from state.workspace import workspace
from wow_gear.models.comparison import ComparisonResult
from wow_gear.models.item import Item
from wow_gear.services.errors import DataValidationError, NotFoundError, WowGearError


def render() -> None:
    try:
        ws = workspace()
    except WowGearError as error:
        st.error(f"The calculator could not start: {error}", icon=":material/error:")
        st.caption("Check the files in configs/ and run `wowgear check` for details.")
        return
    calc = ws.calculator
    if ws.bundled.problem:
        st.warning(
            f"Item data: {ws.bundled.problem}. Search may find nothing; items entered by hand "
            "still work.",
            icon=":material/database:",
        )
    choice = context_bar.render(calc, ws.ruleset.id)
    if choice is None:
        return
    profile, ruleset = choice.profile, choice.ruleset

    weapon_skill = calc.uses_weapon_skill(profile.id)
    main_hand = session.get(session.MAIN_HAND) if weapon_skill else None
    race = session.get(session.RACE) if weapon_skill else None
    stats = calc.gear_total_stats(profile.id)
    skill_stat = advanced.weapon_skill_stat(main_hand)
    if skill_stat is not None:
        stats = [*stats, skill_stat]

    chosen: dict[str, Item | None] = {slot: session.item(slot) for slot in session.SLOTS}
    worn = [f"Item {slot}" for slot, item in chosen.items() if item is not None]
    session.keep_valid(session.EQUIPPED, [session.NEITHER, *worn], session.NEITHER)
    equipped = session.get(session.EQUIPPED, session.NEITHER)
    replacing = chosen.get(equipped.removeprefix("Item ")) if equipped != session.NEITHER else None

    context = None
    try:
        context = calc.context(
            profile.id,
            phase=choice.phase,
            level=choice.level,
            content_mode=choice.content,
            race=race,
            main_hand_type=main_hand,
            current_stats=session.gear_totals(stats),
        )
    except DataValidationError as error:
        st.error(f"This context cannot be scored: {error}", icon=":material/error:")

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
        if not picked or context is None:
            recommendation.empty()
        elif len(picked) == 2 and picked[0].id == picked[1].id:
            st.info("Item A and item B are the same item: choose a different one to compare.")
        else:
            try:
                result = calc.compare(picked, context, replacing=replacing)
            except (DataValidationError, NotFoundError) as error:
                st.error(f"These items cannot be compared: {error}", icon=":material/error:")
            else:
                slots = {item.id: slot for slot, item in chosen.items() if item is not None}
                recommendation.render(result, slots)  # type: ignore[arg-type]

    st.write("")
    st.html(eyebrow("Advanced"))
    advanced.render(profile, ruleset, result, stats, weapon_skill, chosen)
