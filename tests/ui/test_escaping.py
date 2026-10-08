"""Text from data never becomes markup: HTML is escaped, and Markdown too where a widget
renders it (alerts, captions, ``st.write``)."""

from __future__ import annotations

import sys
from pathlib import Path

APP = Path(__file__).resolve().parents[2] / "apps" / "streamlit_app"
if str(APP) not in sys.path:
    sys.path.insert(0, str(APP))

from components.html import chip, md  # noqa: E402


def test_markdown_in_a_name_is_shown_as_text() -> None:
    hostile = "![x](https://example.com/p.png) *bold* [link](u) $x$ `code` # head"
    escaped = md(hostile)
    for character in "![]()*$`#":
        assert f"\\{character}" in escaped
    assert "!" not in escaped.replace("\\!", "")


def test_a_windows_path_keeps_its_backslashes() -> None:
    assert md("C:\\Users\\me") == "C:\\\\Users\\\\me"


def test_html_in_a_chip_is_escaped() -> None:
    assert chip('<img src=x onerror="alert(1)">') == (
        '<span class="wg-chip">&lt;img src=x onerror=&quot;alert(1)&quot;&gt;</span>'
    )
