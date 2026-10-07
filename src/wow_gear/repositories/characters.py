"""Saved characters: one row each in the local database, the whole character kept as JSON."""

from __future__ import annotations

from pydantic import ValidationError
from sqlalchemy import delete, select

from wow_gear.models.gear import SavedCharacter
from wow_gear.repositories.database import CharacterRow, Database, utc_now


class CharacterRepository:
    def __init__(self, database: Database) -> None:
        self._database = database
        self.problems: list[str] = []
        """Rows that could not be read on the last ``all()``, with the reason."""

    def all(self) -> list[SavedCharacter]:
        """Every saved character that can be read, by name."""
        with self._database.session() as session:
            rows = session.scalars(
                select(CharacterRow).order_by(CharacterRow.name, CharacterRow.id)
            )
            found = [(row.id, row.payload) for row in rows]
        characters, problems = [], []
        for character_id, payload in found:
            try:
                characters.append(SavedCharacter.model_validate_json(payload))
            except ValidationError as error:
                problems.append(f"saved character {character_id!r} cannot be read: {error}")
        self.problems = problems
        return characters

    def get(self, character_id: str) -> SavedCharacter | None:
        with self._database.session() as session:
            row = session.get(CharacterRow, character_id)
            payload = row.payload if row is not None else None
        return SavedCharacter.model_validate_json(payload) if payload is not None else None

    def save(self, character: SavedCharacter) -> SavedCharacter:
        """Store ``character`` with the next version and the time it was saved."""
        with self._database.session() as session:
            row = session.get(CharacterRow, character.id)
            version = row.version + 1 if row is not None else 1
            stored = character.model_copy(update={"version": version, "saved_at": utc_now()})
            assert stored.saved_at is not None
            session.merge(
                CharacterRow(
                    id=stored.id,
                    name=stored.name,
                    ruleset=stored.ruleset,
                    class_name=stored.class_name.value,
                    version=stored.version,
                    saved_at=stored.saved_at,
                    payload=stored.model_dump_json(),
                )
            )
            session.commit()
        return stored

    def delete(self, character_id: str) -> bool:
        with self._database.session() as session:
            result = session.execute(delete(CharacterRow).where(CharacterRow.id == character_id))
            session.commit()
        return bool(getattr(result, "rowcount", 0))
