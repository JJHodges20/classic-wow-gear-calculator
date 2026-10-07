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
   between two totals, so the parts add up to the same value in any order. That holds while
   the caps stay put, so the set's weapon types and weapon skill - which move the hit caps -
   are those of the whole set throughout (`scoring.gear.evaluate_gear`). No formula is
   repeated outside the engine.
2. **A piece is worth what the character loses without it**: the set's value less the value
   of the set without it. When removing it leaves the caps where they are, that difference
   is exactly the piece scored on top of the rest of the gear, which is what is computed;
   for a weapon or a piece with weapon skill the set without it is scored in full.
3. **A replacement is the change in the whole set's value**, with the gear without the
   candidate scored in its own context. A two-hander replaces both weapons; an off-hand item
   takes a two-hander off; a weapon that moves the hit cap says so. Its explanation compares
   the two sets' summed components, so the lines add up to the change.
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
- A full analysis scores about seventy items (around 0.1 s); a replacement two whole sets.
  Each score re-hashes the ruleset and profile for its fingerprint, which is most of its
  cost - a candidate for caching if the optimizer (version 3) needs speed.
- Weapon skill is still not valued as a stat (version 2 models it), but its effect on the
  hit caps is counted for the whole set, so a piece with weapon skill can show a loss in hit
  value; the replacement notes say why.
