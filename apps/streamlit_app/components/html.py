"""Small HTML pieces for the custom parts of the page. Every value is escaped: item names and
effect texts come from data files and imports, never trusted as markup."""

from __future__ import annotations

from collections.abc import Iterable
from html import escape
from typing import Literal

import streamlit as st

Tone = Literal["neutral", "good", "bad", "gold", "muted"]


def show(markup: str) -> None:
    st.html(markup)


def chip(text: str, tone: Tone = "neutral", title: str | None = None) -> str:
    tip = f' title="{escape(title)}"' if title else ""
    css = "" if tone == "neutral" else f" wg-{tone}"
    return f'<span class="wg-chip{css}"{tip}>{escape(text)}</span>'


def chips(parts: Iterable[str]) -> str:
    """A wrapping row of chips (already built with ``chip``)."""
    inner = "".join(parts)
    return f'<div class="wg-chips">{inner}</div>' if inner else ""


def signed(value: float, digits: int = 1) -> str:
    """A difference with its direction in text as well as colour: "▲ +6.6", "▼ −3.8", "0"."""
    if abs(value) < 0.5 * 10**-digits:
        return "0"
    arrow = "▲" if value > 0 else "▼"
    number = f"{abs(value):.{digits}f}"
    return f"{arrow} {'+' if value > 0 else '−'}{number}"


def tone_of(value: float, digits: int = 1) -> Tone:
    if abs(value) < 0.5 * 10**-digits:
        return "muted"
    return "good" if value > 0 else "bad"


def eyebrow(text: str) -> str:
    return f'<div class="wg-eyebrow">{escape(text)}</div>'


def small(text: str) -> str:
    return f'<div class="wg-small">{escape(text)}</div>'
