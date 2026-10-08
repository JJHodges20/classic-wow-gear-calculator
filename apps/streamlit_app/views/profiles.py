"""The Build Profiles page (roadmap section 8): inspect a profile's weights, conversions, caps,
assumptions and sources, and save your own weights as a custom profile."""

from __future__ import annotations

from html import escape

import streamlit as st
from streamlit.delta_generator import DeltaGenerator

from components import layout
from components.html import chip, eyebrow, md
from state import session
from views.common import open_workspace
from wow_gear.models.enums import WEAPON_DPS_STATS, Stat
from wow_gear.models.formatting import stat_label
from wow_gear.models.labels import CONTENT_MODE_LABELS, ROLE_LABELS, weapon_label
from wow_gear.models.profile import BuildProfile
from wow_gear.models.ruleset import Ruleset
from wow_gear.services.errors import DataValidationError
from wow_gear.services.profiles import ProfileService

KEY = "profiles_page_profile"
NEXT = "profiles_page_next"
"""The profile to select on the next run (a widget's key cannot change once it is drawn)."""
FLASH = "profiles_page_flash"
CALCULATOR = "pages/calculator.py"


def _option_label(service: ProfileService, profile: BuildProfile) -> str:
    ruleset = service.ruleset_of(profile)
    custom = " (yours)" if service.is_custom(profile.id) else ""
    return (
        f"{ruleset.class_def(profile.class_name).label} · {ROLE_LABELS[profile.role]} · "
        f"{profile.label}{custom}"
    )


def _base_id(profile: BuildProfile) -> str | None:
    """The profile a custom one was copied from, as its notes record it."""
    if profile.notes and profile.notes.startswith("Based on "):
        return profile.notes.split()[2]
    return None


def _number(value: object) -> float:
    return float(value) if isinstance(value, int | float) else 0.0


def _list(lines: list[str]) -> str:
    return "<ul>" + "".join(f"<li>{escape(line)}</li>" for line in lines) + "</ul>"


def _weights(profile: BuildProfile, ruleset: Ruleset) -> str:
    rows = "".join(
        f"<tr><td>{escape(stat_label(weight.stat, ruleset))}</td>"
        f'<td class="wg-num">{weight.weight:g}</td><td>{escape(weight.basis.value)}</td>'
        f"<td>{escape(', '.join(weight.sources))}</td>"
        f"<td>{escape(weight.note or '')}</td></tr>"
        for weight in profile.stat_weights
    )
    return (
        '<table class="wg-table"><thead><tr><th>Stat</th><th class="wg-num">Weight</th>'
        "<th>Basis</th><th>Sources</th><th>Note</th></tr></thead>"
        f"<tbody>{rows}</tbody></table>"
    )


def _conversions(profile: BuildProfile, ruleset: Ruleset) -> list[str]:
    lines = []
    for rule in profile.derived_stats:
        conversion = ruleset.conversion(profile.class_name, rule.conversion)
        source, target = stat_label(rule.source, ruleset), stat_label(rule.target, ruleset)
        target_def = ruleset.stat_def(rule.target)
        one = "1%" if target_def is not None and target_def.unit == "percent" else "1"
        if conversion is not None and conversion.per_point is not None:
            lines.append(f"{source} → {target}: {conversion.per_point:g} per point of {source}")
        elif conversion is not None and conversion.points_per_unit is not None:
            lines.append(
                f"{source} → {target}: {conversion.points_per_unit:g} {source} per {one} "
                f"{target.lower()}"
            )
    return lines


