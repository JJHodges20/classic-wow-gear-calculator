"""What one browser session remembers: the chosen context, the two items, the gear totals.

Widget values live in ``st.session_state`` under the keys below; these helpers read them
with defaults so a page can build its context before the widgets are drawn.
"""

from __future__ import annotations

from typing import Any, Literal

import streamlit as st

from wow_gear.models.enums import Stat
from wow_gear.models.item import Item

Slot = Literal["A", "B"]
SLOTS: tuple[Slot, Slot] = ("A", "B")

CLASS, ROLE, PROFILE = "ctx_class", "ctx_role", "ctx_profile"
PHASE, LEVEL, CONTENT = "ctx_phase", "ctx_level", "ctx_content"
RACE, MAIN_HAND = "ctx_race", "ctx_main_hand"
EQUIPPED = "equipped"
NEITHER = "Neither"


def get(key: str, default: Any = None) -> Any:
    return st.session_state.get(key, default)


def default(key: str, value: Any) -> None:
    """Give a widget its first value, before it is drawn."""
    if key not in st.session_state:
        st.session_state[key] = value


def keep_valid(key: str, options: list[Any], fallback: Any) -> None:
    """Reset a choice that is no longer among the options (a new class has other roles)."""
    if st.session_state.get(key) not in options:
        st.session_state[key] = fallback


def item(slot: Slot) -> Item | None:
    value = st.session_state.get(f"item_{slot}")
    return value if isinstance(value, Item) else None


def set_item(slot: Slot, value: Item | None) -> None:
    st.session_state[f"item_{slot}"] = value


def total_key(stat: Stat) -> str:
    return f"total_{stat.value}"


def gear_totals(stats: list[Stat]) -> dict[Stat, float] | None:
    """The totals entered for ``stats``; None when none was entered (caps measured from 0)."""
    entered = {
        stat: float(value)
        for stat in stats
        if (value := st.session_state.get(total_key(stat))) is not None
    }
    return entered or None
