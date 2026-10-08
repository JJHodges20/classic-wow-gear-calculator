"""The workspace the pages work from: opened once per project and shared by every session.

Opening it reads the configuration and loads the item data, so it is cached. The project is
the one ``WOWGEAR_HOME`` names, or the folder the app was started in.
"""

from __future__ import annotations

import os
from pathlib import Path

import streamlit as st

from wow_gear.services.workspace import Workspace

HOME_VARIABLE = "WOWGEAR_HOME"


@st.cache_resource(show_spinner="Opening the item data…")
def _open(home: str) -> Workspace:
    return Workspace.open(Path(home) if home else None, configure_logs=True)


def workspace() -> Workspace:
    """The shared workspace; raises the service's error if the configuration is broken."""
    return _open(os.environ.get(HOME_VARIABLE, ""))
