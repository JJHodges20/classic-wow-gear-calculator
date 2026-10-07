"""Classic Gear Calculator: the Streamlit entry point.

Milestone 1 ships the shell only; the calculator pages arrive in milestone 7. The app calls
``wow_gear.services`` and never a provider, a repository or a formula directly.
"""

from __future__ import annotations

import streamlit as st

from wow_gear import __version__

st.set_page_config(page_title="Classic Gear Calculator", layout="wide")
st.title("Classic Gear Calculator")
st.caption(f"Version {__version__}. Foundation build: the calculator pages arrive in milestone 7.")
