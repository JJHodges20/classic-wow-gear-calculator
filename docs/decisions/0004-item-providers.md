# 0004 - Item providers: bundled VMaNGOS data, Blizzard for lookups, Wowhead as a link

Date: 2026-10-07. Status: accepted.

## Context

The roadmap's provider order is a bundled curated dataset, then the Warcraft Logs API, then
the Blizzard API, then manual import, with Wowhead as a human reference only. Version 1 needs
one lookup provider and a local cache, and must keep working when a provider fails. The
research (docs/research/DATA_SOURCES.md) found that:

- Warcraft Logs' game-data items carry only an id, a name and an icon;
- Blizzard's Game Data API has full Classic Era items, but its terms allow keeping data for
  at most 30 days and require each user's own credentials;
- Wowhead's terms forbid automated access;
- no openly licensed Classic Era item dataset with documented, non-Wowhead origins exists;
- the VMaNGOS world database has complete patch 1.12 items, under a GPL-2.0 project, with the
  game data itself being Blizzard's.

## Decision

1. **The bundled dataset is built from a VMaNGOS snapshot** by a committed, deterministic
   script, and shipped with the code: every equippable item of uncommon quality or better,
   at its 1.12 version, phases by a documented heuristic. Each equip effect is read from its
   aura, and the build cross-checks that reading against the effect's tooltip text.
2. **Blizzard's API is the first lookup provider.** It runs only on request, with the user's
   own credentials, and its items are cached for at most 30 days, after which the bundled
   copy (if any) returns.
3. **Warcraft Logs is not an item provider.** It keeps its place in the configuration for
   log validation in version 5.
4. **Wowhead is linked, never fetched.**
5. **File import is a provider too**: CSV or JSON records go through the manual form, so an
   imported item is built exactly like a typed one.
6. **Everything is stored as canonical items** in one SQLite repository, by origin (bundled,
   cache, user); search treats them alike.

## Consequences

- The app works offline with every Classic item; online lookup adds the current client's
  data when the player sets it up.
- The bundled data reproduces patch 1.12, not the 1.15 client; differences surface when a
  player looks the item up online.
- Redistributing the repository with the bundled dataset needs a look at the terms first;
  the dataset's README says so.
