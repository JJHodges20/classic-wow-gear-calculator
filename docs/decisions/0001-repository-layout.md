# 0001 - Repository layout and deviations from the roadmap tree

Date: 2026-10-07. Status: accepted.

## Context

Section 4 of the roadmap proposes a repository tree for `wow-classic-gear-calculator/`. The
project lives in `classic-wow-gear-calculator/`, the folder the user named. Milestone 1 asks
that any deviation from the proposed tree be explained.

## Decision

The tree follows the roadmap: `configs/` (app, providers, rulesets, profiles), `data/` (raw,
processed, cache, fixtures), `src/wow_gear/` with the thirteen packages in the roadmap's
order, `apps/streamlit_app/` (app.py, pages, components, state), `tests/` (unit,
integration, regression, ui), `docs/` and `scripts/`. The additions:

1. **Folder name** `classic-wow-gear-calculator`, as the user asked.
2. **`src/wow_gear/cli.py`**, a command line (`wowgear`). The roadmap says services are
   "consumed by UI, CLI, or future API"; the CLI is that consumer and is held to the same
   rule as the app: it calls services.
3. **`data/user/`** for what the user saves (characters, gear sets, custom profiles),
   kept apart from `data/cache/`, which may be cleared at any time. (Later: item lookups
   are cached in the database under `data/user/`, each with its expiry - decision 0004 -
   so `data/cache/` is reserved and nothing writes there yet.)
4. **`requirements-dev.txt`** next to `requirements.txt`, and the same split as optional
   dependencies in `pyproject.toml`.
5. **`.github/workflows/ci.yml`**, the CI foundation milestone 1 asks for.
6. **`docs/decisions/`** for decision records like this one, **`docs/DEVELOPMENT_LOG.md`**
   for the gate evidence of each milestone, and **`docs/roadmap/`** for the roadmap PDF.
7. **`tests/unit/test_architecture.py`** enforces the layer boundaries on every import, and
   `tests/unit/test_repository_hygiene.py` keeps credentials out of the repository.

## Consequences

The architecture rules are checked by the test suite rather than by review alone. A new
module must sit in one of the named layers or the architecture test fails.
