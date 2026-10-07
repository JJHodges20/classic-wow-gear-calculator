"""Classic Gear Calculator: the Streamlit entry point.

The shell sets the page up, applies the design system, and hands over to the page the
navigation selects. Pages call ``wow_gear.services`` and never a provider, a repository or
a formula directly.
"""

from __future__ import annotations

import streamlit as st

from components import theme
from pages import calculator
from wow_gear import __version__

st.set_page_config(
    page_title="Classic Gear Calculator",
    page_icon=":material/shield:",
    layout="wide",
    initial_sidebar_state="collapsed",
)
theme.inject()

page = st.navigation(
    [
        st.Page(
            calculator.render,
            title="Calculator",
            icon=":material/calculate:",
            url_path="calculator",
            default=True,
        ),
    ],
    position="top",
)
st.title("Classic Gear Calculator")
st.caption("Explainable gear comparisons for World of Warcraft Classic Era.")
page.run()

st.divider()
st.caption(
    f"Version {__version__}. An unofficial fan tool: World of Warcraft is a trademark of Blizzard "
    "Entertainment. Wowhead links are for reference; the app never fetches from Wowhead."
)
