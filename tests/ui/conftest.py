"""App tests run the Streamlit app under ``streamlit.testing`` on a throwaway project with the
fixture dataset and no credentials - never on the user's data."""

from __future__ import annotations

import re
from collections.abc import Callable
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

APP = Path(__file__).resolve().parents[2] / "apps" / "streamlit_app" / "app.py"
SECRETS = ("WOWGEAR_BLIZZARD_CLIENT_ID", "WOWGEAR_BLIZZARD_CLIENT_SECRET")


@pytest.fixture
def app_home(project: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setenv("WOWGEAR_HOME", str(project))
    for name in SECRETS:
        monkeypatch.delenv(name, raising=False)
    return project


@pytest.fixture
def open_app(app_home: Path) -> Callable[[], AppTest]:
    def start() -> AppTest:
        return AppTest.from_file(str(APP), default_timeout=60).run()

    return start


@pytest.fixture
def app(open_app: Callable[[], AppTest]) -> AppTest:
    return open_app()


def text(at: AppTest) -> str:
    """Everything the page shows as text: custom HTML, markdown, captions and alerts."""
    parts = [str(getattr(element.proto, "body", "")) for element in at.get("html")]
    parts += [element.value for element in at.markdown]
    parts += [element.value for element in at.caption]
    parts += [element.value for element in (*at.warning, *at.info, *at.error)]
    plain = re.sub(r"<style>.*?</style>", " ", " ".join(parts), flags=re.S)
    plain = re.sub(r"<[^>]+>", " ", plain)
    plain = plain.replace("&nbsp;", " ").replace("&#x27;", "'").replace("&amp;", "&")
    return re.sub(r"\s+", " ", plain)


def no_exceptions(at: AppTest) -> None:
    assert not at.exception, [error.value for error in at.exception]


def pick(at: AppTest, slot: str, query: str, item_id: str) -> None:
    """Search for ``query`` in item ``slot`` and choose ``item_id`` from the results."""
    at.text_input(key=f"search_{slot}").input(query).run()
    no_exceptions(at)
    at.selectbox(key=f"pick_{slot}:{query.lower()}").select(item_id).run()
    no_exceptions(at)
