"""The advanced tabs under the result: assumptions, caps, current stats and the raw math.

A first-time user never needs them; a theorycrafter can check every number. The current
stats tab holds the inputs that change a cap-sensitive answer.
"""

from __future__ import annotations

from html import escape

import streamlit as st

from components.items import stat_label
from state import session
from wow_gear.models.comparison import ComparisonResult
from wow_gear.models.enums import WEAPON_SKILL_STATS, Stat, WeaponType
from wow_gear.models.item import Item
from wow_gear.models.labels import weapon_label
from wow_gear.models.profile import BuildProfile
from wow_gear.models.ruleset import Ruleset
from wow_gear.reporting.text import comparison_text

TABS = ["Assumptions", "Caps", "Current stats", "Raw math"]


def _list(lines: list[str]) -> str:
    return "<ul>" + "".join(f"<li>{escape(line)}</li>" for line in lines) + "</ul>"


def _assumptions(profile: BuildProfile, ruleset: Ruleset, result: ComparisonResult | None) -> None:
    st.markdown(
        f"**{profile.label}** · {profile.id} {profile.version} · {profile.validation_status}"
    )
    st.caption(profile.summary)
    rows = "".join(
        f"<tr><td>{escape(stat_label(weight.stat, ruleset))}</td>"
        f'<td class="wg-num">{weight.weight:g}</td><td>{escape(weight.basis.value)}</td>'
        f"<td>{escape(weight.note or '')}</td></tr>"
        for weight in profile.stat_weights
    )
    st.html(
        '<table class="wg-table"><thead><tr><th>Stat</th><th class="wg-num">Weight</th>'
        f"<th>Basis</th><th>Note</th></tr></thead><tbody>{rows}</tbody></table>"
    )
    lines = []
    for rule in profile.derived_stats:
        conversion = ruleset.conversion(profile.class_name, rule.conversion)
        source, target = stat_label(rule.source, ruleset), stat_label(rule.target, ruleset)
        target_def = ruleset.stat_def(rule.target)
        one = "1%" if target_def is not None and target_def.unit == "percent" else "1"
        if conversion is not None and conversion.per_point is not None:
            lines.append(
                f"{source} counts as {target.lower()}: {conversion.per_point:g} "
                f"{target.lower()} per point of {source}."
            )
        elif conversion is not None and conversion.points_per_unit is not None:
            lines.append(
                f"{source} counts as {target.lower()}: {conversion.points_per_unit:g} "
                f"{source} per {one} {target.lower()}."
            )
    if result is not None and result.results:
        lines.extend(result.results[0].assumptions)
    else:
        lines.extend(profile.assumptions)
    lines.extend(profile.proc_assumptions)
    lines.extend(profile.set_bonus_rules)
    st.html(_list(lines))
    if profile.sources:
        st.caption("Sources")
        st.html(
            "<ul>"
            + "".join(
                f'<li><a href="{escape(source.url)}" target="_blank" rel="noopener noreferrer">'
                f"{escape(source.title)}</a> (read {escape(str(source.retrieved))})</li>"
                for source in profile.sources
            )
            + "</ul>"
        )


def _caps(result: ComparisonResult | None) -> None:
    if result is None:
        st.caption("Caps and breakpoints show here once an item is scored.")
        return
    messages: list[str] = []
    for score in result.results:
        messages.extend(f"{score.item_name}: {event.message}" for event in score.capped_stats)
        messages.extend(f"{score.item_name}: {event.message}" for event in score.threshold_events)
    if messages:
        st.html(_list(messages))
    else:
        st.caption("No cap or breakpoint changed either item's value with these gear totals.")
    derivations = [line for line in result.results[0].assumptions if " cap: " in line]
    if derivations:
        st.caption("How the caps were worked out")
        st.html(_list(derivations))


