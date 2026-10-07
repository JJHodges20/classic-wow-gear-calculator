"""Reading gear from import files: a saved character as JSON, a gear list as CSV."""

from __future__ import annotations

import json

import pytest

from wow_gear.core import DataValidationError
from wow_gear.data_sources.files import read_gear_text
from wow_gear.models.enums import EquipmentSlot
from wow_gear.models.gear import GearSet, SavedCharacter
from wow_gear.processing.gear_files import (
    character_from_record,
    gear_from_rows,
    item_reference,
    slot_from_text,
)

CHARACTER = {
    "id": "grom",
    "name": "Grom",
    "ruleset": "classic_era",
    "class_name": "warrior",
    "level": 60,
    "phase": 3,
    "profile_id": "warrior_dps_fury",
    "gear": {"name": "Raid", "items": {"head": "classic_era:12640"}},
}


class TestReadingFiles:
    def test_a_json_character_is_one_object(self) -> None:
        assert read_gear_text(json.dumps(CHARACTER), ".json") == CHARACTER
        with pytest.raises(DataValidationError, match="one saved character"):
            read_gear_text("[1, 2]", ".json")
        with pytest.raises(DataValidationError, match="not valid JSON"):
            read_gear_text("{", ".json")

    def test_a_csv_gear_list_keeps_its_rows_with_lowercase_columns(self) -> None:
        text = "\ufeffSlot,Item_ID,item_name\nhead,12640,Lionheart Helm\n,,\nneck,,\n"
        rows = read_gear_text(text, ".csv")
        assert rows == [
            {"slot": "head", "item_id": "12640", "item_name": "Lionheart Helm"},
            {"slot": "neck", "item_id": "", "item_name": ""},
        ]

    def test_other_files_are_refused(self) -> None:
        with pytest.raises(DataValidationError, match=r"\.json or \.csv"):
            read_gear_text("", ".txt")


class TestCharacters:
    def test_a_saved_character_is_read_back(self) -> None:
        character = character_from_record(CHARACTER)
        assert isinstance(character, SavedCharacter)
        assert character.gear.items == {EquipmentSlot.HEAD: "classic_era:12640"}

    def test_a_record_that_is_not_a_character_says_why(self) -> None:
        with pytest.raises(DataValidationError, match="level"):
            character_from_record({**CHARACTER, "level": 0})
        with pytest.raises(DataValidationError, match="not a saved character"):
            character_from_record({"hello": "world"})


class TestGearLists:
    def test_slots_are_read_as_written_or_as_shown(self) -> None:
        assert slot_from_text("finger_1") == EquipmentSlot.FINGER_1
        assert slot_from_text("Finger 1") == EquipmentSlot.FINGER_1
        assert slot_from_text(" main-hand ") == EquipmentSlot.MAIN_HAND
        assert slot_from_text("Ranged or relic") == EquipmentSlot.RANGED
        with pytest.raises(DataValidationError, match="not an equipment slot"):
            slot_from_text("shirt")

    def test_a_game_number_becomes_the_app_s_item_id(self) -> None:
        assert item_reference("12640", "classic_era") == "classic_era:12640"
        assert item_reference("custom:my-ring-1a2b", "classic_era") == "custom:my-ring-1a2b"
        with pytest.raises(DataValidationError, match="not an item id"):
            item_reference("Lionheart Helm", "classic_era")

    def test_a_gear_list_becomes_a_gear_set(self) -> None:
        rows = [
            {"slot": "head", "id": "12640"},
            {"slot": "Finger 2", "id": "classic_era:13098"},
            {"slot": "neck", "id": ""},
        ]
        gear = gear_from_rows(rows, "classic_era", "Raid")
        assert gear == GearSet(
            name="Raid",
            items={
                EquipmentSlot.HEAD: "classic_era:12640",
                EquipmentSlot.FINGER_2: "classic_era:13098",
            },
        )

    def test_every_bad_row_is_reported_with_its_row_number(self) -> None:
        rows = [
            {"slot": "head", "item_id": "12640"},
            {"slot": "head", "item_id": "12641"},
            {"slot": "shirt", "item_id": "1"},
            {"slot": "neck", "item_id": "not an id"},
        ]
        with pytest.raises(DataValidationError) as error:
            gear_from_rows(rows, "classic_era", "Raid")
        message = str(error.value)
        assert "row 3: the Head slot is listed twice" in message
        assert "row 4: 'shirt' is not an equipment slot" in message
        assert "row 5: 'not an id' is not an item id" in message

    def test_a_list_without_the_columns_or_rows_is_refused(self) -> None:
        with pytest.raises(DataValidationError, match="slot column and an item_id column"):
            gear_from_rows([{"slot": "head", "name": "Helm"}], "classic_era", "Raid")
        with pytest.raises(DataValidationError, match="no rows"):
            gear_from_rows([], "classic_era", "Raid")
