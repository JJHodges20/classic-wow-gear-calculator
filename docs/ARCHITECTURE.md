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
   comparison / optimizer   item A vs item B, replacement deltas; later whole sets
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

## Sections to complete

This document grows with the milestones: item entry and validation (4), the repository,
providers and cache (5), comparison (6), the app (7 and 8), characters and gear sets (9).
