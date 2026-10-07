# Research: Classic Era item data sources and their terms

Read 2026-10-07. Only documentation, terms and repository pages were read; no dataset was
downloaded for this research. Warcraft Logs and Archon pages sit behind a human check, so
their terms below are second-hand.

## Summary

| Source | Item stats | Terms | Bundling a curated set | On-demand lookup |
| --- | --- | --- | --- | --- |
| Blizzard Game Data API, `static-classic1x-{region}` | Yes (`preview_item`) | Developer API Terms: personal use allowed, data refreshed at least every 30 days, Blizzard credited, no monetization | No (30-day limit) | Yes, cached at most 30 days |
| Warcraft Logs API v2 | No: `GameItem` has only id, icon, name | Cache per response headers (second-hand) | No | No (names and icons only) |
| Wowhead | Pages only | Terms forbid robots, crawlers and data mining | No | No |
| VMaNGOS database snapshot | Yes (patch 1.2 to 1.12 rows) | Code GPL-2.0; the game data is Blizzard's, no separate data license | Best technical fit; legally a gray area | Local import only |
| CMaNGOS classic-db | Yes (1.12 only) | GPL v3, with a COPYRIGHT.md forbidding modification of the copyrighted material | Gray, worse than VMaNGOS | Local import only |
| wago.tools DB2 exports | Yes (client tables) | No terms published; robots.txt disallows all but the home page; client data under Blizzard's EULA | Gray | No |
| nexus-devs/wow-classic-items, wowsims/classic | Yes | MIT code, data scraped from Wowhead | No | - |

## Blizzard Game Data API

- Namespace for Classic Era: `static-classic1x-{region}` (`static-classic-{region}` is the
  progression realms). Blizzard staff, 2021-06-08: "Era realms are now using
  `classic1x-{region}` namespaces." ([forum](https://us.forums.blizzard.com/en/blizzard/t/wow-classic-era-realm-apis/16812))
- Endpoints: Item `/data/wow/item/{itemId}`, Item Search `/data/wow/search/item` (pages of at
  most 1,000), Item Media, Item Class. Item responses link `/data/wow/item-set/{id}`.
- `preview_item` carries `stats[]`, `spells[].description` (equip lines as text), `armor`,
  `weapon.damage`, `weapon.attack_speed` (milliseconds), `weapon.dps`, `requirements.level`,
  `set` with `effects[]`, `inventory_type`, `binding` (example responses in a
  [2026 gist](https://gist.github.com/branneman/684767197dc50b932e6f4a6ba38b3bf2), from the
  Anniversary namespace).
- Authentication: OAuth client credentials at `https://oauth.battle.net/token`; tokens last
  about a day. Limits: 36,000 requests an hour, 100 a second.
- [Developer API Terms of Use](https://www.blizzard.com/en-us/legal/a2989b50-5f16-43b1-abec-2ae17cc09dd6/blizzard-developer-api-terms-of-use):
  "You must implement a maximum 30-day TTL (time-to-live) policy for all Data obtained
  through our APIs"; "clearly and conspicuously identify Blizzard ... as the source of the
  Data"; no premium versions or monetization; keep the API key confidential (each user
  registers their own client).
- Coverage of Era items is not documented as complete; past forum reports show gaps. A test
  call with credentials is needed.

## Warcraft Logs API v2

`type GameItem { id: Int!  icon: String  name: String }` - no stats, slot, armor or damage
([schema](https://classic.warcraftlogs.com/v2-api-docs/warcraft/gameitem.doc.html)). It
cannot fill the canonical item. It stays in the roadmap for version 5 (log validation).

## Wowhead

[Fanbyte terms](https://corp.fanbyte.com/legal/terms) (May 14, 2025), section 8: no access
"using any engine, software, tool, agent, device or mechanism (including spiders, robots,
crawlers, data mining tools or the like)". Wowhead's robots.txt disallows ClaudeBot and
other named bots entirely. The app links to Wowhead item pages for a person to check; it
never fetches them.

## VMaNGOS

- [vmangos/core](https://github.com/vmangos/core): GPL-2.0. The README offers the "Latest
  MySQL 5.6 development database snapshot" under the release tag `db_latest`, including a
  SQLite conversion (`db-sqlite-<commit>.zip`, about 42 MB).
- `item_template` has a `patch` column (0 = patch 1.2 ... 10 = patch 1.12; the server loads the
  highest patch not above its own), stats, weapon damage and delay, armor, block, resistances,
  equip spells with triggers, `set_id`, `required_level`, `inventory_type`.
- `spell_template` has `description` and aura effect columns.
- No item-set table: only `set_id` refers to sets.
- It reproduces patches 1.2 to 1.12, not the 1.15 Era client.

## Openly licensed datasets

None found with documented non-Wowhead origins and an explicit license for the data:
nexus-devs/wow-classic-items says it was built "by scraping Wowhead and the official
Blizzard API"; wowsims/classic's database is generated from Wowhead tooltip endpoints; a
third (Gunnarguy/WoWCA) does not say where its data came from.
