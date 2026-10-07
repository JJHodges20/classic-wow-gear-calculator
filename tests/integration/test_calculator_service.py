"""The calculator service: choosing a context, and search result -> score -> comparison output
(roadmap section 11, integration tests), with the fixture dataset and a fake Blizzard API."""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path

import pytest
from typer.testing import CliRunner

from wow_gear.cli import app
from wow_gear.core.errors import DataValidationError, NotFoundError
from wow_gear.models.enums import ArmorType, ClassName, ContentMode, ItemSlot, Role, Stat
from wow_gear.models.forms import ManualItemForm
from wow_gear.models.item import Item
from wow_gear.services.workspace import Workspace

Opener = Callable[..., Workspace]
LIONHEART, MASK = "classic_era:12640", "classic_era:13404"


class TestChoosingAContext:
    def test_the_selector_lists_classes_roles_and_profiles(self, open_workspace: Opener) -> None:
        calculator = open_workspace().calculator
        classes = dict(calculator.classes("classic_era"))
        assert classes[ClassName.WARRIOR] == "Warrior" and ClassName.PRIEST in classes
        roles = dict(calculator.roles("classic_era", ClassName.WARRIOR))
        assert roles == {Role.TANK: "Tank", Role.MELEE_DPS: "Melee DPS"}
        fury = calculator.profiles("classic_era", ClassName.WARRIOR, Role.MELEE_DPS)
        assert [profile.id for profile in fury] == ["warrior_dps_fury"]

    def test_unchosen_values_come_from_the_profile(self, open_workspace: Opener) -> None:
        workspace = open_workspace()
        context = workspace.calculator.context("warrior_dps_fury")
        assert (context.class_name, context.role, context.level) == (
            ClassName.WARRIOR,
            Role.MELEE_DPS,
            60,
        )
        assert context.content_mode == ContentMode.RAID
        assert context.phase == workspace.ruleset.default_phase
        assert context.current_stats is None

    @pytest.mark.parametrize(
        ("profile", "choices", "reason"),
        [
            ("warrior_dps_fury", {"level": 75}, "outside 1-60"),
            ("warrior_dps_fury", {"phase": 9}, "has no phase 9"),
            ("warrior_dps_fury", {"class_name": "mage"}, "profile is for a warrior melee dps"),
            ("mage_dps_frost", {"race": "tauren"}, "a tauren cannot be a Mage"),
            ("warrior_dps_fury", {"current_stats": {"speed": 3}}, "current_stats"),
        ],
    )
    def test_impossible_choices_are_explained(
        self, open_workspace: Opener, profile: str, choices: dict[str, object], reason: str
    ) -> None:
        with pytest.raises(DataValidationError, match=reason):
            open_workspace().calculator.context(profile, **choices)


