# Classic Gear Calculator

A local-first workspace for World of Warcraft Classic players. Choose a ruleset, class, role
and build profile; enter an item by hand or find it in an item database; and get an
explainable comparison that shows which item better supports that build, by how much, and
why.

> Do the game math once, make the assumptions visible, and never hide a recommendation
> behind a mystery score.

The product roadmap is in [docs/roadmap/](docs/roadmap/); progress against its ten-milestone
build plan is tracked in [docs/ROADMAP.md](docs/ROADMAP.md).

## Status

Milestones 1 to 6 are complete: the Classic Era ruleset and four sourced build profiles
(Fury and Deep Protection warrior, Frost mage, Holy priest, all draft), the explainable
scoring engine, manual item entry, the bundled item dataset with optional Blizzard lookups,
and item comparison with a component-by-component explanation, available from the command
line. The Streamlit app arrives in milestones 7 and 8, saved characters and gear sets in 9.

## Quick start

Requires Python 3.12 or newer. From the project root in PowerShell:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\bootstrap.ps1
.\.venv\Scripts\wowgear.exe ui
```

The bootstrap script creates `.venv`, installs the app with its development tools, copies
`.env.example` to `.env`, and checks the configuration.

## Commands

| Command | Does |
| --- | --- |
| `wowgear ui [--port 8501] [--no-browser]` | Start the app |
| `wowgear check` | Validate the configuration, load the data, report each provider's status |
| `wowgear items search "<name or id>" [--online]` | Find items |
| `wowgear items import <file.csv or .json>` | Import your own items |
| `wowgear compare <item> <item>... -p <profile> [--phase 3] [--current hit=5] [--replacing <item>] [--json]` | Compare items for a build profile and explain the difference |
| `wowgear --version` | Print the version |

Development:

```powershell
.\.venv\Scripts\python.exe -m pytest -n auto
.\.venv\Scripts\ruff.exe check . ; .\.venv\Scripts\ruff.exe format --check .
.\.venv\Scripts\mypy.exe
```

## Item data and credentials

The app ships with every equippable Classic Era item (uncommon quality and better) and
works offline. Online lookups through Blizzard's Game Data API are optional: create a client
at [develop.battle.net](https://develop.battle.net/access/clients) and put its id and secret
in `.env` (never in `configs/` or code; `.env.example` lists the variables). You can also
import your own items from CSV or JSON. Wowhead is used only as a human reference: the app
links to it and never fetches from it. Sources and terms are in
[docs/DATA_SOURCES.md](docs/DATA_SOURCES.md).

## Project layout

```
configs/            app settings, providers, rulesets, build profiles (YAML)
data/               raw, processed, cache and user data (git-ignored) and test fixtures
src/wow_gear/       the package, one folder per layer (see docs/ARCHITECTURE.md)
apps/streamlit_app/ the Streamlit app: presentation only
tests/              unit, integration, regression and UI tests
docs/               architecture, data model, roadmap status, decisions, development log
scripts/            setup and maintenance scripts
```

## Documentation

- [CLAUDE.md](CLAUDE.md) - engineering rules for anyone (or any agent) changing the code
- [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) - layers, rules, configuration
- [docs/DATA_MODEL.md](docs/DATA_MODEL.md) - the canonical models
- [docs/ROADMAP.md](docs/ROADMAP.md) - milestone status and the version 1 acceptance criteria
- [docs/DEVELOPMENT_LOG.md](docs/DEVELOPMENT_LOG.md) - what each milestone built and its gate evidence
- [docs/decisions/](docs/decisions/) - decision records

World of Warcraft is a trademark of Blizzard Entertainment. This is an unofficial fan tool.
