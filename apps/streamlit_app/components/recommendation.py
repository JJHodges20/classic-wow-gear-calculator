"""The recommendation: a large result first, a short explanation, then notes.

Wording follows the roadmap: an answer is "recommended under this profile and these
assumptions", never presented as absolute truth, and a cap-sensitive comparison made without
the player's current gear totals says that it may be approximate.
"""

from __future__ import annotations

from html import escape

import streamlit as st

from components.html import chip, eyebrow, md, signed, tone_of
from state.session import Slot
from wow_gear.models.comparison import ComparisonResult, ExplanationLine

CAP_NOTE = "Cap-sensitive stats were scored without your current gear totals"


def empty() -> None:
    st.html(
        '<div class="wg-empty"><b>Choose two items to compare.</b>'
        "<ol><li>Pick your class, role and build profile above.</li>"
        "<li>Search for item A and item B, or enter one by hand.</li>"
        "<li>Enter your current gear totals under <i>Current stats</i> when a cap matters.</li>"
        "</ol></div>"
    )


def _tile(label: str, value: str, unit: str, *, picked: bool, tone: str = "") -> str:
    css = " wg-picked" if picked else ""
    value_css = f" wg-delta-{tone}" if tone in ("good", "bad") else ""
    return (
        f'<div class="wg-tile{css}"><div class="wg-tile-label" title="{escape(label)}">'
        f"{escape(label)}</div>"
        f'<div class="wg-tile-value{value_css}">{escape(value)}'
        f'<span class="wg-tile-unit">{escape(unit)}</span></div></div>'
    )


def verdict(result: ComparisonResult, names: dict[str, str]) -> str:
    unit = result.unit_abbreviation
    if result.outcome in ("winner", "only_usable") and result.winner_id:
        winner = result.result(result.winner_id)
        if result.outcome == "winner" and result.second_id:
            other = names[result.second_id]
            sub = f"{result.score_delta:.1f} {unit} more than {other} for {result.profile_label}."
        else:
            sub = "The only usable choice of these; the other item is shown for reference."
        return (
            '<div class="wg-verdict">'
            + chip("Recommended under this profile", "gold")
            + f'<div class="wg-winner">{escape(winner.item_name)}</div>'
            + f'<div class="wg-sub">{escape(sub)}</div></div>'
        )
    if result.outcome == "tie":
        return (
            '<div class="wg-verdict wg-neutral">'
            + chip("Effectively equal", "muted")
            + '<div class="wg-winner">No clear winner</div>'
            + f'<div class="wg-sub">{escape(result.headline)}</div></div>'
        )
    if result.outcome == "none_usable":
        return (
            '<div class="wg-verdict wg-neutral">'
            + chip("Not usable", "bad")
            + '<div class="wg-winner">Neither item is usable</div>'
            + '<div class="wg-sub">See the notes below for why.</div></div>'
        )
    only = result.results[0]
    return (
        '<div class="wg-verdict wg-neutral">'
        + chip("One item", "muted")
        + f'<div class="wg-winner">{escape(only.item_name)}</div>'
        + '<div class="wg-sub">Add a second item to compare.</div></div>'
    )


def _tiles(result: ComparisonResult, slots: dict[str, Slot]) -> str:
    unit = result.unit_abbreviation
    by_slot = sorted(result.results, key=lambda r: slots.get(r.item_id, "Z"))
    tiles = [
        _tile(
            f"Item {slots.get(r.item_id, '?')} · {r.item_name}",
            f"{r.score:.1f}",
            unit,
            picked=r.item_id == result.winner_id,
        )
        for r in by_slot
    ]
    if result.first_id and result.second_id and len(by_slot) == 2:
        first = slots.get(result.first_id, "?")
        second = slots.get(result.second_id, "?")
        tiles.append(
            _tile(
                f"Difference, {first} over {second}",
                signed(result.score_delta),
                unit,
                picked=False,
                tone=tone_of(result.score_delta),
            )
        )
    return '<div class="wg-tiles">' + "".join(tiles) + "</div>"


def line_html(line: ExplanationLine) -> str:
    tone = tone_of(line.delta)
    css = {"good": "wg-delta-good", "bad": "wg-delta-bad"}.get(tone, "wg-small")
    note = f'<div class="wg-note">{escape(line.note)}</div>' if line.note else ""
    return (
        f'<li><span class="wg-amount {css}">{escape(signed(line.delta))}</span>'
        f"<span>{escape(line.label)}{note}</span></li>"
    )


def render(result: ComparisonResult, slots: dict[str, Slot]) -> None:
    names = {r.item_id: r.item_name for r in result.results}
    with st.container(border=True):
        st.html(eyebrow("Recommendation") + verdict(result, names) + _tiles(result, slots))
        confidence = result.confidence
        reasons = "; ".join(confidence.reasons)
        st.html(
            '<div class="wg-small">Recommended under this profile and these assumptions. '
            + chip(f"Confidence: {confidence.level}", "muted", title=reasons or None)
            + (f" {escape(reasons)}." if reasons else "")
            + "</div>"
        )

        if result.lines:
            first = names.get(result.first_id or "", "")
            second = names.get(result.second_id or "", "")
            st.html(
                eyebrow("Why")
                + f'<div class="wg-small">Each line is what {escape(first)} gains (▲) or gives '
                f"up (▼) against {escape(second)}, in {escape(result.unit_abbreviation)}.</div>"
                + '<ul class="wg-why">'
                + "".join(line_html(line) for line in result.lines)
                + "</ul>"
            )
        elif result.first_id and result.second_id:
            st.html(eyebrow("Why") + '<div class="wg-small">Every component is equal.</div>')

    for note in result.notes:
        if note.startswith(CAP_NOTE):
            st.warning(
                md(note) + " Open *Current stats* below to enter them.", icon=":material/tune:"
            )
        elif "not usable" in note:
            st.error(md(note), icon=":material/block:")
        else:
            st.info(md(note), icon=":material/info:")
    details = []
    if result.not_valued:
        details.append("Not valued by this profile: " + ", ".join(result.not_valued) + ".")
    details.extend(f"Not scored in version 1 - {effect}" for effect in result.not_scored)
    if details:
        st.html("".join(f'<div class="wg-small">{escape(text)}</div>' for text in details))
