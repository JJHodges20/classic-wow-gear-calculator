# 0008 - Saved characters and whole gear sets

Date: 2026-10-07. Status: accepted.

## Context

Version 1.5 of the roadmap asks to "save named character/build profiles locally", "enter or
import a full current gear set", "calculate aggregate stats and show how a replacement
changes the whole character, not just one slot", "identify capped or wasted stats and
under-served priorities" and "export comparison results as JSON/CSV and a shareable report".
The Gear Set page is to "assemble current gear and see aggregate stats / weak slots".

Single-item scores already measure caps from the current gear totals. A whole set raises
three questions: what the set as a whole is worth, what each piece is worth inside it, and
how one change moves the whole - including changes that move a cap, such as a weapon of
another type for a race with a weapon skill bonus.

## Decision

1. **The engine scores the whole set.** The set's value is every item scored by the engine
   on top of the items before it. A stat's counted amount is the area under its value curve
   between two totals, so the parts add up to the same value in any order (an exclusive
   group, which no shipped profile uses, applies per item and is the exception). That holds
   while the caps stay put: they are those of the gear as worn - its weapon types and its
   weapon skill - throughout (`scoring.gear.evaluate_gear`). No formula is repeated outside
   the engine.
2. **A piece is worth what the character loses without it**, the caps staying where the gear
   as worn puts them: exactly the piece scored on top of the rest of the gear.
3. **A replacement is the change in the whole set's value**, the set with the candidate
   valued against the caps of the gear as worn. A two-hander replaces both weapons; an
   off-hand item takes a two-hander off; an off-hand weapon a class cannot yet dual wield is
   not usable. Where the change would move a cap - another weapon type for a race with a
   weapon skill bonus, a piece with weapon skill - the caps after it are shown and a note
   says the change is measured against the current ones. Its explanation compares the two
   sets' summed components, so the lines add up to the change; better or worse uses the
   comparison's tie margin.
   *Revised in milestone 10.* Valued in their own context, two sets differed by the hit that
   a change of weapon skill made surplus, while the skill itself - which version 1 does not
   value - earned nothing: Edgemaster's Handguards showed as a loss. Weapon skill is valued
   from version 2; until then a change is measured against the current caps, as the
   calculator measures every item against the current gear.
4. **What the set lacks and wastes**: caps and breakpoints short of their target, with what
   reaching them is worth (under-served priorities); stats the profile gives no value
   (wasted); pieces worth nothing, or ten or more item levels below the set's median (the
   weakest pieces - item level is a rough sign, and labelled so). Sets are named from their
   pieces, as the data names none; set bonuses are noted, not scored (version 2).
5. **Characters live in the local database** (`data/user/wowgear.sqlite3`, a `characters`
   table, schema version 2), one row each with the whole character as JSON and a version
   that goes up with every save. Gear is kept as item ids; an item missing from the data is
   reported and the rest is still analysed.
6. **Files**: a character exports as JSON (the import format); gear lists as CSV with every
   slot; comparisons as JSON, ranking CSV, components CSV; comparisons and gear analyses as
   a self-contained HTML report - no scripts, nothing loaded from elsewhere, light and dark,
   printable. CSV text cells that a spreadsheet would run as a formula are prefixed with an
   apostrophe.

## Consequences

- The Gear set page, `wowgear gear` and the exports all read the same analysis.
- A full analysis scores each item twice (about 35 scores, under 0.1 s); a replacement two
  whole sets.
  Each score re-hashes the ruleset and profile for its fingerprint, which is most of its
  cost - a candidate for caching if the optimizer (version 3) needs speed.
- Weapon skill is not valued in version 1. The caps come from the gear as worn - racial and
  gear weapon skill included - and a change that moves them is shown, not counted; a piece
  whose only value is weapon skill is worth nothing, and the weakest-pieces list says why.
- Every analysis carries its assumptions (the caps as worked out, the profile's
  assumptions, what version 1 does not value); the page and the reports show them. A profile
  valued for two weapons, worn with one, says that it still counts hit past the melee cap.
