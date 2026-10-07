"""The Compare, Build Profiles, Item Database and Data Health pages (roadmap section 8)."""

from __future__ import annotations

from collections.abc import Callable

from streamlit.testing.v1 import AppTest

from .conftest import no_exceptions, text

LIONHEART, MASK, GOLDMINER = "classic_era:12640", "classic_era:13404", "classic_era:9375"


def open_page(open_app: Callable[[], AppTest], page: str) -> AppTest:
    app = open_app()
    app.switch_page(f"pages/{page}.py").run()
    no_exceptions(app)
    return app


def add(app: AppTest, query: str, item_id: str, round_number: int) -> None:
    app.text_input(key=f"search_cmp{round_number}").input(query).run()
    app.selectbox(key=f"pick_cmp{round_number}:{query}").select(item_id).run()
    no_exceptions(app)


def test_compare_ranks_several_items_and_shows_every_component(
    open_app: Callable[[], AppTest],
) -> None:
    app = open_page(open_app, "compare")
    assert "Add items to rank them." in text(app)
    app.selectbox(key="ctx_role").select("melee_dps").run()
    app.selectbox(key="ctx_phase").select(6).run()
    app.number_input(key="ctx_level").set_value(60).run()
    add(app, "lionheart", LIONHEART, 0)
    add(app, "mask", MASK, 1)
    add(app, "goldminer", GOLDMINER, 2)
    assert app.text_input(key="search_cmp3").value == ""  # an empty picker for the next
    page = text(app)
    assert "Items to compare (3 of up to 8)" in page
    assert "Recommended under this profile" in page and "Lionheart Helm" in page
    assert "Why Lionheart Helm over Mask of the Unforgiven" in page
    assert "Every component" in page and "Strength into attack power" in page
    app.button(key="compare_remove_0").click().run()
    assert "Items to compare (2 of up to 8)" in text(app)


def test_profiles_page_shows_weights_caps_and_sources(open_app: Callable[[], AppTest]) -> None:
    app = open_page(open_app, "profiles")
    app.selectbox(key="profiles_page_profile").select("warrior_dps_fury").run()
    no_exceptions(app)
    page = text(app)
    assert "Stat weights" in page and "sourced" in page
    assert "Strength → Attack power: 2 per point of Strength" in page
    assert "Hit soft cap: 9" in page
    assert "Sixty Upgrades: Fury EP preset" in page


def test_saving_a_custom_profile_from_the_page(open_app: Callable[[], AppTest]) -> None:
    app = open_page(open_app, "profiles")
    app.selectbox(key="profiles_page_profile").select("mage_dps_frost").run()
    app.text_input(key="profile_name_mage_dps_frost").input("My Frost").run()
    app.button(key="profile_save_mage_dps_frost").click().run()
    no_exceptions(app)
    assert app.selectbox(key="profiles_page_profile").value == "custom_my_frost"
    page = text(app)
    assert "Yours" in page and "custom_my_frost 1.0.0" in page


def test_item_database_filters_and_pages(open_app: Callable[[], AppTest]) -> None:
    app = open_page(open_app, "item_database")
    page = text(app)
    assert "17 items here: 17 from the bundled dataset" in page
    assert "Page 1 of 1 · 17 items" in page
    app.selectbox(key="db_slot").select("head").run()
    no_exceptions(app)
    assert "Page 1 of 1 · 3 items" in text(app)
    app.text_input(key="db_text").input("lionheart").run()
    assert "1 found" in text(app)


def test_data_health_reports_and_refreshes(open_app: Callable[[], AppTest]) -> None:
    app = open_page(open_app, "data_health")
    page = text(app)
    assert "fixture-3" in page and "17 items" in page
    assert "Credentials not set; see .env.example" in page
    assert "No provider has been called yet" in page
    app.button[0].click().run()  # Drop expired lookups now
    no_exceptions(app)
    assert any("Dropped 0 expired lookup(s)" in s.value for s in app.success)
