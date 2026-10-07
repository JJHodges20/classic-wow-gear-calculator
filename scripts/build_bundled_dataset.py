"""Build the bundled curated Classic Era item dataset from a VMaNGOS database snapshot.

Usage (from the project root):

    .venv\\Scripts\\python.exe scripts\\build_bundled_dataset.py data\\raw\\vmangos\\sqlite-dump\\mangos.sqlite

Downloads nothing: fetch the SQLite snapshot yourself from
https://github.com/vmangos/core/releases/tag/db_latest (``db-sqlite-<commit>.zip``) and unzip
it under ``data/raw/vmangos/``. The script writes ``data/bundled/classic_era_items.json.gz``
and a metadata file beside it, and prints what it kept, dropped and could not score.

Curation: equippable items of uncommon quality or better, at their patch 1.12 version,
without the developer placeholders VMaNGOS keeps (names marked as tests, deprecated or
monster weapons). Every item goes through the canonical model's validation.
"""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import re
import sys
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path

from wow_gear.data_sources.vmangos import VmangosDatabase
from wow_gear.processing.tooltip import parse_line
from wow_gear.processing.vmangos import (
    map_spell,
    normalize_item,
    render_description,
    source_info,
    vmangos_provenance,
)

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "data" / "bundled" / "classic_era_items.json.gz"
METADATA = ROOT / "data" / "bundled" / "classic_era_items.meta.json"
MIN_QUALITY = 2  # uncommon
PLACEHOLDER = re.compile(
    r"(^monster - |^zz|\[ph\]|\bdeprecated\b|\btest\b|^old |\(old\)|\bunused\b|^qa |\bdnd\b|^npc "
    # Blizzard's stat-budget test items, such as "90 Epic Frost Belt" and "63 Green Agility Ring".
    r"|^\d+ (?:green|blue|rare|epic) )",
    re.IGNORECASE,
)


def cross_check(spells: dict[int, dict[str, object]], spell_ids: set[int]) -> dict[str, object]:
    """Read every mapped equip spell twice - by aura and by its tooltip text - and compare."""
    agree, differ, text_only_unknown = 0, [], 0
    for spell_id in sorted(spell_ids):
        spell = spells.get(spell_id)
        mapped = map_spell(spell) if spell else None
        if not mapped:
            continue
        by_aura = sorted((stat.value, value) for stat, value, _ in mapped)
        parsed = parse_line(render_description(spell, spells))  # type: ignore[arg-type]
        if not parsed.recognized:
            text_only_unknown += 1
            continue
        by_text = sorted((line.stat.value, line.value) for line in parsed.stats)
        if by_aura == by_text:
            agree += 1
        else:
            differ.append({"spell": spell_id, "aura": by_aura, "text": by_text})
    return {
        "agree": agree,
        "differ": len(differ),
        "text_not_recognized": text_only_unknown,
        "differences": differ[:20],
    }


def build(database: Path, snapshot: str, archive_sha256: str | None) -> dict[str, object]:
    built_at = datetime.now(UTC).replace(microsecond=0)
    provenance = vmangos_provenance(snapshot, built_at)
    items = []
    dropped: Counter[str] = Counter()
    equip_spells: set[int] = set()
    with VmangosDatabase(database) as db:
        spells = db.spells()
        loot = db.loot_sources()
        unplaced = [f"{row['name']} ({row['entry']})" for row in db.unplaced_bosses()]
        for row in db.items():
            for index in range(1, 6):
                if row.get(f"spelltrigger_{index}") == 1 and row.get(f"spellid_{index}"):
                    equip_spells.add(int(row[f"spellid_{index}"]))
            name = str(row["name"])
            if row["quality"] < MIN_QUALITY:
                dropped["below uncommon quality"] += 1
                continue
            if row["quality"] > 5:
                dropped["artifact or developer quality"] += 1
                continue
            if PLACEHOLDER.search(name):
                dropped["placeholder or developer item"] += 1
                continue
            item = normalize_item(
                row,
                spells,
                source=source_info(loot.get(row["entry"], [])),
                provenance=provenance,
            )
            items.append(item)

    unscored = Counter(
        effect.description for item in items for effect in item.equip_effects if effect.stat is None
    )
    by_slot = Counter(item.slot.value for item in items)
    by_phase = Counter(str(item.phase) for item in items)
    records = [item.model_dump(mode="json") for item in items]
    digest = hashlib.sha256(
        json.dumps(records, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()[:8]
    payload = {
        "dataset": "classic_era_items",
        # The digest changes whenever the items do, so a workspace reloads a rebuilt dataset.
        "version": f"{built_at:%Y.%m.%d}-{snapshot}-{digest}",
        "ruleset": "classic_era",
        "items": records,
    }
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    with gzip.open(OUTPUT, "wt", encoding="utf-8", compresslevel=9) as handle:
        json.dump(payload, handle, sort_keys=True, separators=(",", ":"))
    metadata = {
        "dataset": payload["dataset"],
        "version": payload["version"],
        "built_at": built_at.isoformat(),
        "source": provenance.source,
        "source_url": provenance.source_url,
        "snapshot": snapshot,
        "snapshot_archive_sha256": archive_sha256,
        "license": provenance.license,
        "curation": (
            "Equippable items of uncommon quality or better at their patch 1.12 version, "
            "without developer placeholders."
        ),
        "phase_heuristic": (
            "Raid and world-boss drops (patch 1.12 loot tables) take the phase that content "
            "opened in; other items take the phase of the first patch they exist in."
        ),
        "bosses_without_a_spawn": unplaced,
        "counts": {
            "items": len(items),
            "dropped": dict(dropped),
            "by_slot": dict(sorted(by_slot.items())),
            "by_phase": dict(sorted(by_phase.items())),
            "items_with_unscored_effects": sum(
                1 for item in items if any(e.stat is None for e in item.equip_effects)
            ),
        },
    }
    check = cross_check(spells, equip_spells)
    metadata["cross_check"] = {
        key: check[key] for key in ("agree", "differ", "text_not_recognized")
    }
    METADATA.write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")
    metadata["most_common_unscored"] = unscored.most_common(15)
    metadata["cross_check_differences"] = check["differences"]
    return metadata


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[union-attr]
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("database", type=Path, help="path to VMaNGOS mangos.sqlite")
    parser.add_argument("--snapshot", help="snapshot name (default: from the archive name)")
    args = parser.parse_args()
    database: Path = args.database
    archive = (
        next(database.parents[1].glob("db-sqlite-*.zip"), None)
        if len(database.parents) > 1
        else None
    )
    snapshot = args.snapshot or (
        archive.stem.replace("db-sqlite-", "db-") if archive else "unknown"
    )
    digest = hashlib.sha256(archive.read_bytes()).hexdigest() if archive else None
    metadata = build(database, snapshot, digest)
    print(json.dumps(metadata, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
