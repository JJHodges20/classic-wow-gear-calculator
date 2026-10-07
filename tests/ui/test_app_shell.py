"""The Streamlit shell starts and renders without errors."""

from __future__ import annotations

from pathlib import Path

from streamlit.testing.v1 import AppTest

APP = Path(__file__).resolve().parents[2] / "apps" / "streamlit_app" / "app.py"


def test_the_app_shell_renders() -> None:
    app = AppTest.from_file(str(APP), default_timeout=30).run()
    assert not app.exception, [error.value for error in app.exception]
    assert app.title[0].value == "Classic Gear Calculator"
