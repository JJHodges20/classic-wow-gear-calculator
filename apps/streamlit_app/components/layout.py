"""The building blocks every page is laid out with: the logo, a page header, section
headers, cards, metric tiles, notes, empty states and the footer. Text is escaped; the icons
are simple SVG drawn here and embedded as data, so nothing is fetched."""

from __future__ import annotations

import base64
from collections.abc import Sequence
from dataclasses import dataclass
from html import escape
from typing import Literal

import streamlit as st
from streamlit.delta_generator import DeltaGenerator

from components.theme import Tokens, tokens

_STROKE = (
    'fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" '
    'stroke-linejoin="round"'
)
ICONS = {
    "calculator": '<rect x="4" y="3" width="16" height="18" rx="2"/><path d="M8 7h8M8 12h.01M12 12h.01M16 12h.01M8 16h.01M12 16h.01M16 16h.01"/>',
    "compare": '<path d="M7 4v13M3 13l4 4 4-4M17 20V7M13 11l4-4 4 4"/>',
    "gear": '<path d="M12 3l7 3v5c0 4.5-3 8.2-7 10-4-1.8-7-5.5-7-10V6z"/><path d="M9 12l2 2 4-4"/>',
    "profiles": '<path d="M4 6h10M18 6h2M4 12h4M12 12h8M4 18h12M20 18h0"/><circle cx="16" cy="6" r="2"/><circle cx="10" cy="12" r="2"/><circle cx="18" cy="18" r="2"/>',
    "items": '<rect x="3" y="4" width="18" height="5" rx="1"/><path d="M5 9v10a1 1 0 0 0 1 1h12a1 1 0 0 0 1-1V9M10 13h4"/>',
    "health": '<path d="M3 12h4l2-6 4 12 2-6h6"/>',
    "search": '<circle cx="11" cy="11" r="6"/><path d="M20 20l-4.5-4.5"/>',
    "plus": '<path d="M12 5v14M5 12h14"/>',
    "info": '<circle cx="12" cy="12" r="9"/><path d="M12 11v5M12 8h.01"/>',
}

Icon = Literal[
    "calculator", "compare", "gear", "profiles", "items", "health", "search", "plus", "info"
]


def icon(name: Icon) -> str:
    """The icon as an image: Streamlit's HTML sanitizer keeps images but drops inline SVG, so
    the SVG travels as a data URI, coloured for the theme in use."""
    colour = tokens().gold
    svg = (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" '
        f"{_STROKE.replace('currentColor', colour)}>{ICONS[name]}</svg>"
    )
    data = base64.b64encode(svg.encode("utf-8")).decode("ascii")
    return f'<img src="data:image/svg+xml;base64,{data}" alt="">'


def logo_svg(t: Tokens) -> str:
    """The wordmark in the top bar: a gold shield and the app's name."""
    return (
        '<svg xmlns="http://www.w3.org/2000/svg" width="236" height="32" viewBox="0 0 236 32">'
        f'<path d="M14 3l10 4v7c0 6.5-4.3 11.8-10 14-5.7-2.2-10-7.5-10-14V7z" fill="{t.gold}"/>'
        f'<path d="M9.5 15.5l3 3 6-6" fill="none" stroke="{t.surface}" stroke-width="2.4" '
        'stroke-linecap="round" stroke-linejoin="round"/>'
        f'<text x="34" y="21" fill="{t.text}" font-family="Segoe UI, Helvetica Neue, Arial, '
        'sans-serif" font-size="15.5" font-weight="650" letter-spacing="-0.1">'
        "Classic Gear Calculator</text></svg>"
    )


def page_header(title: str, lede: str, glyph: Icon) -> None:
    """The page's title and what the page is for, one sentence."""
    st.html(
        '<div class="wg-page-header">'
        f'<div class="wg-page-icon">{icon(glyph)}</div>'
        f'<div><h1 class="wg-page-title">{escape(title)}</h1>'
        f'<p class="wg-page-lede">{escape(lede)}</p></div></div>'
    )


