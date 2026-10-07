"""Saved characters: keep, check, analyse and change a whole set of gear, and move it in and
out of files - on a throwaway project with the fixture dataset and the shipped profiles.

Fury values by hand: 2 per Strength, 20 per 1% crit, 20 per 1% hit. Without a weapon skill
bonus the first 1% of hit is suppressed against a raid boss, so Lionheart Helm (18 Strength,
2% crit, 2% hit) is worth 36 + 40 + 20 = 96 and Mask of the Unforgiven (1% crit, 2% hit) 40.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import pytest
from sqlalchemy import update
from typer.testing import CliRunner

from wow_gear.cli import app
from wow_gear.core.errors import DataValidationError, NotFoundError
from wow_gear.models.enums import ClassName, EquipmentSlot, Race, Stat
from wow_gear.models.gear import GearSet, SavedCharacter
from wow_gear.repositories.database import CharacterRow
from wow_gear.services.characters import CharacterService
from wow_gear.services.workspace import Workspace

Opener = Callable[..., Workspace]
S = EquipmentSlot
FURY = "warrior_dps_fury"
LIONHEART, MASK = "classic_era:12640", "classic_era:13404"
THUNDERFURY, BRUTALITY = "classic_era:19019", "classic_era:18832"
BLACKHAND = "classic_era:13965"


def grom(workspace: Workspace, race: Race | None = None) -> SavedCharacter:
    return workspace.characters.new("Grom Hellscream", FURY, race=race)


def grom_with(service: CharacterService, *pieces: str) -> SavedCharacter:
    character = service.new("Grom Hellscream", FURY)
    slots = {LIONHEART: S.HEAD, MASK: S.HEAD, THUNDERFURY: S.MAIN_HAND, BLACKHAND: S.TRINKET_1}
    for piece in pieces:
        character = service.equip(character, slots[piece], piece)
    return character


class TestKeepingCharacters:
    def test_a_new_character_takes_the_profile_s_defaults(self, open_workspace: Opener) -> None:
        character = grom(open_workspace())
        assert character.id == "grom_hellscream"
        assert (character.class_name, character.level, character.phase) == (
            ClassName.WARRIOR,
            60,
            6,
        )
        assert character.gear.items == {}

    def test_saving_keeps_it_and_counts_versions(self, open_workspace: Opener) -> None:
        workspace = open_workspace()
        service = workspace.characters
        character = service.equip(grom(workspace), S.HEAD, LIONHEART)
        first = service.save(character)
        second = service.save(first)
        assert (first.version, second.version) == (1, 2)
        assert first.saved_at is not None
        assert [c.id for c in service.all()] == ["grom_hellscream"]
        reopened = open_workspace().characters.get("grom_hellscream")
        assert reopened == second

    def test_deleting_removes_it(self, open_workspace: Opener) -> None:
        service = open_workspace().characters
        service.save(grom_with(service, LIONHEART))
        service.delete("grom_hellscream")
        with pytest.raises(NotFoundError):
            service.get("grom_hellscream")
        with pytest.raises(NotFoundError):
            service.delete("grom_hellscream")

    def test_a_second_character_of_the_same_name_gets_its_own_id(
        self, open_workspace: Opener
    ) -> None:
        workspace = open_workspace()
        workspace.characters.save(grom(workspace))
        assert grom(workspace).id == "grom_hellscream_2"

    def test_a_race_the_class_cannot_be_is_refused(self, open_workspace: Opener) -> None:
        workspace = open_workspace()
        with pytest.raises(DataValidationError, match="cannot be a Paladin"):
            workspace.characters.new("Thrall", "paladin_dps_ret", race=Race.ORC)

    def test_a_profile_of_another_class_moves_the_character(self, open_workspace: Opener) -> None:
        workspace = open_workspace()
        human = grom(workspace, race=Race.HUMAN)
        paladin = workspace.characters.update(human, profile_id="paladin_dps_ret", name="Uther")
        assert (paladin.class_name, paladin.name, paladin.race) == (
            ClassName.PALADIN,
            "Uther",
            Race.HUMAN,
        )
        with pytest.raises(DataValidationError, match="cannot be a Druid"):
            workspace.characters.update(human, profile_id="druid_tank_bear")

    def test_the_schema_records_the_characters_table(self, open_workspace: Opener) -> None:
        assert open_workspace().database.get_meta("schema_version") == "2"

    def test_a_saved_character_that_cannot_be_read_is_reported(
        self, open_workspace: Opener
    ) -> None:
        workspace = open_workspace()
        service = workspace.characters
        service.save(grom(workspace))
        with workspace.database.session() as session:
            session.execute(update(CharacterRow).values(payload='{"id": "broken"}'))
            session.commit()
        assert service.all() == []
        assert "grom_hellscream" in service.problems[0]


class TestGear:
    def test_equipping_checks_the_slot(self, open_workspace: Opener) -> None:
        service = open_workspace().characters
        with pytest.raises(DataValidationError, match="cannot be worn in the finger 1 slot"):
            service.equip(grom_with(service), S.FINGER_1, LIONHEART)

    def test_a_unique_weapon_is_worn_once(self, open_workspace: Opener) -> None:
        service = open_workspace().characters
        character = grom_with(service, THUNDERFURY)
        with pytest.raises(DataValidationError, match="unique"):
            service.equip(character, S.OFF_HAND, THUNDERFURY)
        both = service.equip(character, S.OFF_HAND, BRUTALITY)
        assert set(both.gear.items) == {S.MAIN_HAND, S.OFF_HAND}

    def test_emptying_a_slot(self, open_workspace: Opener) -> None:
        service = open_workspace().characters
        character = service.equip(grom_with(service, LIONHEART), S.HEAD, None)
        assert character.gear.items == {}

    def test_the_analysis_values_each_piece(self, open_workspace: Opener) -> None:
        service = open_workspace().characters
        analysis, loaded = service.analyse(grom_with(service, LIONHEART))
        assert analysis.score == pytest.approx(96.0)
        assert [(v.slot, v.score) for v in analysis.slots] == [(S.HEAD, pytest.approx(96.0))]
        assert set(loaded.items) == {S.HEAD}
        assert analysis.totals[Stat.STRENGTH] == 18.0

    def test_the_worn_weapon_and_race_set_the_cap(self, open_workspace: Opener) -> None:
        # A Human with a sword has 305 skill: nothing suppressed, the helm's 2% hit is 40.
        service = open_workspace().characters
        character = grom_with(service, LIONHEART, THUNDERFURY)
        human = service.update(character, race=Race.HUMAN)
        analysis, _ = service.analyse(human)
        assert analysis.slots[0].score == pytest.approx(116.0)
        assert analysis.caps[0].target == 6.0

    def test_a_replacement_against_the_whole_character(self, open_workspace: Opener) -> None:
        service = open_workspace().characters
        result = service.try_replacement(grom_with(service, LIONHEART), S.HEAD, MASK)
        assert result.delta == pytest.approx(40.0 - 96.0)
        assert result.removed == ("Lionheart Helm",)

    def test_an_item_missing_from_the_data_is_reported_not_fatal(
        self, open_workspace: Opener
    ) -> None:
        service = open_workspace().characters
        character = grom_with(service, BLACKHAND)
        gear = GearSet(items={**character.gear.items, S.HEAD: "classic_era:99999999"})
        missing = character.model_copy(update={"gear": gear})
        analysis, loaded = service.analyse(missing)
        assert loaded.missing == ("Head: item classic_era:99999999 is not in the item data",)
        assert analysis.score == pytest.approx(40.0)
        assert analysis.notes[-1].startswith("Not analysed - Head")

    def test_gear_totals_for_the_calculator(self, open_workspace: Opener) -> None:
        service = open_workspace().characters
        totals = service.gear_totals(grom_with(service, LIONHEART), [Stat.HIT, Stat.DEFENSE])
        assert totals == {Stat.HIT: 2.0, Stat.DEFENSE: 0.0}


class TestFiles:
    def test_a_character_file_imports_as_a_new_unsaved_character(
        self, open_workspace: Opener
    ) -> None:
        service = open_workspace().characters
        saved = service.save(grom_with(service, LIONHEART, BLACKHAND))
        imported = service.import_text(service.export_json(saved), ".json")
        assert imported.id == "grom_hellscream_2"
        assert (imported.version, imported.saved_at) == (1, None)
        assert imported.gear == saved.gear

    def test_a_gear_list_replaces_the_gear(self, open_workspace: Opener) -> None:
        service = open_workspace().characters
        source = grom_with(service, LIONHEART, BLACKHAND)
        analysis, _ = service.analyse(source)
        text = service.export_csv(source, analysis)
        target = service.import_text(text, ".csv", into=grom_with(service))
        assert target.gear.items == source.gear.items

    def test_a_gear_list_needs_a_character_and_known_items(self, open_workspace: Opener) -> None:
        service = open_workspace().characters
        text = "slot,item_id\nhead,99999999\n"
        with pytest.raises(DataValidationError, match="choose or create a character"):
            service.import_text(text, ".csv")
        with pytest.raises(DataValidationError, match="not in the item data"):
            service.import_text(text, ".csv", into=grom_with(service))

    def test_the_report_is_a_page(self, open_workspace: Opener) -> None:
        service = open_workspace().characters
        character = grom_with(service, LIONHEART)
        analysis, _ = service.analyse(character)
        html = service.export_html(character, analysis)
        assert html.startswith("<!doctype html>")
        assert "Grom Hellscream" in html


class TestCommandLine:
    runner = CliRunner()

    def test_listing_the_saved_characters(
        self, open_workspace: Opener, project: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("WOWGEAR_HOME", str(project))
        assert "No saved characters." in self.runner.invoke(app, ["gear"]).output
        service = open_workspace().characters
        service.save(grom_with(service, LIONHEART))
        result = self.runner.invoke(app, ["gear"])
        assert result.exit_code == 0, result.output
        assert "grom_hellscream" in result.output and "1 pieces" in result.output

    def test_analysing_a_character_and_trying_an_item(
        self,
        open_workspace: Opener,
        project: Path,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
    ) -> None:
        monkeypatch.setenv("WOWGEAR_HOME", str(project))
        service = open_workspace().characters
        service.save(grom_with(service, LIONHEART))
        report = tmp_path / "gear.html"
        args = ["gear", "grom_hellscream", "--try", "head=13404", "--output", str(report)]
        result = self.runner.invoke(app, args)
        assert result.exit_code == 0, result.output
        assert "This gear is worth 96.0 AP." in result.output
        assert (
            "Trying Mask of the Unforgiven in the head slot (replacing Lionheart Helm): -56.0 AP"
            in result.output
        )
        assert report.read_text(encoding="utf-8").startswith("<!doctype html>")

    def test_analysing_a_character_file(
        self,
        open_workspace: Opener,
        project: Path,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
    ) -> None:
        monkeypatch.setenv("WOWGEAR_HOME", str(project))
        service = open_workspace().characters
        source = tmp_path / "grom.json"
        source.write_text(service.export_json(grom_with(service, LIONHEART)), encoding="utf-8")
        result = self.runner.invoke(app, ["gear", str(source)])
        assert result.exit_code == 0, result.output
        assert "Lionheart Helm" in result.output

    @pytest.mark.parametrize(
        ("args", "message"),
        [
            (["nobody"], "no saved character 'nobody'"),
            (["grom_hellscream", "--try", "head"], "SLOT=ITEM"),
            (["grom_hellscream", "--try", "shirt=13404"], "not an equipment slot"),
            (["grom_hellscream", "--output", "gear.csv"], ".json or .html"),
        ],
    )
    def test_the_gear_command_explains_what_is_wrong(
        self,
        open_workspace: Opener,
        project: Path,
        monkeypatch: pytest.MonkeyPatch,
        args: list[str],
        message: str,
    ) -> None:
        monkeypatch.setenv("WOWGEAR_HOME", str(project))
        service = open_workspace().characters
        service.save(grom_with(service, LIONHEART))
        result = self.runner.invoke(app, ["gear", *args])
        assert result.exit_code == 2
        assert message in result.output
