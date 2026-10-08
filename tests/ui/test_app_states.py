"""States a player can run into: a manual item kept for later, a tooltip read into the form,
a broken configuration, a missing item dataset, and a context that cannot be scored."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from streamlit.testing.v1 import AppTest

from wow_gear.core import load_settings
from wow_gear.models.enums import ArmorType, ItemSlot
from wow_gear.services.workspace import Workspace

from .conftest import no_exceptions, text

TOOLTIP = "\n".join(
    [
        "Lionheart Helm",
        "Binds when equipped",
        "Head\tPlate",
        "565 Armor",
        "+18 Strength",
        "Requires Level 56",
        "Equip: Improves your chance to get a critical strike by 2%.",
        "Equip: Improves your chance to hit by 2%.",
    ]
)


def test_a_manual_item_can_be_kept_in_your_items(app: AppTest, app_home: Path) -> None:
    app.segmented_control(key="mode_A").set_value("Enter manually").run()
    app.text_input(key="manual_A_name").input("Kept Helm").run()
    app.selectbox(key="manual_A_slot").select(ItemSlot.HEAD).run()
    app.selectbox(key="manual_A_type").select(ArmorType.PLATE).run()
    app.number_input(key="manual_A_stat_strength").set_value(12).run()
    app.button(key="manual_A_check").click().run()
    app.button(key="manual_A_keep").click().run()
    no_exceptions(app)
    assert [success.value for success in app.success] == ["Kept Helm is kept in your items\\."]
    workspace = Workspace(load_settings(app_home, environment={}))
    try:
        hits = workspace.search.search("kept helm").hits
    finally:
        workspace.close()
    assert [(hit.item.name, hit.origin) for hit in hits] == [("Kept Helm", "user")]


def test_reading_a_tooltip_fills_the_form(app: AppTest) -> None:
    app.segmented_control(key="mode_A").set_value("Enter manually").run()
    app.text_area(key="manual_A_tooltip").input(TOOLTIP).run()
    app.button(key="manual_A_read").click().run()
    no_exceptions(app)
    assert app.text_input(key="manual_A_name").value == "Lionheart Helm"
    assert app.number_input(key="manual_A_stat_strength").value == 18
    assert app.number_input(key="manual_A_stat_hit").value == 2


def test_a_broken_configuration_explains_itself(
    open_app: Callable[[], AppTest], app_home: Path
) -> None:
    (app_home / "configs" / "app.yaml").write_text("app: {name: x}\n", encoding="utf-8")
    app = open_app()
    no_exceptions(app)
    errors = [error.value for error in app.error]
    assert errors and errors[0].startswith("The calculator could not start")


def test_a_missing_item_dataset_leaves_manual_entry(
    open_app: Callable[[], AppTest], app_home: Path, tmp_path: Path
) -> None:
    empty = tmp_path / "no_dataset"
    empty.mkdir()
    settings = app_home / "configs" / "app.yaml"
    text_now = settings.read_text(encoding="utf-8")
    start = text_now.index("bundled_dir:")
    end = text_now.index("\n", start)
    settings.write_text(
        text_now[:start] + f"bundled_dir: {empty.as_posix()}" + text_now[end:], encoding="utf-8"
    )
    app = open_app()
    no_exceptions(app)
    assert any("No bundled dataset" in warning.value for warning in app.warning)
    assert app.segmented_control(key="mode_A").options == ["Search", "Enter manually"]


def test_a_context_that_cannot_be_scored_is_explained(app: AppTest) -> None:
    app.selectbox(key="ctx_role").select("melee_dps").run()
    app.session_state["ctx_race"] = "tauren"  # chosen for a warrior, then the class changes
    app.selectbox(key="ctx_class").select("paladin").run()
    no_exceptions(app)
    assert any("This context cannot be scored" in error.value for error in app.error)
    assert "Choose two items to compare" in text(app)
