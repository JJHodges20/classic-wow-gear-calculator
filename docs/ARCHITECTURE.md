# Architecture

The calculator is a layered Python package (`src/wow_gear`) with a Streamlit app on top
(`apps/streamlit_app`). Data flows one way, from item sources to the screen:

```
External item providers / bundled data / manual entry
        |
   data_sources             fetch provider-shaped payloads
        |
   processing               normalize into the canonical Item, validate
        |
   repositories             local item repository and cache (SQLite)
        |
   rulesets + profiles      game/version mechanics, build priorities (YAML configuration)
        |
   calculations             every formula
        |
   scoring                  weighted, cap-aware, explainable item scores
        |
   comparison / optimizer   items compared, whole gear sets, replacements; later the optimizer
        |
   services                 use cases for the UI and the command line
        |
   apps/streamlit_app       presentation only
```

## Rules

- Data-source adapters fetch; they do not score items.
- Normalization converts provider-specific fields into one canonical Item model.
- Rulesets define game/version assumptions; build profiles define role priorities.
- The calculation engine owns all formulas. The UI never performs theorycraft math.
- Presentation code formats results; it does not change them.
- A recommendation exposes its assumptions, caps, penalties and uncertainty.
- Manual items and looked-up items pass through the exact same scoring pipeline.
- Every score is reproducible from stored inputs and a versioned scoring profile.

## Layer imports

Each layer's `__init__.py` says what it owns and may import; the table in `CLAUDE.md` is the
same list, and `tests/unit/test_architecture.py` enforces it on every import statement,
together with library ownership (`httpx` in data_sources, `sqlalchemy` in repositories,
`streamlit` and `plotly` in the app) and the rule that provider response schemas never reach
the game math.

## Configuration

| File | Holds |
| --- | --- |
| `configs/app.yaml` | App name, default ruleset, data paths, log level, cache lifetime |
| `configs/providers.yaml` | Item providers in search order, with status and the names of their secret variables |
| `configs/rulesets/*.yaml` | One file per ruleset: mechanics, caps, eligibility, phases, each value with its source (milestone 2) |
| `configs/profiles/<class>/*.yaml` | One file per build profile (milestone 2) |
| `.env` (not in git) | Provider credentials; `.env.example` lists the variables |

Unknown keys in any configuration file are errors, so a typing slip is caught at load time.

## The scoring pipeline

`wow_gear.scoring.engine.score_item(item, context, profile, ruleset, replacing=...)`:

1. **Check the inputs agree**: one ruleset for item, context and profile; the context names
   the profile; the profile fits the class and role.
2. **Eligibility** (`rulesets/eligibility.py`): level, phase, class and race restrictions,
   armor by level, weapon proficiency, shields, relics, dual wield. An unusable item is still
   scored and marked, so a player sees what it would have been worth.
3. **What the item provides** (`scoring/amounts.py`): its stats, its weapon damage per second,
   and the effects that apply. A conditional bonus ("+81 Attack Power when fighting Undead")
   counts only when the context meets it; a weapon-skill bonus only with a weapon of its
   type; procs and on-use effects are listed with no value.
4. **Conversions** (`calculations/conversions.py`): each of the profile's derived rules turns
   a primary stat into what the profile values (Agility into crit), at the ruleset's rate
   for the class.
5. **Caps** (`calculations/caps.py`, `calculations/curves.py`): each capped stat gets a value
   curve - a dead zone (suppressed hit), full value up to the cap, an optional soft band at
   a fraction, nothing beyond. The amount that counts is the area under the curve between
   what the character already has and what it has with the item. What it already has is
   the context's current gear totals minus the replaced item; without them, zero, and a
   warning.
6. **Thresholds**: reaching a breakpoint (crit immunity) adds the profile's bonus once.
7. **Exclusive groups**: where stats cannot all count, only the most valuable does.
8. **The result** (`ScoreResult`): the score is the sum of its components and nothing else;
   cap and threshold events say what happened; warnings, assumptions, confidence, and every
   version and hash needed to reproduce it.

Cap formulas are implemented once per kind (melee, dual-wield, ranged and spell miss, crit
immunity); a ruleset names caps of those kinds and supplies their inputs; a profile refers to
a ruleset cap and says what its talents already provide (`reduced_by`).

## Item entry and validation

