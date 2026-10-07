"""The Streamlit shell starts on a fixture project and renders without errors."""

from __future__ import annotations

from streamlit.testing.v1 import AppTest

from .conftest import no_exceptions, text


def test_the_app_shell_renders(app: AppTest) -> None:
    no_exceptions(app)
    assert app.title[0].value == "Classic Gear Calculator"
    assert "An unofficial fan tool" in text(app)


def test_the_calculator_starts_empty_with_a_context(app: AppTest) -> None:
    page = text(app)
    assert "Current context: Warrior › Tank › Deep Protection" in page
    assert "Choose two items to compare." in page
    assert "Draft profile" in page