def _inspect(service: ProfileService, profile: BuildProfile) -> None:
    ruleset = service.ruleset_of(profile)
    status = profile.validation_status.value
    badges = [
        chip(f"{profile.id} {profile.version}", "muted"),
        chip(f"{status.capitalize()} profile", "gold" if status == "validated" else "muted"),
    ]
    if service.is_custom(profile.id):
        badges.append(chip("Yours", "gold"))
    target = (
        f"Written for level {profile.target_level}, "
        f"{CONTENT_MODE_LABELS[profile.default_content_mode]}"
        + (f", phase {profile.target_phase}" if profile.target_phase else "")
        + f". Scores are in {profile.score_unit}."
    )
    st.html(f'<h2 class="wg-card-title">{escape(profile.label)}</h2>')
    st.html(
        '<div class="wg-chips">'
        + "".join(badges)
        + "</div>"
        + f'<div class="wg-small">{escape(profile.summary)} {escape(target)}</div>'
    )

    st.html(eyebrow("Stat weights") + _weights(profile, ruleset))
    left, right = layout.split([1, 1], key="profile")
    with left:
        conversions = _conversions(profile, ruleset)
        st.html(
            eyebrow("Conversions")
            + (
                _list(conversions)
                if conversions
                else '<div class="wg-small">No conversions: the weights value each stat as '
                "it stands.</div>"
            )
        )
        caps = service.caps(profile.id)
        lines = [
            f"{stat_label(cap.stat, ruleset)} {cap.kind}: {cap.value:g} - {cap.detail}"
            for cap in caps
        ]
        st.html(
            eyebrow(f"Caps and breakpoints (level {profile.target_level}, default content)")
            + (_list(lines) if lines else '<div class="wg-small">None in this profile.</div>')
        )
        groups = [
            f"{', '.join(stat_label(s, ruleset) for s in group.stats)}: {group.note}"
            for group in profile.exclusive_groups
        ]
        if groups:
            st.html(eyebrow("Only the best of") + _list(groups))
    with right:
        preferences = profile.weapon_preferences
        weapons = [weapon_label(w) for w in preferences.preferred_types]
        if weapons or preferences.note:
            st.html(
                eyebrow("Weapons")
                + _list([", ".join(weapons)] if weapons else [])
                + (
                    f'<div class="wg-small">{escape(preferences.note)}</div>'
                    if preferences.note
                    else ""
                )
            )
        st.html(eyebrow("Assumptions") + _list(list(profile.assumptions)))
        rules = [*profile.proc_assumptions, *profile.set_bonus_rules]
        if rules:
            st.html(eyebrow("Procs and set bonuses") + _list(rules))
        if profile.notes:
            st.html(eyebrow("Notes") + f'<div class="wg-small">{escape(profile.notes)}</div>')
    if profile.sources:
        st.html(
            eyebrow("Sources")
            + "<ul>"
            + "".join(
                f'<li><a href="{escape(source.url)}" target="_blank" rel="noopener noreferrer">'
                f"{escape(source.title)}</a> - read {escape(str(source.retrieved))}"
                + (f" ({escape(source.note)})" if source.note else "")
                + f' <span class="wg-small">[{escape(source.id)}]</span></li>'
                for source in profile.sources
            )
            + "</ul>"
        )


