"""The calculator page, driven like a player would (roadmap section 11, UI tests): choose a
class, role and profile; find items and compare them; enter one by hand; change the current
stats; and survive a failing provider."""

from __future__ import annotations

from collections.abc import Callable

import httpx
import pytest
from streamlit.testing.v1 import AppTest

from tests.integration.conftest import blizzard_handler
from wow_gear.data_sources.blizzard import BlizzardClient
from wow_gear.models.enums import ArmorType, ItemSlot
from wow_gear.services.workspace import OnlineSetup, Workspace

from .conftest import no_exceptions, pick, text

LIONHEART, MASK = "classic_era:12640", "classic_era:13404"
TRUESTRIKE, DRAKE_TALON = "classic_era:12927", "classic_era:19394"
ROBE_OF_THE_ARCHMAGE = "classic_era:14152"


def fury(at: AppTest) -> None:
    at.selectbox(key="ctx_role").select("melee_dps").run()
    at.selectbox(key="ctx_profile").select("warrior_dps_fury").run()
    no_exceptions(at)
    assert at.selectbox(key="ctx_profile").value == "warrior_dps_fury"


def test_choosing_class_role_and_profile(app: AppTest) -> None:
    assert app.selectbox(key="ctx_class").value == "warrior"
    assert app.selectbox(key="ctx_profile").value == "warrior_tank_deep_prot"
    app.selectbox(key="ctx_class").select("mage").run()
    no_exceptions(app)
    assert app.selectbox(key="ctx_role").value == "caster_dps"
    assert app.selectbox(key="ctx_profile").value == "mage_dps_frost"
    assert "Current context: Mage › Caster DPS › Frost (raid)" in text(app)
    app.selectbox(key="ctx_class").select("priest").run()  # the role stays caster DPS
    assert app.selectbox(key="ctx_profile").value == "priest_dps_shadow"
    app.selectbox(key="ctx_role").select("healer").run()
    assert app.selectbox(key="ctx_profile").value == "priest_healer_holy"


def test_search_finds_items_and_the_comparison_explains_itself(app: AppTest) -> None:
    fury(app)
    pick(app, "A", "lionheart", LIONHEART)
    assert "Lionheart Helm" in text(app) and "One item" in text(app)
    assert app.selectbox(key="slot_filter_B").value == "head"  # follows item A
    pick(app, "B", "mask", MASK)
    page = text(app)
    assert "Recommended under this profile" in page
    assert "56.0 AP more than Mask of the Unforgiven for Fury (dual wield)." in page
    assert "Strength into attack power" in page
    assert "Recommended under this profile and these assumptions." in page
    assert any("without your current gear totals" in w.value for w in app.warning)


def test_current_stats_change_a_cap_sensitive_recommendation(app: AppTest) -> None:
    fury(app)
    app.selectbox(key="ctx_phase").select(3).run()
    pick(app, "A", "truestrike", TRUESTRIKE)
    pick(app, "B", "drake talon", DRAKE_TALON)
    app.number_input(key="total_hit").set_value(5).run()
    no_exceptions(app)
    assert "4.0 AP more than Drake Talon Pauldrons" in text(app)
    assert not any("without your current gear totals" in w.value for w in app.warning)
    app.number_input(key="total_hit").set_value(9).run()
    no_exceptions(app)
    page = text(app)
    assert "16.0 AP more than Truestrike Shoulders" in page
    assert "Truestrike Shoulders: 1 of its 2 counts" in page


def test_the_equipped_item_comes_out_of_the_totals(app: AppTest) -> None:
    fury(app)
    pick(app, "A", "lionheart", LIONHEART)
    pick(app, "B", "mask", MASK)
    app.number_input(key="total_hit").set_value(9).run()
    assert "Item A · Lionheart Helm 96.0 AP" in text(app)  # its hit lands past the cap
    app.radio(key="equipped").set_value("Item B").run()  # the 9% includes the mask's 2%
    no_exceptions(app)
    assert "Item A · Lionheart Helm 116.0 AP" in text(app)  # from 7%, all of it counts


def test_a_manual_item_is_previewed_validated_and_scored(app: AppTest) -> None:
    fury(app)
    pick(app, "A", "lionheart", LIONHEART)
    app.segmented_control(key="mode_B").set_value("Enter manually").run()
    no_exceptions(app)
    app.text_input(key="manual_B_name").input("Theorycrafted Helm").run()
    app.selectbox(key="manual_B_slot").select(ItemSlot.HEAD).run()
    app.selectbox(key="manual_B_type").select(ArmorType.PLATE).run()
    app.number_input(key="manual_B_stat_strength").set_value(30).run()
    app.number_input(key="manual_B_stat_hit").set_value(1).run()
    app.button(key="manual_B_check").click().run()
    no_exceptions(app)
    assert "Preview" in text(app) and "+30 Strength" in text(app)
    app.button(key="manual_B_use").click().run()
    no_exceptions(app)
    page = text(app)
    assert "Theorycrafted Helm" in page
    assert "Entered by hand (theorycrafted)" in page
    assert "Lionheart Helm" in page and "AP more than Theorycrafted Helm" in page


def test_an_invalid_manual_item_cannot_be_used(app: AppTest) -> None:
    app.segmented_control(key="mode_A").set_value("Enter manually").run()
    app.button(key="manual_A_check").click().run()
    no_exceptions(app)
    assert any("name" in error.value for error in app.error)
    with pytest.raises(KeyError):
        app.button(key="manual_A_use")


def test_an_unusable_item_is_explained(app: AppTest) -> None:
    app.selectbox(key="ctx_class").select("mage").run()
    pick(app, "A", "robe of the archmage", ROBE_OF_THE_ARCHMAGE)
    app.selectbox(key="slot_filter_B").select("any").run()
    pick(app, "B", "lionheart", LIONHEART)
    errors = [error.value for error in app.error]
    assert any("Lionheart Helm is not usable: Mages cannot wear plate armor" in e for e in errors)
    assert any("worn in different slots" in info.value for info in app.info)


def test_a_failing_provider_leaves_a_message_and_local_results(
    open_app: Callable[[], AppTest], monkeypatch: pytest.MonkeyPatch
) -> None:
    client = BlizzardClient(
        "test-id", "test-secret", transport=httpx.MockTransport(blizzard_handler("connect"))
    )
    monkeypatch.setattr(
        Workspace, "_online_setup", lambda self: OnlineSetup(client, "ok", "Injected")
    )
    app = open_app()
    app.toggle(key="online_A").set_value(True).run()
    app.text_input(key="search_A").input("lionheart").run()
    no_exceptions(app)
    assert any("Online lookup failed" in warning.value for warning in app.warning)
    app.selectbox(key="pick_A:lionheart").select(LIONHEART).run()
    assert "Lionheart Helm" in text(app)
