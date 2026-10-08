# Data Sources

Where the calculator's item data comes from, under what terms, and how long it is kept. The
research behind these choices is in [research/DATA_SOURCES.md](research/DATA_SOURCES.md);
the decision is [0004](decisions/0004-item-providers.md). Game mechanics come from the
sources cited in `configs/rulesets/classic_era.yaml` (see [research/](research/)).

| Source | Role | Status | Kept |
| --- | --- | --- | --- |
| Bundled dataset (`data/bundled`) | Offline baseline: every equippable Classic Era item of uncommon quality or better | In use | Shipped with the code; reloaded when its version changes |
| Blizzard Battle.net Game Data API | Online lookup by name or id | In use when you add your own credentials | At most 30 days, then dropped (the bundled copy, if any, returns) |
| Your files (CSV or JSON) | Items you add: seasonal, missing or custom | In use | Until you delete them |
| Manual entry | One item at a time, typed or pasted from a tooltip | In use | Kept with your items when you choose "Keep in my items" |
| Warcraft Logs API v2 | Reserved for log validation (roadmap version 5) | Not used for items: its items have no stats | - |
| Wowhead | A human reference: the app links to item pages | Never fetched or scraped: its terms forbid automated access | - |

## Bundled dataset

Built by `scripts/build_bundled_dataset.py` from the world database of
[VMaNGOS](https://github.com/vmangos/core), a community-maintained reproduction of the patch
1.2 to 1.12 game. See [data/bundled/README.md](../data/bundled/README.md) for the curation
rule, the phase heuristic, the build cross-check (each equip effect read both from its aura
and from its tooltip text) and the terms. In short: VMaNGOS's code is GPL-2.0, the game data
is Blizzard's, and the dataset is bundled for a personal, non-commercial tool; review that
before redistributing the repository.

## Blizzard Game Data API

- Classic Era namespace `static-classic1x-{region}`; endpoints `/data/wow/item/{id}` and
  `/data/wow/search/item`.
- **Your own credentials.** Create a client at
  [develop.battle.net](https://develop.battle.net/access/clients) and put its id and secret
  in `.env` (`WOWGEAR_BLIZZARD_CLIENT_ID`, `WOWGEAR_BLIZZARD_CLIENT_SECRET`). They are read
  from the environment only, never written to the configuration or the database, and masked
  in the logs of both the app and the command line, tracebacks included. The region and locale are in `configs/providers.yaml`.
- **Terms** ([Blizzard Developer API Terms of Use](https://www.blizzard.com/en-us/legal/a2989b50-5f16-43b1-abec-2ae17cc09dd6/blizzard-developer-api-terms-of-use)):
  data is refreshed at least every 30 days, so looked-up items expire after at most 30 days
  and are dropped while the app runs, not only when it starts; a lookup never replaces an
  item you imported or kept yourself;
  Blizzard is shown as the source of every item it supplied; the app has no paid features.
- **Privacy:** the app runs on your computer and keeps everything in a local SQLite file
  (`data/user/wowgear.sqlite3`); it sends Blizzard only the item names and ids you search.
- **Unverified:** the response shape is taken from Blizzard's documentation and published
  examples; the tests use constructed responses (`data/fixtures/providers/blizzard`). The
  first real lookup should be checked against the item's tooltip.

Online search runs only when you ask for it; local search never waits on the network. A
failure (no credentials, offline, timeout, rate limit, an unexpected response) becomes a
notice beside the local results.

## Your files

CSV or JSON. A JSON file may hold canonical items as the app exports them, or simple
records; a CSV row is a simple record:

```
name,slot,armor_type,weapon_type,required_level,strength,stamina,hit,effects
My Helm,head,plate,,60,20,15,1,Equip: +81 Attack Power when fighting Undead.
```

Columns: `name`, `slot` and optionally `armor_type`, `weapon_type`, `relic_type`, `quality`,
`required_level`, `phase`, `min_damage`, `max_damage`, `speed`, `damage_school`, `custom`,
`set_name`, one column per stat (named as the stat: `strength`, `spell_hit`, `mp5`, ...) and
`effects` (tooltip lines separated by `|`). An unknown column rejects the row, so a typing
slip is caught. Run `wowgear items import <file>`.
