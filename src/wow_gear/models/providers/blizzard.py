"""The parts of Blizzard's Game Data API item responses the calculator reads.

Shapes follow Blizzard's documentation and published example responses (docs/research/
DATA_SOURCES.md). Unknown fields are ignored: Blizzard adds fields over time, and a missing
optional field must not break a lookup.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class _Lenient(BaseModel):
    model_config = ConfigDict(extra="ignore", frozen=True)


class TypedName(_Lenient):
    type: str | None = None
    name: str | None = None


class IdName(_Lenient):
    id: int | None = None
    name: str | None = None


class Display(_Lenient):
    display_string: str | None = None


class ValueDisplay(_Lenient):
    value: float | None = None
    display_string: str | None = None
    display: Display | None = None

    @property
    def text(self) -> str | None:
        if self.display_string:
            return self.display_string
        return self.display.display_string if self.display else None


class StatEntry(_Lenient):
    type: TypedName
    value: float
    display: Display | None = None
    is_negated: bool = False


class SpellRef(_Lenient):
    id: int | None = None
    name: str | None = None


class SpellEntry(_Lenient):
    spell: SpellRef | None = None
    description: str | None = None


class Damage(_Lenient):
    min_value: float | None = None
    max_value: float | None = None
    display_string: str | None = None
    damage_class: TypedName | None = None


class Weapon(_Lenient):
    damage: Damage | None = None
    attack_speed: ValueDisplay | None = None
    dps: ValueDisplay | None = None


class Links(_Lenient):
    links: list[IdName] = Field(default_factory=list)
    display_string: str | None = None


class Requirements(_Lenient):
    level: ValueDisplay | None = None
    playable_classes: Links | None = None
    playable_races: Links | None = None


class ItemSetInfo(_Lenient):
    item_set: IdName | None = None
    display_string: str | None = None


class PreviewItem(_Lenient):
    name: str | None = None
    quality: TypedName | None = None
    item_class: IdName | None = None
    item_subclass: IdName | None = None
    inventory_type: TypedName | None = None
    binding: TypedName | None = None
    unique_equipped: str | None = None
    weapon: Weapon | None = None
    armor: ValueDisplay | None = None
    shield_block: ValueDisplay | None = None
    stats: list[StatEntry] = Field(default_factory=list)
    spells: list[SpellEntry] = Field(default_factory=list)
    requirements: Requirements | None = None
    set: ItemSetInfo | None = None
    level: ValueDisplay | None = None


class BlizzardItem(_Lenient):
    """``GET /data/wow/item/{id}``."""

    id: int
    name: str
    quality: TypedName | None = None
    level: int | None = None
    required_level: int | None = None
    item_class: IdName | None = None
    item_subclass: IdName | None = None
    inventory_type: TypedName | None = None
    is_equippable: bool | None = None
    preview_item: PreviewItem | None = None


class SearchItemData(_Lenient):
    id: int
    name: dict[str, str] = Field(default_factory=dict)
    level: int | None = None
    required_level: int | None = None
    inventory_type: TypedName | None = None


class SearchResult(_Lenient):
    data: SearchItemData


class BlizzardSearchPage(_Lenient):
    """``GET /data/wow/search/item``."""

    page: int = 1
    pageSize: int = 0
    pageCount: int = 0
    results: list[SearchResult] = Field(default_factory=list)
