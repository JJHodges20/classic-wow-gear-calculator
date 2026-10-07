# Bundled item dataset

`classic_era_items.json.gz` is the curated Classic Era item dataset the app works from
offline: every equippable item of uncommon quality or better, normalized into the canonical
Item model. `classic_era_items.meta.json` records how it was built - the source snapshot and
its checksum, the build date, the curation rule, the phase heuristic and the counts.

## Where it comes from

The items are converted by `scripts/build_bundled_dataset.py` from the world database of
[VMaNGOS](https://github.com/vmangos/core), a community-maintained reproduction of the
patch 1.2 to 1.12 game, using its `db_latest` SQLite snapshot. Each item is taken at its
patch 1.12 version, the patch Classic Era is based on. The script is deterministic: the same
snapshot gives the same dataset.

## Terms and caveats

- VMaNGOS's code is licensed GPL-2.0; it publishes no separate license for the data, which is
  Blizzard Entertainment's game data. Using it in a personal, non-commercial tool is the
  reason it is bundled; anyone redistributing this repository should review that first.
  `docs/research/DATA_SOURCES.md` records why this source was chosen over the alternatives
  (Wowhead forbids automated access; Blizzard's API forbids keeping data longer than 30 days;
  Warcraft Logs has no item stats).
- The data reproduces patch 1.12. The current Classic Era client (1.15) may differ for a few
  items. Every item links to Wowhead, a human reference, for checking.
- Phases are a heuristic: raid and world-boss drops take the phase that content opened in;
  other items take the phase of the first patch they exist in.
- Procs, on-use effects and spell-specific bonuses are kept as text and reported as not
  scored; the calculator never invents a value for them.

## Rebuilding

Download `db-sqlite-<commit>.zip` from the
[db_latest release](https://github.com/vmangos/core/releases/tag/db_latest), unzip it under
`data/raw/vmangos/`, then run:

```powershell
.\.venv\Scripts\python.exe scripts\build_bundled_dataset.py data\raw\vmangos\sqlite-dump\mangos.sqlite
```
