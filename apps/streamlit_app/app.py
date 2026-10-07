"""Classic Gear Calculator: the Streamlit entry point.

The shell sets the page up, applies the design system, and hands over to the page the
navigation selects. Pages call ``wow_gear.services`` and never a provider, a repository or
a formula directly. Each page is a small script in ``pages/`` that draws its view from
``views/``.
"""

from __future__ import annotations

import streamlit as st

from components import theme
from state import session
from wow_gear import __version__

st.set_page_config(
    page_title="Classic Gear Calculator",
    page_icon=":material/shield:",
    layout="wide",
    initial_sidebar_state="collapsed",
)
theme.inject()
session.keep_across_pages()

page = st.navigation(
    [
        st.Page(
            "pages/calculator.py",
            title="Calculator",
            icon=":material/calculate:",
            url_path="calculator",
            default=True,
        ),
        st.Page(
            "pages/compare.py",
            title="Compare",
            icon=":material/compare_arrows:",
            url_path="compare",
        ),
        st.Page(
            "pages/profiles.py",
            title="Build profiles",
            icon=":material/tune:",
            url_path="profiles",
        ),
        st.Page(
            "pages/item_database.py",
            title="Item database",
            icon=":material/inventory_2:",
            url_path="items",
        ),
        st.Page(
            "pages/data_health.py",
            title="Data health",
            icon=":material/monitor_heart:",
            url_path="health",
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