A manual item takes the same path as a looked-up one. `services/item_entry.py` offers the
item types that make sense for a slot (armor types for armor, weapon types by hands, relic
types) and the ruleset's stats grouped for the form; `processing/manual.py` turns the
submitted `ManualItemForm` into a canonical `Item` with an id derived from its contents (the
same form gives the same item); `processing/tooltip.py` reads Classic tooltip lines into
stats, so a pasted tooltip can fill the form; and `processing/validation.py` checks the item
against the ruleset:

- **error** - the calculator cannot use it (a stat or phase the ruleset lacks);
- **warning** - unlike any game item (plate below level 40, a sword in a two-hand slot, an
  odd weapon speed, a large percentage); a custom (theorycrafted) item may be so on purpose;
- **info** - what will not be scored (procs and on-use effects kept as text).

A custom item is usable when it has no errors; an item claimed to be from the game must also
have no warnings.

## Items: providers, repository and cache

```
data/bundled (VMaNGOS-built)   Blizzard Game Data API   CSV / JSON files   manual form
        |                              |                       |                |
 data_sources/bundled.py     data_sources/blizzard.py   data_sources/files.py    |
        |                              |                       |                |
 (canonical already)      processing/blizzard.py       processing/imports.py -> processing/manual.py
        \______________________________|_______________________|________________/
                                       |
                         processing/validation.py (against the ruleset)
                                       |
                 repositories/items.py (SQLite: bundled, cache, user)
                                       |
                services/item_search.py   services/item_entry.py
```

- `services/workspace.py` opens everything once: rulesets, profiles, the database
  (`data/user/wowgear.sqlite3`), the bundled dataset (loaded when its version changes),
  expired lookups dropped and their bundled versions restored, and the Blizzard client when
  credentials are set.
- `services/item_search.py` searches locally (every word of the query, exact names first,
  filters for ruleset, slot, armor and weapon type, phase, level, quality and origin) and
  online only on request. Online items are validated and cached with an expiry of at most 30
  days; every call is recorded for data health. Any provider failure becomes a notice beside
  the local results.
- One canonical id per game item (`classic_era:<id>`): a fresher online lookup replaces the
  bundled row until it expires; the player's own items are never overwritten.

See [DATA_SOURCES.md](DATA_SOURCES.md) for the terms of each source.

## Comparison and the explanation

`wow_gear.comparison.compare.compare_items(items, context, profile, ruleset, replacing=...)`:

1. **Score every item from one baseline** - current gear totals minus the equipped item
   (`replacing`) - so the scores are directly comparable.
2. **Rank**: usable items first, then by score; ties in name and id keep the order
   deterministic. Each result gets its `rank` and a `recommendation_label`.
3. **Decide the outcome**: `winner` (the best usable item beats the next usable one by more
   than the tie margin), `tie` (within 0.05 points or 0.5% of the larger score - weights are
   not that precise), `only_usable` (one usable item, measured against the best unusable
   one), `none_usable`, or `single` (one item, scored).
