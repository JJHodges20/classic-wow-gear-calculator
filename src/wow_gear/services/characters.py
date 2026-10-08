"""Saved characters and their gear (roadmap V1.5): keep named characters with a full gear
set, analyse the gear as a whole, and try a replacement against the whole character.

A character names its build profile, so every analysis is made under a stated profile and
context, exactly like a comparison. Gear is kept as item ids; an item that is no longer in
the item data is reported, and the rest of the gear is still analysed.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from pydantic import ValidationError

from wow_gear.comparison.gear import analyse_gear, check_gear, displaced, replacement
from wow_gear.core.errors import DataValidationError, NotFoundError
from wow_gear.data_sources.files import read_gear_text
from wow_gear.models.character import CharacterContext
from wow_gear.models.enums import ContentMode, EquipmentSlot, Race
from wow_gear.models.gear import GearAnalysis, GearSet, ReplacementResult, SavedCharacter
from wow_gear.models.item import Item
from wow_gear.models.labels import EQUIPMENT_SLOT_LABELS
from wow_gear.processing.gear_files import character_from_record, gear_from_rows, slot_from_text
from wow_gear.reporting.export import character_json, gear_csv, gear_html
from wow_gear.repositories.characters import CharacterRepository
from wow_gear.repositories.items import name_key
from wow_gear.services.calculator import CalculatorService


@dataclass(frozen=True)
class LoadedGear:
    """A character's gear as items, and what could not be loaded."""

    items: dict[EquipmentSlot, Item]
    missing: tuple[str, ...] = ()


def parse_slot(text: str) -> EquipmentSlot:
    """An equipment slot as a player writes it: "main_hand", "Main hand" or "finger-1"."""
    return slot_from_text(text)


def _slug(name: str) -> str:
    return name_key(name).replace(" ", "_") or "character"


