"""The Compare page (roadmap section 8): two or more items for one context, ranked, with
every item's score broken down component by component."""

from __future__ import annotations

from html import escape

import streamlit as st

from components import advanced, exports, items, recommendation
from components.html import Tone, chip, eyebrow, md, signed, tone_of
from components.item_input import picker
from views.common import setup
from wow_gear.models.comparison import ComparisonResult
from wow_gear.models.item import Item
from wow_gear.models.score import ComponentKind
from wow_gear.services.errors import DataValidationError

KEY = "compare_items"
ROUND = "compare_round"
MAX_ITEMS = 8


def _chosen() -> list[Item]:
    value = st.session_state.get(KEY, [])
    return [item for item in value if isinstance(item, Item)]


def _ranking(result: ComparisonResult) -> str:
    unit = escape(result.unit_abbreviation)
    best = next((r.score for r in result.results if r.eligible), None)
    rows = []
    for score in result.results:
        gap = "" if best is None else signed(score.score - best)
        tone = "" if best is None else tone_of(score.score - best)
        css = {"good": "wg-delta-good", "bad": "wg-delta-bad"}.get(tone, "wg-small")
        status = score.recommendation_label or ""
        status_tone: Tone = "muted"
        if score.item_id == result.winner_id:
            status_tone = "gold"
        elif not score.eligible:
            status_tone = "bad"
        rows.append(
            f'<tr><td class="wg-num">{score.rank}</td><td>{escape(score.item_name)}</td>'
            f'<td class="wg-num"><b>{score.score:.1f}</b></td>'
            f'<td class="wg-num {css}">{escape(gap)}</td>'
            f"<td>{chip(status, status_tone)}</td></tr>"
        )
    return (
        '<table class="wg-table"><thead><tr><th class="wg-num">#</th><th>Item</th>'
        f'<th class="wg-num">Score ({unit})</th><th class="wg-num">Against the best</th>'
        f"<th>Status</th></tr></thead><tbody>{''.join(rows)}</tbody></table>"
    )


def _matrix(result: ComparisonResult) -> str:
    """Every valued component, one column per item, in the ranking's order."""
    labels: dict[str, str] = {}
    values: dict[str, dict[str, float]] = {}
    for score in result.results:
        for component in score.components:
            if component.kind in (ComponentKind.PROC, ComponentKind.SET_BONUS):
                continue
            if component.weight == 0 and component.kind != ComponentKind.THRESHOLD:
                continue
            labels.setdefault(component.key, component.label)
            values.setdefault(component.key, {})[score.item_id] = component.contribution
    if not labels:
        return '<div class="wg-small">No item has a stat this profile values.</div>'
    head = "".join(
        f'<th class="wg-num" title="{escape(s.item_name)}">{escape(s.item_name)}</th>'
        for s in result.results
    )
    body = []
    for key, label in labels.items():
        cells = []
        for score in result.results:
            value = values[key].get(score.item_id)
            cells.append(
                '<td class="wg-num wg-small">-</td>'
                if value is None
                else f'<td class="wg-num">{value:.1f}</td>'
            )
        body.append(f"<tr><td>{escape(label)}</td>{''.join(cells)}</tr>")
    totals = "".join(f'<td class="wg-num"><b>{s.score:.1f}</b></td>' for s in result.results)
    body.append(f"<tr><td><b>Score</b></td>{totals}</tr>")
    return (
        f'<table class="wg-table"><thead><tr><th>Component</th>{head}</tr></thead>'
        f"<tbody>{''.join(body)}</tbody></table>"
    )


def render() -> None:
    ready = setup()
    if ready is None:
        return
    ws, profile, ruleset = ready.workspace, ready.choice.profile, ready.choice.ruleset
    chosen = _chosen()
    result: ComparisonResult | None = None

    st.write("")
    left, right = st.columns([1, 1.5], gap="large")
    with left:
        st.html(eyebrow(f"Items to compare ({len(chosen)} of up to {MAX_ITEMS})"))
        for index, item in enumerate(chosen):
            with st.container(border=True):
                row = st.container(
                    horizontal=True, horizontal_alignment="distribute", vertical_alignment="center"
                )
                row.html(
                    f'<div class="wg-item-name">{escape(item.name)}</div>'
                    f'<div class="wg-item-meta">{escape(items.type_label(item))}</div>',
                    width="content",
                )
                if row.button("Remove", key=f"compare_remove_{index}", icon=":material/close:"):
                    st.session_state[KEY] = [i for i in chosen if i.id != item.id]
                    st.rerun()
        if len(chosen) < MAX_ITEMS:
            with st.container(border=True):
                st.html(eyebrow("Add an item"))
                # A new round of keys after each add leaves an empty picker for the next.
                round_number = int(st.session_state.get(ROUND, 0))
                added = picker(f"cmp{round_number}", ws, follow=chosen[0] if chosen else None)
                if added is not None:
                    if added.id in {item.id for item in chosen}:
                        st.info(md(f"{added.name} is already in the list."))
                    else:
                        st.session_state[KEY] = [*chosen, added]
                        st.session_state[ROUND] = round_number + 1
                        st.rerun()
        if chosen and st.button("Clear the list", icon=":material/delete_sweep:"):
            st.session_state[KEY] = []
            st.rerun()

    with right:
        st.html(eyebrow("Ranking"))
        if not chosen or ready.context is None:
            st.html(
                '<div class="wg-empty"><b>Add items to rank them.</b> Every item is scored '
                "from the same gear for the profile above; the two best are explained "
                "component by component.</div>"
            )
        else:
            try:
                result = ws.calculator.compare(chosen, ready.context)
            except DataValidationError as error:
                st.error(md(f"These items cannot be compared: {error}"), icon=":material/error:")
            else:
                names = {r.item_id: r.item_name for r in result.results}
                with st.container(border=True):
                    st.html(recommendation.verdict(result, names) + _ranking(result))
                    st.html(
                        '<div class="wg-small">Recommended under this profile and these '
                        "assumptions. "
                        + chip(f"Confidence: {result.confidence.level}", "muted")
                        + "</div>"
                    )
                if result.lines and result.first_id and result.second_id:
                    st.html(
                        eyebrow(f"Why {names[result.first_id]} over {names[result.second_id]}")
                        + '<ul class="wg-why">'
                        + "".join(recommendation.line_html(line) for line in result.lines)
                        + "</ul>"
                    )
                st.html(eyebrow("Every component") + _matrix(result))
                for note in result.notes:
                    st.info(md(note), icon=":material/info:")
                exports.comparison_downloads(result, ready.context, "compare_export")

    st.write("")
    with st.expander("Assumptions", icon=":material/rule:"):
        advanced.assumptions(profile, ruleset, result)
    with st.expander("Current stats used for caps", icon=":material/tune:"):
        advanced.current_stats(profile, ruleset, ready.stats, ready.weapon_skill, {})