def section(title: str, description: str | None = None, *, aside: str | None = None) -> None:
    """A section of a page: a title, an optional count or status beside it, and a line."""
    st.html(
        '<div class="wg-section">'
        f'<h2 class="wg-section-title">{escape(title)}</h2>'
        + (f'<span class="wg-section-aside">{escape(aside)}</span>' if aside else "")
        + (f'<p class="wg-section-desc">{escape(description)}</p>' if description else "")
        + "</div>"
    )


def card(key: str) -> DeltaGenerator:
    """A panel: a white surface with a hairline border and a soft shadow."""
    return st.container(border=True, key=f"wg-card-{key}")


Breakpoint = Literal["tablet", "laptop"]


def split(
    spec: Sequence[float], *, key: str, stack_below: Breakpoint = "tablet"
) -> list[DeltaGenerator]:
    """A page's side-by-side columns, which stack one under the other on a narrower screen:
    below a tablet's width (960px), or below a laptop's (1280px) where each column needs the
    room. Streamlit itself stacks columns only below 640px."""
    with st.container(key=f"wg-split-{stack_below}-{key}"):
        return st.columns(spec, gap="large")


def inset(key: str) -> DeltaGenerator:
    """A panel inside a card, such as an editor that opens under a row: a quieter surface."""
    return st.container(border=True, key=f"wg-inset-{key}")


@dataclass(frozen=True)
class Tile:
    """A metric: its label, its value and unit, and a line of context."""

    label: str
    value: str
    unit: str = ""
    context: str = ""
    tone: str = ""
    """"good" or "bad" colours the value (it also carries a sign)."""
    picked: bool = False
    text: bool = False
    """A word or a version rather than a number: shown smaller, cut with an ellipsis."""


def tiles_html(tiles: Sequence[Tile]) -> str:
    cells = []
    for tile in tiles:
        css = " wg-picked" if tile.picked else ""
        value_css = " wg-text-value" if tile.text else ""
        if tile.tone in ("good", "bad"):
            value_css += f" wg-delta-{tile.tone}"
        unit = f'<span class="wg-tile-unit">{escape(tile.unit)}</span>' if tile.unit else ""
        context = (
            f'<div class="wg-tile-context">{escape(tile.context)}</div>' if tile.context else ""
        )
        cells.append(
            f'<div class="wg-tile{css}"><div class="wg-tile-label" title="{escape(tile.label)}">'
            f"{escape(tile.label)}</div>"
            f'<div class="wg-tile-value{value_css}" title="{escape(tile.value)}">'
            f'<span class="wg-tile-number">{escape(tile.value)}</span>{unit}</div>{context}</div>'
        )
    return '<div class="wg-tiles">' + "".join(cells) + "</div>"


NoteKind = Literal["info", "warn", "problem"]


def notes_html(entries: Sequence[str | tuple[str, NoteKind]]) -> str:
    """Notes that explain a result, quieter than alerts: a dot, then the sentence."""
    items = []
    for entry in entries:
        text, kind = (entry, "info") if isinstance(entry, str) else entry
        css = "" if kind == "info" else f' class="wg-{kind}"'
        items.append(f"<li{css}>{escape(text)}</li>")
    return f'<ul class="wg-notes">{"".join(items)}</ul>' if items else ""


def notes(entries: Sequence[str | tuple[str, NoteKind]]) -> None:
    markup = notes_html(entries)
    if markup:
        st.html(markup)


def empty_state(
    title: str, body: str = "", steps: Sequence[str] = (), glyph: Icon = "info"
) -> None:
    """What to do when there is nothing to show yet."""
    listed = "".join(f"<li>{escape(step)}</li>" for step in steps)
    st.html(
        f'<div class="wg-empty"><div class="wg-empty-icon">{icon(glyph)}</div><div>'
        f'<div class="wg-empty-title">{escape(title)}</div>'
        + (f'<div class="wg-empty-body">{escape(body)}</div>' if body else "")
        + (f"<ol>{listed}</ol>" if listed else "")
        + "</div></div>"
    )


def footer(version: str) -> None:
    st.html(
        f'<div class="wg-footer">Classic Gear Calculator {escape(version)}. An unofficial fan '
        "tool: World of Warcraft is a trademark of Blizzard Entertainment. Wowhead links are for "
        "reference; the app never fetches from Wowhead.</div>"
    )