class CharacterService:
    def __init__(self, repository: CharacterRepository, calculator: CalculatorService) -> None:
        self._repository = repository
        self._calculator = calculator

    # --- reading ------------------------------------------------------------------------

    def all(self) -> list[SavedCharacter]:
        return self._repository.all()

    @property
    def problems(self) -> list[str]:
        """Saved characters that could not be read, with the reason."""
        return self._repository.problems

    def get(self, character_id: str) -> SavedCharacter:
        character = self._repository.get(character_id)
        if character is None:
            raise NotFoundError(f"no saved character {character_id!r}")
        return character

    # --- building -----------------------------------------------------------------------

    def free_id(self, name: str, keep: str | None = None) -> str:
        taken = {character.id for character in self._repository.all()} - {keep}
        base = _slug(name)[:50].rstrip("_") or "character"
        candidate, number = base, 2
        while candidate in taken:
            candidate, number = f"{base}_{number}", number + 1
        return candidate

    def new(
        self,
        name: str,
        profile_id: str,
        *,
        race: Race | None = None,
        level: int | None = None,
        phase: int | None = None,
        content_mode: ContentMode | None = None,
    ) -> SavedCharacter:
        """A new, unsaved character; choices left out take the profile's defaults."""
        name = " ".join(name.split())
        context = self._calculator.context(
            profile_id, race=race, level=level, phase=phase, content_mode=content_mode
        )
        return self._character(
            {
                "id": self.free_id(name),
                "name": name,
                "ruleset": context.ruleset,
                "class_name": context.class_name,
                "race": context.race,
                "level": context.level,
                "phase": context.phase,
                "profile_id": profile_id,
                "content_mode": context.content_mode,
            }
        )

    def update(self, character: SavedCharacter, **changes: Any) -> SavedCharacter:
        """``character`` with ``changes`` (name, profile_id, race, level, phase, content_mode,
        notes), checked. A profile for another class moves the character to that class."""
        data = character.model_dump(mode="python")
        data.update(changes)
        if "name" in changes:
            data["name"] = " ".join(str(changes["name"]).split())
        profile = self._calculator.profile(data["profile_id"])
        data["class_name"], data["ruleset"] = profile.class_name, profile.ruleset
        updated = self._character(data)
        self.context(updated)
        return updated

    @staticmethod
    def _character(data: Mapping[str, Any]) -> SavedCharacter:
        try:
            return SavedCharacter.model_validate(data)
        except ValidationError as error:
            reasons = "; ".join(issue["msg"] for issue in error.errors())
            raise DataValidationError(f"the character is not valid: {reasons}") from error

    def context(self, character: SavedCharacter) -> CharacterContext:
        """The context the character's gear is analysed in (its weapon types come from the gear)."""
        profile = self._calculator.profile(character.profile_id)
        if profile.ruleset != character.ruleset:
            raise DataValidationError(
                f"{character.name} is for the {character.ruleset!r} ruleset; the "
                f"{profile.label} profile is for {profile.ruleset!r}"
            )
        if profile.class_name != character.class_name:
            raise DataValidationError(
                f"{character.name} is a {character.class_name}; the {profile.label} profile is "
                f"for a {profile.class_name}"
            )
        return self._calculator.context(
            character.profile_id,
            race=character.race,
            level=character.level,
            phase=character.phase,
            content_mode=character.content_mode,
        )

    # --- gear ---------------------------------------------------------------------------

    def load_gear(self, character: SavedCharacter) -> LoadedGear:
        items: dict[EquipmentSlot, Item] = {}
        missing = []
        for slot in EquipmentSlot:
            item_id = character.gear.items.get(slot)
            if item_id is None:
                continue
            try:
                items[slot] = self._calculator.item(item_id)
            except NotFoundError:
                missing.append(
                    f"{EQUIPMENT_SLOT_LABELS[slot]}: item {item_id} is not in the item data"
                )
        return LoadedGear(items=items, missing=tuple(missing))

    def equip(
        self, character: SavedCharacter, slot: EquipmentSlot, item_id: str | None
    ) -> SavedCharacter:
        """``character`` with ``item_id`` in ``slot``, or the slot emptied for None.

        A two-handed weapon empties the off hand; an off-hand item takes a two-handed weapon
        off. Raises ``DataValidationError`` when the item cannot be worn there.
        """
        ids = dict(character.gear.items)
        if item_id is None:
            ids.pop(slot, None)
        else:
            item = self._calculator.item(item_id)
            worn = self.load_gear(character).items
            for other in displaced(worn, slot, item):
                ids.pop(other, None)
            ids[slot] = item.id
            check_gear({**{s: worn[s] for s in ids if s in worn and s != slot}, slot: item})
        gear = GearSet(name=character.gear.name, items=dict(sorted(ids.items())))
        return character.model_copy(update={"gear": gear})

    # --- saving -------------------------------------------------------------------------

    def save(self, character: SavedCharacter) -> SavedCharacter:
        """Check and store ``character``; its version goes up with every save."""
        self.context(character)
        check_gear(self.load_gear(character).items)
        return self._repository.save(character)

    def delete(self, character_id: str) -> None:
        if not self._repository.delete(character_id):
            raise NotFoundError(f"no saved character {character_id!r}")

    # --- analysis -----------------------------------------------------------------------

    def _scoring(self, character: SavedCharacter) -> tuple[CharacterContext, LoadedGear]:
        context = self.context(character)
        gear = self.load_gear(character)
        ruleset = self._calculator.ruleset(context.ruleset)
        self._calculator.check_items(list(gear.items.values()), ruleset)
        return context, gear

    def analyse(self, character: SavedCharacter) -> tuple[GearAnalysis, LoadedGear]:
        """What the character's gear is worth under its profile, piece by piece."""
        context, gear = self._scoring(character)
        profile = self._calculator.profile(character.profile_id)
        analysis = analyse_gear(
            gear.items, context, profile, self._calculator.ruleset(profile.ruleset)
        )
        if gear.missing:
            notes = (*analysis.notes, *(f"Not analysed - {entry}." for entry in gear.missing))
            analysis = analysis.model_copy(update={"notes": notes})
        return analysis, gear

    def try_replacement(
        self, character: SavedCharacter, slot: EquipmentSlot, item_id: str
    ) -> ReplacementResult:
        """How putting ``item_id`` into ``slot`` changes the character's whole gear."""
        context, gear = self._scoring(character)
        candidate = self._calculator.item(item_id)
        profile = self._calculator.profile(character.profile_id)
        ruleset = self._calculator.ruleset(profile.ruleset)
        self._calculator.check_items([candidate], ruleset)
        return replacement(gear.items, slot, candidate, context, profile, ruleset)

    # --- files --------------------------------------------------------------------------

    def import_text(
        self, text: str, suffix: str, *, into: SavedCharacter | None = None
    ) -> SavedCharacter:
        """A character from an import file: a saved character (JSON), or a gear list (CSV)
        put on ``into``. Nothing is saved until ``save``."""
        data = read_gear_text(text, suffix)
        if isinstance(data, dict):
            imported = character_from_record(data)
            fresh = {"id": self.free_id(imported.name), "version": 1, "saved_at": None}
            character = imported.model_copy(update=fresh)
            self.context(character)
            return character
        if into is None:
            raise DataValidationError("choose or create a character to put a gear list on")
        gear = gear_from_rows(data, into.ruleset, into.gear.name)
        character = into.model_copy(update={"gear": gear})
        loaded = self.load_gear(character)
        if loaded.missing:
            raise DataValidationError("; ".join(loaded.missing))
        check_gear(loaded.items)
        return character

    def export_json(self, character: SavedCharacter) -> str:
        return character_json(character)

    def export_csv(self, character: SavedCharacter, analysis: GearAnalysis | None) -> str:
        return gear_csv(character, analysis)

    def export_html(
        self,
        character: SavedCharacter,
        analysis: GearAnalysis,
        tried: ReplacementResult | None = None,
    ) -> str:
        ruleset = self._calculator.ruleset(character.ruleset)
        return gear_html(character, analysis, ruleset, tried)
