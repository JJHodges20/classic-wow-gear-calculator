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

## Sections to complete

This document grows with the milestones: the scoring pipeline (milestone 3), item entry and
validation (4), the repository, providers and cache (5), comparison (6), the app (7 and 8),
characters and gear sets (9).
