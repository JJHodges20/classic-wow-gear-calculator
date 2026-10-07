"""The Gear set page (roadmap V1.5): build, save, analyse and change a character's gear.

Fury values by hand, as in the service tests: Lionheart Helm is worth 96 and Mask of the
Unforgiven 40 to a character without a weapon skill bonus.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from streamlit.testing.v1 import AppTest

from wow_gear.core import load_settings
from wow_gear.models.enums import EquipmentSlot
from wow_gear.services.workspace import Workspace

from .conftest import no_exceptions, text

LIONHEART, MASK = "classic_era:12640", "classic_era:13404"


def flashed(app: AppTest) -> list[str]:
    return [element.value for element in app.success]


def open_gear(open_app: Callable[[], AppTest]) -> AppTest:
    app = open_app()
    app.switch_page("pages/gear_set.py").run()
    no_exceptions(app)
    return app


def save_character(project: Path, *items: tuple[EquipmentSlot, str]) -> None:
    """A saved Fury character on the project, before the app opens it."""
    workspace = Workspace(load_settings(project, environment={}))
    try:
        service = workspace.characters
        character = service.new("Grom", "warrior_dps_fury")
        for slot, item_id in items:
            character = service.equip(character, slot, item_id)
        service.save(character)
    finally:
        workspace.close()


def test_a_new_character_is_built_and_saved(open_app: Callable[[], AppTest]) -> None:
    app = open_gear(open_app)
    assert "Add your gear to analyse it." in text(app)
    app.text_input(key="gear_name_1").input("Grom").run()
    app.selectbox(key="gear_profile_1").select("warrior_dps_fury").run()
    no_exceptions(app)
    app.button(key="gear_change_head").click().run()
    app.text_input(key="search_gear0").input("lionheart").run()
    app.selectbox(key="pick_gear0:lionheart").select(LIONHEART).run()
    no_exceptions(app)
    page = text(app)
    assert "Lionheart Helm" in page and "96.0 AP" in page
    assert "Unsaved changes" in page
    app.button(key="gear_save").click().run()
    no_exceptions(app)
    assert app.selectbox(key="gear_choice").value == "grom"
    assert flashed(app) == ["Saved Grom (version 1)."]
    assert "Unsaved changes" not in text(app)


def test_trying_a_replacement_and_putting_it_on(
    open_app: Callable[[], AppTest], app_home: Path
) -> None:
    save_character(app_home, (EquipmentSlot.HEAD, LIONHEART))
    app = open_gear(open_app)
    assert app.selectbox(key="gear_choice").value == "grom"
    assert "Gear value" in text(app)
    app.text_input(key="search_try0").input("mask").run()
    app.selectbox(key="pick_try0:mask").select(MASK).run()
    no_exceptions(app)
    page = text(app)
    assert "Worse for the whole character" in page
    assert "−56.0" in page and "replacing Lionheart Helm" in page
    app.button(key="gear_try_equip").click().run()
    no_exceptions(app)
    assert flashed(app) == ["Mask of the Unforgiven is on. Save to keep the change."]
    assert "Unsaved changes" in text(app)


def test_emptying_a_slot_and_deleting_the_character(
    open_app: Callable[[], AppTest], app_home: Path
) -> None:
    save_character(app_home, (EquipmentSlot.HEAD, LIONHEART))
    app = open_gear(open_app)
    app.button(key="gear_change_head").click().run()
    app.button(key="gear_empty_head").click().run()
    no_exceptions(app)
    assert "Add your gear to analyse it." in text(app)
    app.button(key="gear_delete_confirm").click().run()
    no_exceptions(app)
    assert flashed(app) == ["Deleted Grom."]
    assert app.selectbox(key="gear_choice").options == ["New character"]


def test_the_gear_totals_go_to_the_calculator(
    open_app: Callable[[], AppTest], app_home: Path
) -> None:
    save_character(app_home, (EquipmentSlot.HEAD, LIONHEART))
    app = open_gear(open_app)
    app.button(key="gear_use_totals").click().run()
    no_exceptions(app)
    assert app.session_state["ctx_profile"] == "warrior_dps_fury"
    assert app.session_state["total_hit"] == 2.0
    assert app.session_state["total_sword_skill"] == 0.0  # no weapon skill on this gear
    assert app.number_input(key="total_hit").value == 2.0
