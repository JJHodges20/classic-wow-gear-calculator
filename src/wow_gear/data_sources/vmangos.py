"""Reading item data from a VMaNGOS database snapshot (SQLite conversion).

VMaNGOS (https://github.com/vmangos/core, GPL-2.0) is a community-maintained reproduction of
the patch 1.2 to 1.12 game. Its ``db_latest`` release ships the world database as SQLite.
The lab uses it to build the bundled curated dataset; this reader only fetches rows - the
normalizer in ``wow_gear.processing.vmangos`` turns them into canonical items.

Rows are returned as plain dictionaries, keyed by VMaNGOS column names.
"""

from __future__ import annotations

import sqlite3
from collections import defaultdict
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from wow_gear.core.errors import ProviderUnavailable

Row = dict[str, Any]

EQUIPPABLE_INVENTORY_TYPES = (
    1,
    2,
    3,
    5,
    6,
    7,
    8,
    9,
    10,
    11,
    12,
    13,
    14,
    15,
    16,
    17,
    20,
    21,
    22,
    23,
    25,
    26,
    28,
)
"""Inventory types worn in an equipment slot (no shirts, tabards, bags, ammo or quivers)."""

MAX_PATCH = 10
"""Patch index of 1.12, the patch Classic Era is based on (0 is 1.2)."""


@dataclass(frozen=True)
class LootSource:
    """Where an item drops: a creature or object, the map it is spawned on, the patch range."""

    source_kind: str
    source_entry: int
    map_id: int
    patch_min: int
    patch_max: int


class VmangosDatabase:
    """A read-only connection to a VMaNGOS ``mangos.sqlite`` file."""

    def __init__(self, path: Path) -> None:
        if not path.is_file():
            raise ProviderUnavailable(f"no VMaNGOS database at {path}")
        self.path = path
        self._db = sqlite3.connect(f"file:{path.as_posix()}?mode=ro", uri=True)
        self._db.row_factory = sqlite3.Row
        self._spells: dict[int, Row] | None = None

    def close(self) -> None:
        self._db.close()

    def __enter__(self) -> VmangosDatabase:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    def _rows(self, sql: str, params: tuple[Any, ...] = ()) -> list[Row]:
        return [dict(row) for row in self._db.execute(sql, params)]

    def items(self, max_patch: int = MAX_PATCH) -> Iterator[Row]:
        """Each equippable item at its latest version not after ``max_patch``.

        Each row also carries ``first_patch``: the earliest patch the item exists in.
        """
        placeholders = ",".join("?" for _ in EQUIPPABLE_INVENTORY_TYPES)
        sql = f"""
            select t.*, f.first_patch
            from item_template t
            join (
                select entry, max(patch) as patch, min(patch) as first_patch
                from item_template
                where patch <= ? and inventory_type in ({placeholders})
                group by entry
            ) f on f.entry = t.entry and f.patch = t.patch
            order by t.entry
        """
        yield from self._rows(sql, (max_patch, *EQUIPPABLE_INVENTORY_TYPES))

    def spells(self) -> dict[int, Row]:
        """Every spell at its latest build, by id (loaded once)."""
        if self._spells is None:
            rows = self._rows(
                """
                select s.* from spell_template s
                join (select entry, max(build) as build from spell_template group by entry) b
                  on b.entry = s.entry and b.build = s.build
                """
            )
            self._spells = {row["entry"]: row for row in rows}
        return self._spells

    def loot_sources(self) -> dict[int, list[LootSource]]:
        """Where each item drops, through creature, object and reference loot tables.

        Reference tables are followed one level deep, as VMaNGOS uses them for boss loot.
        """
        references: dict[int, list[Row]] = defaultdict(list)
        for row in self._rows(
            "select entry, item, mincountOrRef, patch_min, patch_max from reference_loot_template"
        ):
            references[row["entry"]].append(row)

        creature_maps: dict[int, set[int]] = defaultdict(set)
        for row in self._rows("select id, map from creature"):
            creature_maps[row["id"]].add(row["map"])
        object_maps: dict[int, set[int]] = defaultdict(set)
        for row in self._rows("select id, map from gameobject"):
            object_maps[row["id"]].add(row["map"])

        creature_loot: dict[int, list[int]] = defaultdict(list)
        for row in self._rows("select entry, loot_id from creature_template where loot_id > 0"):
            creature_loot[row["loot_id"]].append(row["entry"])
        object_loot: dict[int, list[int]] = defaultdict(list)
        for row in self._rows(
            "select entry, data1 from gameobject_template where type = 3 and data1 > 0"
        ):
            object_loot[row["data1"]].append(row["entry"])

        sources: dict[int, list[LootSource]] = defaultdict(list)

        def add(item: int, kind: str, entry: int, maps: set[int], low: int, high: int) -> None:
            for map_id in maps:
                sources[item].append(LootSource(kind, entry, map_id, low, high))

        for table, owners, spawns, kind in (
            ("creature_loot_template", creature_loot, creature_maps, "creature"),
            ("gameobject_loot_template", object_loot, object_maps, "object"),
        ):
            for row in self._rows(
                f"select entry, item, mincountOrRef, patch_min, patch_max from {table}"
            ):
                for owner in owners.get(row["entry"], []):
                    maps = spawns.get(owner, set())
                    if not maps:
                        continue
                    if row["mincountOrRef"] < 0:
                        for ref in references.get(-row["mincountOrRef"], []):
                            if ref["mincountOrRef"] > 0:
                                add(
                                    ref["item"],
                                    kind,
                                    owner,
                                    maps,
                                    max(row["patch_min"], ref["patch_min"]),
                                    min(row["patch_max"], ref["patch_max"]),
                                )
                    else:
                        add(row["item"], kind, owner, maps, row["patch_min"], row["patch_max"])
        return dict(sources)

    def snapshot_label(self) -> str:
        """The snapshot's name, from its folder or file (for provenance)."""
        return (
            self.path.parent.parent.name
            if self.path.parent.name == "sqlite-dump"
            else self.path.stem
        )
