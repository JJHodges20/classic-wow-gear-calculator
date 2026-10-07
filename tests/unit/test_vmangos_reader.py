"""The VMaNGOS reader's loot sources: patch 1.12 rows only, and summoned raid bosses placed.

A tiny snapshot is built in a temporary SQLite file with the shape of the real tables.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from wow_gear.data_sources.vmangos import SUMMONED_RAID_BOSSES, VmangosDatabase
from wow_gear.processing.vmangos import source_info

GARR, VAELASTRASZ, NEFARIAN, THUNDERAAN = 12057, 13020, 11583, 14435
NETHERWIND_BELT, NETHERWIND_ROBES, CRYSTAL = 16818, 16916, 20465
MOLTEN_CORE, BLACKWING_LAIR = 409, 469

SCHEMA = """
create table creature_template (entry integer, name text, loot_id integer, `rank` integer);
create table creature (id integer, map integer);
create table gameobject_template (entry integer, name text, type integer, data1 integer);
create table gameobject (id integer, map integer);
create table creature_loot_template
    (entry integer, item integer, mincountOrRef integer, patch_min integer, patch_max integer);
create table gameobject_loot_template
    (entry integer, item integer, mincountOrRef integer, patch_min integer, patch_max integer);
create table reference_loot_template
    (entry integer, item integer, mincountOrRef integer, patch_min integer, patch_max integer);
"""


@pytest.fixture
def snapshot(tmp_path: Path) -> Path:
    path = tmp_path / "mangos.sqlite"
    db = sqlite3.connect(path)
    db.executescript(SCHEMA)
    db.executemany(
        "insert into creature_template values (?, ?, ?, ?)",
        [
            (GARR, "Garr", GARR, 3),
            (VAELASTRASZ, "Vaelastrasz the Corrupt", VAELASTRASZ, 3),
            (NEFARIAN, "Nefarian", NEFARIAN, 3),
            (THUNDERAAN, "Prince Thunderaan", THUNDERAAN, 3),
        ],
    )
    db.executemany(
        "insert into creature values (?, ?)", [(GARR, MOLTEN_CORE), (VAELASTRASZ, BLACKWING_LAIR)]
    )
    db.executemany(
        "insert into creature_loot_template values (?, ?, ?, ?, ?)",
        [
            (GARR, 30574, -30574, 0, 10),
            (VAELASTRASZ, 30372, -30372, 0, 10),
            (NEFARIAN, 30486, -30486, 0, 10),
            (THUNDERAAN, CRYSTAL, 1, 0, 10),
        ],
    )
    db.executemany(
        "insert into reference_loot_template values (?, ?, ?, ?, ?)",
        [
            (30574, NETHERWIND_BELT, 1, 0, 1),  # Molten Core, patches 1.2 and 1.3 only
            (30372, NETHERWIND_BELT, 1, 4, 10),  # Blackwing Lair from 1.6
            (30486, NETHERWIND_ROBES, 1, 0, 10),
        ],
    )
    db.commit()
    db.close()
    return path


def test_loot_rows_that_end_before_the_patch_are_left_out(snapshot: Path) -> None:
    with VmangosDatabase(snapshot) as db:
        at_112 = db.loot_sources()
        at_12 = db.loot_sources(patch=0)
    assert {source.map_id for source in at_112[NETHERWIND_BELT]} == {BLACKWING_LAIR}
    assert {source.map_id for source in at_12[NETHERWIND_BELT]} == {MOLTEN_CORE}
    assert source_info(at_112[NETHERWIND_BELT]).raid_or_world_boss_phase == 3


def test_a_summoned_raid_boss_is_placed_in_its_raid(snapshot: Path) -> None:
    assert SUMMONED_RAID_BOSSES[NEFARIAN] == BLACKWING_LAIR
    with VmangosDatabase(snapshot) as db:
        loot = db.loot_sources()
    sources = loot[NETHERWIND_ROBES]
    assert [(source.source_entry, source.map_id) for source in sources] == [
        (NEFARIAN, BLACKWING_LAIR)
    ]
    assert source_info(sources).raid_or_world_boss_phase == 3


def test_an_unplaced_boss_is_reported_not_guessed(snapshot: Path) -> None:
    with VmangosDatabase(snapshot) as db:
        loot = db.loot_sources()
        unplaced = db.unplaced_bosses()
    assert CRYSTAL not in loot
    assert [row["entry"] for row in unplaced] == [THUNDERAAN]