class TestComparing:
    def test_search_result_to_score_to_comparison(self, open_workspace: Opener) -> None:
        workspace = open_workspace()
        found = [workspace.search.search(name).hits[0].item for name in ("lionheart", "mask of")]
        assert [item.id for item in found] == [LIONHEART, MASK]
        context = workspace.calculator.context(
            "warrior_dps_fury", phase=1, current_stats={Stat.HIT: 5}
        )
        result = workspace.calculator.compare(found, context)
        assert result.outcome == "winner" and result.winner_id == LIONHEART
        assert result.score_delta == pytest.approx(56.0)
        assert result.result(LIONHEART).item_provider == "bundled"
        assert result.result(LIONHEART).item_data_version.startswith("classic_era-vmangos-")

    def test_by_id_and_against_the_equipped_item(self, open_workspace: Opener) -> None:
        calculator = open_workspace().calculator
        context = calculator.context("warrior_dps_fury", current_stats={Stat.HIT: 7})
        result = calculator.compare_ids([LIONHEART], context, replacing_id=MASK)
        assert result.replaced is not None and result.replaced.item_id == MASK
        assert [u.item_id for u in result.upgrades] == [LIONHEART]
        assert result.upgrades[0].delta == pytest.approx(56.0)

    def test_unknown_items_are_reported(self, open_workspace: Opener) -> None:
        calculator = open_workspace().calculator
        context = calculator.context("warrior_dps_fury")
        with pytest.raises(NotFoundError, match="classic_era:1"):
            calculator.compare_ids(["classic_era:1"], context)

    def test_a_manual_item_against_a_found_one(self, open_workspace: Opener) -> None:
        workspace = open_workspace()
        form = ManualItemForm(
            name="Theorycrafted Helm",
            slot=ItemSlot.HEAD,
            armor_type=ArmorType.PLATE,
            stats={Stat.STRENGTH: 30, Stat.HIT: 1},
        )
        preview = workspace.entry.preview(form)
        assert preview.item is not None and preview.usable
        lionheart = workspace.search.get(LIONHEART)
        assert lionheart is not None
        context = workspace.calculator.context("warrior_dps_fury", current_stats={Stat.HIT: 5})
        result = workspace.calculator.compare([preview.item, lionheart], context)
        assert result.result(preview.item.id).score == pytest.approx(60 + 20)
        assert result.winner_id == LIONHEART  # 116 against 80

    def test_an_invalid_item_is_refused(self, open_workspace: Opener) -> None:
        workspace = open_workspace()
        lionheart = workspace.search.get(LIONHEART)
        assert lionheart is not None
        broken = Item.model_validate({**lionheart.model_dump(), "id": "custom:broken", "phase": 9})
        context = workspace.calculator.context("warrior_dps_fury")
        with pytest.raises(DataValidationError, match="cannot be scored"):
            workspace.calculator.compare([lionheart, broken], context)

    def test_a_failing_provider_does_not_stop_a_comparison(self, open_workspace: Opener) -> None:
        workspace = open_workspace(online=True, fail="connect")
        outcome = workspace.search.search("lionheart", online=True)
        assert outcome.online == "failed" and outcome.hits
        context = workspace.calculator.context("warrior_dps_fury", current_stats={Stat.HIT: 5})
        result = workspace.calculator.compare_ids([LIONHEART, MASK], context)
        assert result.winner_id == LIONHEART


class TestCommandLine:
    runner = CliRunner()

    def test_compare_prints_the_explanation(
        self, project: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("WOWGEAR_HOME", str(project))
        args = [
            "compare",
            "Lionheart Helm",
            "13404",
            "-p",
            "warrior_dps_fury",
            "--current",
            "hit=5",
        ]
        result = self.runner.invoke(app, args)
        assert result.exit_code == 0, result.output
        assert "Lionheart Helm is better for Fury (dual wield) by 56.0 AP" in result.output
        assert "Why: +36.0 from strength into attack power and +20.0 from crit." in result.output
        assert "Recommended under this profile and these assumptions" in result.output

    def test_compare_as_json(self, project: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("WOWGEAR_HOME", str(project))
        result = self.runner.invoke(
            app, ["compare", "12640", "13404", "-p", "warrior_dps_fury", "--json"]
        )
        assert result.exit_code == 0, result.output
        payload = json.loads(result.stdout)
        assert payload["winner_id"] == LIONHEART and payload["profile_id"] == "warrior_dps_fury"

    @pytest.mark.parametrize(
        ("args", "message"),
        [
            (["12640", "-p", "nobody"], "no build profile"),
            (["12640", "-p", "warrior_dps_fury", "--current", "speed=3"], "not a stat"),
            (["12640", "-p", "warrior_dps_fury", "--current", "hit"], "STAT=NUMBER"),
            (["no such item", "-p", "warrior_dps_fury"], "no item matches"),
        ],
    )
    def test_compare_explains_what_is_wrong(
        self, project: Path, monkeypatch: pytest.MonkeyPatch, args: list[str], message: str
    ) -> None:
        monkeypatch.setenv("WOWGEAR_HOME", str(project))
        result = self.runner.invoke(app, ["compare", *args])
        assert result.exit_code == 2
        assert message in result.output