def _customize(service: ProfileService, profile: BuildProfile) -> None:
    ruleset = service.ruleset_of(profile)
    custom = service.is_custom(profile.id)
    title = "Change your weights" if custom else "Customize the weights"
    with st.expander(title, icon=":material/edit:"):
        st.caption(
            "Your copy is saved in your data folder with a version that goes up with each "
            "save; the shipped profile is never changed. Weights you set are labelled as "
            "assumptions."
        )
        extra_key = f"profile_extra_{profile.id}"
        extra: list[Stat] = list(st.session_state.get(extra_key, []))
        rows = [
            {"Stat": stat_label(w.stat, ruleset), "Weight": w.weight, "Keep": True}
            for w in profile.stat_weights
        ] + [{"Stat": stat_label(stat, ruleset), "Weight": 0.0, "Keep": True} for stat in extra]
        stats = [w.stat for w in profile.stat_weights] + extra
        edited = st.data_editor(
            rows,
            key=f"profile_editor_{profile.id}",
            hide_index=True,
            width="stretch",
            disabled=["Stat"],
            column_config={
                "Weight": st.column_config.NumberColumn(format="%g", step=0.01),
                "Keep": st.column_config.CheckboxColumn(help="Untick to stop valuing a stat."),
            },
        )
        weighted = set(stats)
        addable = [
            s.stat
            for s in ruleset.stats
            if s.stat not in weighted and s.stat not in WEAPON_DPS_STATS
        ] + [stat for stat in WEAPON_DPS_STATS if stat not in weighted]
        columns = st.columns([2, 1], vertical_alignment="bottom")
        to_add = columns[0].selectbox(
            "Add a stat",
            addable,
            index=None,
            placeholder="Choose a stat to value…",
            format_func=lambda stat: stat_label(stat, ruleset),
            key=f"profile_add_{profile.id}",
        )
        if columns[1].button("Add", key=f"profile_add_button_{profile.id}") and to_add:
            st.session_state[extra_key] = [*extra, to_add]
            st.rerun()

        name = st.text_input(
            "Name of your profile",
            value=profile.label if custom else f"My {profile.label}",
            key=f"profile_name_{profile.id}",
        )
        label = "Save a new version" if custom else "Save as my profile"
        if st.button(label, type="primary", key=f"profile_save_{profile.id}"):
            weights = {
                stat: _number(row["Weight"])
                for stat, row in zip(stats, edited, strict=True)
                if row["Keep"]
            }
            try:
                saved = service.save_custom(profile.id, name, weights)
            except DataValidationError as error:
                st.error(md(f"Not saved: {error}"), icon=":material/error:")
            else:
                st.session_state.pop(extra_key, None)
                st.session_state[NEXT] = saved.id
                st.session_state[FLASH] = f"Saved {saved.label} {saved.version}."
                st.rerun()


def _manage(
    service: ProfileService, profile: BuildProfile, use: DeltaGenerator, delete: DeltaGenerator
) -> None:
    if use.button("Use in the calculator", icon=":material/calculate:", width="stretch"):
        st.session_state[session.CLASS] = profile.class_name
        st.session_state[session.ROLE] = profile.role
        st.session_state[session.PROFILE] = profile.id
        st.switch_page(CALCULATOR)
    if service.is_custom(profile.id):
        versions = service.history(profile.id)
        st.caption("Saved versions: " + ", ".join(versions))
        with delete.popover("Delete", icon=":material/delete:", width="stretch"):
            st.write(md(f"Delete {profile.label}? Its saved versions stay in your data folder."))
            if st.button("Delete it", type="primary", key=f"profile_delete_{profile.id}"):
                service.delete_custom(profile.id)
                st.session_state[NEXT] = _base_id(profile)
                st.session_state[FLASH] = f"Deleted {profile.label}."
                st.rerun()


def render() -> None:
    layout.page_header(
        "Build profiles",
        "The weights, caps and assumptions behind every score - and your own versions of them.",
        "profiles",
    )
    ws = open_workspace()
    if ws is None:
        return
    service = ws.profile_service
    for problem in service.problems:
        st.warning(md(f"A saved profile could not be read: {problem}"), icon=":material/warning:")
    profiles = {profile.id: profile for profile in service.all()}
    pending = st.session_state.pop(NEXT, None)
    if pending in profiles:
        st.session_state[KEY] = pending
    flash = st.session_state.pop(FLASH, None)
    if flash:
        st.success(flash, icon=":material/check:")
    first = str(session.get(session.PROFILE) or next(iter(profiles)))
    session.default(KEY, first if first in profiles else next(iter(profiles)))
    session.keep_valid(KEY, list(profiles), next(iter(profiles)))
    top = st.columns([3.2, 1.2, 0.8], vertical_alignment="bottom")
    selected = top[0].selectbox(
        "Build profile",
        list(profiles),
        format_func=lambda key: _option_label(service, profiles[key]),
        key=KEY,
    )
    if selected is None:
        return
    profile = profiles[selected]
    _manage(service, profile, top[1], top[2])
    with layout.card("profile"):
        _inspect(service, profile)
    _customize(service, profile)
