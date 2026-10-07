"""What the calculator and compare pages share: opening the workspace, the context bar, and
the context built from it and from the current stats the player entered."""

from __future__ import annotations

from dataclasses import dataclass

import streamlit as st

from components import advanced, context_bar
from state import session
from state.workspace import workspace
from wow_gear.models.character import CharacterContext
from wow_gear.models.enums import Stat
from wow_gear.services.errors import DataValidationError, WowGearError
from wow_gear.services.workspace import Workspace


@dataclass(frozen=True)
class Setup:
    workspace: Workspace
    choice: context_bar.Choice
    stats: list[Stat]
    """The gear totals the current stats inputs ask for."""
    weapon_skill: bool
    context: CharacterContext | None


def open_workspace() -> Workspace | None:
    """The shared workspace, or an explained error state when it cannot open."""
    try:
        ws = workspace()
    except WowGearError as error:
        st.error(f"The calculator could not start: {error}", icon=":material/error:")
        st.caption("Check the files in configs/ and run `wowgear check` for details.")
        return None
    if ws.bundled.problem:
        st.warning(
            f"Item data: {ws.bundled.problem}. Search may find nothing; items entered by hand "
            "still work.",
            icon=":material/database:",
        )
    return ws


def setup() -> Setup | None:
    """Draw the context bar and build the context; None when the page cannot go on."""
    ws = open_workspace()
    if ws is None:
        return None
    calc = ws.calculator
    choice = context_bar.render(calc, ws.ruleset.id)
    if choice is None:
        return None
    profile = choice.profile
    weapon_skill = calc.uses_weapon_skill(profile.id)
    main_hand = session.get(session.MAIN_HAND) if weapon_skill else None
    race = session.get(session.RACE) if weapon_skill else None
    stats = calc.gear_total_stats(profile.id)
    skill_stat = advanced.weapon_skill_stat(main_hand)
    if skill_stat is not None:
        stats = [*stats, skill_stat]
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
    return Setup(ws, choice, stats, weapon_skill, context)