4. **Explain** the two items that decide it, component by component: each
   `ExplanationLine` is the first item's contribution minus the second's ("+36.0 from
   Strength into attack power"). Equal components are left out unless a cap or an exclusive
   group cut one side ("0 from hit (Gauntlets of Might: none of its 1 counts)"). The lines
   add up to the score difference. `why` joins the largest few into one phrase, ending with
   a wasted stat when there is one - the roadmap's "+12.4 from healing power ... and 0 from
   excess hit beyond the selected cap".
5. **Say what is not in the number**: stats the profile does not value, effects and set
   memberships version 1 does not score, and notes - items worn in different slots (a
   two-handed weapon against a one-hander is flagged: it also takes the off hand), unusable
   items with the reason, cap-sensitive stats scored without current gear.
6. **Against the equipped item**: with `replacing`, the equipped item is scored from the same
   baseline and each candidate's change (`Upgrade.delta`) is reported.

The comparison's confidence is the lower of the two deciding items'; its fingerprint is a
hash of every item's score fingerprint, so the same inputs in any order give the same
result.

## The calculator service

`services/calculator.py` is what the app and the command line call: it lists the classes,
roles and profiles a ruleset has, builds a checked `CharacterContext` from a profile and the
player's choices (the profile supplies defaults: level, content mode, phase), runs every
item - manual, imported or looked up - through the same validation, and calls the scoring
engine and the comparison layer. `reporting/text.py` formats a comparison as plain text;
`wowgear compare` prints it (or `--json`) and writes it to a file with `--output` (`.json`,
`.csv`, `.html`, `.txt`) and every score component with `--components`.

## The app

```
apps/streamlit_app/
  app.py          the shell: page setup, theme, top navigation, footer; keeps the shared
                  choices when the player changes page
  pages/          one small script per page, as st.navigation runs them
  views/          what each page draws, as functions: calculator, compare, gear_set,
                  profiles, item_database, data_health, and the setup they share
  components/     the pieces: theme, escaped HTML, item cards, the context bar, the item
                  picker and manual entry, the recommendation, the advanced tabs, the
                  gear set's slots, caps and value, and the export menu
  state/          session keys and helpers; the workspace, cached once per project
```

The pages: **Calculator** (two items, the recommendation and the advanced tabs);
**Compare** (up to eight items ranked, the two best explained, every component in one
table); **Gear set** (a saved character's whole gear: each slot with what the piece is
worth, the set's value and where it comes from, caps and breakpoints as bars, under-served
priorities, stats not valued, the weakest pieces, a replacement tried against the whole
character, the totals sent to the calculator, import and export); **Build profiles** (a profile's weights, conversions, caps evaluated as numbers,
assumptions and sources; save your own weights as a custom profile - [decision
0007](decisions/0007-custom-profiles.md)); **Item database** (filter and page through the
local items, see where each came from, send one to the calculator); **Data health**
(checks, the dataset's version and phases, providers, recent provider calls, the cache).

The calculator page follows the roadmap's layout: a context bar (class, role, build
profile; ruleset, phase; level, content) with a breadcrumb; items on the left - search with
a slot filter and an optional online lookup, or manual entry with a tooltip reader and a
validated preview; the recommendation on the right - the recommended item, the scores, the
difference with ▲/▼, the component lines, notes and confidence; and advanced tabs for
assumptions (weights, conversions, sources), caps, current stats (only the totals that can
change the answer, the equipped item, race and weapon type when a hit cap depends on weapon
skill) and the raw math with every version and fingerprint.

States are designed, not left to chance: an empty result explains the three steps; a
missing dataset, an invalid context, a failing or unconfigured provider, an expired cached
lookup, an item that fails validation and an unusable item each say what happened and what
still works. The design system is in [decision 0006](decisions/0006-app-design-system.md).

## Characters and gear sets

[Decision 0008](decisions/0008-gear-sets.md) has the reasoning; the pieces:

| Module | Does |
| --- | --- |
| `models/gear.py` | `GearSet`, `SavedCharacter`, and the analysis results: `GearAnalysis`, `SlotValue`, `CapStatus`, `WeakSlot`, `SetPieces`, `ReplacementResult` |
| `scoring/gear.py` | What items add up to (`gear_totals`, weapon damage left out) and the whole set scored by the engine (`evaluate_gear`): each item on top of the ones before it, with the set's weapon types and weapon skill throughout |
| `comparison/gear.py` | `check_gear` (slots, a two-hander's off hand, unique items), `analyse_gear` (each piece's worth, caps and breakpoints, under-served priorities, stats not valued, weakest pieces, sets), `replacement` (the change in the whole set's value and its explanation) |
| `repositories/characters.py` | Saved characters in the local database, one row each as JSON, versioned on save |
| `data_sources/files.py`, `processing/gear_files.py` | Reading a character (JSON) or a gear list (CSV) from a file |
| `services/characters.py` | The use cases: new, change, equip, save, delete, analyse, try a replacement, import and export |

A piece's worth is the set's value less the set's value without it; a replacement's is the
set's value with it less the set's value as it is. Both are exact under the scoring model,
and both reuse the engine for every number. The engine's cap curves (`cap_curves`) and
measured totals (`measured_totals`) are public so the cap status reads the same curves the
scores use. `wowgear gear` lists the saved characters, analyses one (or a character file)
and tries an item with `--try SLOT=ITEM`.

## Exports

`reporting/export.py` formats, and never changes a number: a comparison as JSON (the result
model), a ranking CSV and a components CSV; a character as JSON (what the gear import
reads); a gear list as CSV (every slot, the import format); and a comparison or a gear
analysis as one self-contained HTML page - escaped, no scripts, nothing loaded from
elsewhere, light and dark, printable. Text cells a spreadsheet would run as a formula are
prefixed with an apostrophe. The calculator and Compare pages have an Export menu; the
Gear set page exports the character, the gear list and the report.
