"""The context bar: class, role and build profile; ruleset and phase; level and content.

Every score is computed for this context, so it sits at the top of the page, and the
breadcrumb under it repeats the choice in words.
"""

from __future__ import annotations

from dataclasses import dataclass
from html import escape

import streamlit as st

from components.html import chip
from state import session
from wow_gear.models.enums import ContentMode
from wow_gear.models.labels import CONTENT_MODE_LABELS, ROLE_LABELS
from wow_gear.models.profile import BuildProfile
from wow_gear.models.ruleset import Ruleset
from wow_gear.services.calculator import CalculatorService


@dataclass(frozen=True)
class Choice:
    """What the bar decided: the profile and ruleset, and the values for the context."""

    ruleset: Ruleset
    profile: BuildProfile
    phase: int
    level: int
    content: ContentMode


def _phase_label(ruleset: Ruleset, number: int) -> str:
    phase = next(p for p in ruleset.phases if p.number == number)
    headline = phase.content.split(",")[0].split(" with ")[0].strip()
    return f"{phase.label}: {headline}"


def render(calc: CalculatorService, ruleset_id: str) -> Choice | None:
    ruleset = calc.ruleset(ruleset_id)
    classes = calc.classes(ruleset_id)
    if not classes:
        st.error("No build profiles are configured for this ruleset (see configs/profiles).")
        return None
    class_labels = dict(classes)
    session.default(session.CLASS, classes[0][0])
    session.keep_valid(session.CLASS, list(class_labels), classes[0][0])

    with st.container(border=True):
        columns = st.columns([1.0, 1.0, 1.5, 1.0, 1.25, 0.7, 1.0], vertical_alignment="bottom")
        class_name = columns[0].selectbox(
            "Class",
            list(class_labels),
            format_func=lambda value: class_labels[value],
            key=session.CLASS,
        )
        if class_name is None:
            return None
        roles = calc.roles(ruleset_id, class_name)
        role_options = [role for role, _ in roles]
        session.keep_valid(session.ROLE, role_options, role_options[0])
        role = columns[1].selectbox(
            "Role", role_options, format_func=lambda value: ROLE_LABELS[value], key=session.ROLE
        )
        if role is None:
            return None
        profiles = {profile.id: profile for profile in calc.profiles(ruleset_id, class_name, role)}
        first = next(iter(profiles))
        session.keep_valid(session.PROFILE, list(profiles), first)
        profile_id = columns[2].selectbox(
            "Build profile",
            list(profiles),
            format_func=lambda key: profiles[key].label,
            key=session.PROFILE,
            help="A build profile holds the stat weights, caps and assumptions the score uses.",
        )
        if profile_id is None:
            return None
        profile = profiles[profile_id]
        columns[3].selectbox(
            "Ruleset",
            [ruleset.id],
            format_func=lambda _: ruleset.label,
            disabled=True,
            key="ctx_ruleset",
            help=f"{ruleset.label} {ruleset.version}: {ruleset.rules_basis}",
        )
        phases = [phase.number for phase in ruleset.phases]
        session.default(session.PHASE, profile.target_phase or ruleset.default_phase)
        phase = columns[4].selectbox(
            "Phase",
            phases,
            format_func=lambda number: _phase_label(ruleset, number),
            key=session.PHASE,
            help="Items from later phases are shown as not yet available.",
        )
        session.default(session.LEVEL, profile.target_level)
        level = columns[5].number_input(
            "Level",
            min_value=ruleset.min_level,
            max_value=ruleset.max_level,
            step=1,
            key=session.LEVEL,
        )
        modes = [mode.mode for mode in ruleset.content_modes]
        session.default(session.CONTENT, profile.default_content_mode)
        content = columns[6].selectbox(
            "Content",
            modes,
            format_func=lambda value: CONTENT_MODE_LABELS[value],
            key=session.CONTENT,
            help="Sets the target's level: raid bosses count as three levels above you.",
        )
    if phase is None or content is None or level is None:
        return None

    status = profile.validation_status.value
    status_chip = chip(
        f"{status.capitalize()} profile",
        "gold" if status == "validated" else "muted",
        title="Draft profiles use sourced weights that have not been validated against logs.",
    )
    crumbs = [
        f"<b>{escape(class_labels[class_name])}</b>",
        f"<b>{escape(ROLE_LABELS[role])}</b>",
        f"<b>{escape(profile.label)}</b>",
        escape(CONTENT_MODE_LABELS[content]),
    ]
    tail = f"{ruleset.label} {ruleset.version} · Phase {phase} · Level {int(level)}"
    st.html(
        '<div class="wg-crumbs">Current context: '
        + '<span class="wg-sep">›</span>'.join(crumbs)
        + f' <span class="wg-sep">·</span> {escape(tail)} &nbsp;{status_chip}</div>'
    )
    return Choice(ruleset=ruleset, profile=profile, phase=phase, level=int(level), content=content)