def current_stats(
    profile: BuildProfile,
    ruleset: Ruleset,
    stats: list[Stat],
    weapon_skill: bool,
    chosen: dict[str, Item | None],
) -> None:
    st.caption(
        "Enter what your other gear adds up to - the tooltip totals, not the character sheet. "
        "Only stats with a cap or a breakpoint change the answer, so only those are asked for."
    )
    columns = st.columns(3)
    names = [f"Item {slot}" for slot, item in chosen.items() if item is not None]
    if names:
        columns[0].radio(
            "Which of these are you wearing now?",
            [session.NEITHER, *names],
            key=session.EQUIPPED,
            help="Its stats are taken out of your totals before the items are compared.",
        )
    if weapon_skill:
        races = [race for race in ruleset.class_def(profile.class_name).races]
        columns[1].selectbox(
            "Race",
            [None, *races],
            format_func=lambda value: (
                "Not given" if value is None else ruleset.race_def(value).label
            ),
            key=session.RACE,
            help="Racial weapon skill lowers the hit cap with that weapon type.",
        )
        weapons = [
            w for w in ruleset.class_def(profile.class_name).weapons if w in WEAPON_SKILL_STATS
        ]
        columns[2].selectbox(
            "Main-hand weapon",
            [None, *weapons],
            format_func=lambda value: "Not given" if value is None else weapon_label(value),
            key=session.MAIN_HAND,
        )
    if not stats:
        st.info(
            "No stat in this profile has a cap or a breakpoint: your gear totals do not "
            "change its scores.",
            icon=":material/check_circle:",
        )
        return
    fields = st.columns(4)
    for index, stat in enumerate(stats):
        stat_def = ruleset.stat_def(stat)
        unit = " (%)" if stat_def is not None and stat_def.unit == "percent" else ""
        fields[index % 4].number_input(
            f"{stat_label(stat, ruleset)}{unit}",
            min_value=0.0,
            value=None,
            step=1.0,
            format="%g",
            key=session.total_key(stat),
            placeholder="Not given",
        )
    if st.button("Clear totals", icon=":material/backspace:"):
        for stat in stats:
            st.session_state.pop(session.total_key(stat), None)
        st.rerun()


def weapon_skill_stat(main_hand: WeaponType | None) -> Stat | None:
    return WEAPON_SKILL_STATS.get(main_hand) if main_hand is not None else None


def _raw_math(result: ComparisonResult | None) -> None:
    if result is None:
        st.caption("The full breakdown shows here once an item is scored.")
        return
    for score in result.results:
        st.markdown(f"**{score.item_name}** - {score.score:.2f} {result.unit_abbreviation}")
        rows = [
            {
                "Component": component.label,
                "Kind": component.kind.value,
                "Amount": component.amount,
                "Counts": component.effective_amount,
                "Weight": component.weight,
                "Contribution": component.contribution,
                "Note": component.note or "",
            }
            for component in score.components
        ]
        number = st.column_config.NumberColumn(format="%.3f")
        st.dataframe(
            rows,
            hide_index=True,
            width="stretch",
            column_config={
                "Amount": number,
                "Counts": number,
                "Weight": number,
                "Contribution": number,
            },
        )
        st.caption(
            f"Item {score.item_id} ({score.item_provider}, {score.item_data_version}); "
            f"profile {score.profile_id} {score.profile_version} ({score.profile_hash[:10]}); "
            f"ruleset {score.ruleset_id} {score.ruleset_version} ({score.ruleset_hash[:10]}); "
            f"engine {score.engine_version}; fingerprint {score.context_fingerprint}."
        )
    with st.expander("The whole comparison as text"):
        st.code(comparison_text(result), language=None)


def render(
    profile: BuildProfile,
    ruleset: Ruleset,
    result: ComparisonResult | None,
    stats: list[Stat],
    weapon_skill: bool,
    chosen: dict[str, Item | None],
) -> None:
    assumptions, caps, current, raw = st.tabs(TABS)
    with assumptions:
        _assumptions(profile, ruleset, result)
    with caps:
        _caps(result)
    with current:
        current_stats(profile, ruleset, stats, weapon_skill, chosen)
    with raw:
        _raw_math(result)
