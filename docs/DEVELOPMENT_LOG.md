# Development Log

One entry per milestone: what was built, what was decided, the assumptions made, and the
evidence for the gate in `CLAUDE.md`. Newest first.

## Milestone 2 - Canonical models, ruleset and profile loaders, fixtures (2026-10-07)

**Built**

- Canonical models (`src/wow_gear/models`): the vocabularies (`enums.py`, with
  human-readable `labels.py`), `Item` (stats as a controlled vocabulary, a weapon block,
  equip and on-use effects with optional conditions, provenance, a content-hash version),
  `CharacterContext` (with current gear totals), `BuildProfile`, `Ruleset`, `ScoreResult`
  and `GearSet`. Unknown fields are errors everywhere; all models are immutable.
- `configs/rulesets/classic_era.yaml` 1.0.0: six phases, five content modes with target
  levels, nine classes (armor by level, weapons, shields, dual wield, relics, roles), eight
  races (faction, weapon-skill bonuses), 50 stats, per-class conversions at level 60, five
  named caps and the inputs of their formulas, nine stated assumptions and 43 cited sources.
- Loaders: `rulesets/loader.py` and `profiles/loader.py`, which checks every profile against
  its ruleset (class, role, stats, conversions, caps, levels, phases) and rejects it with the
  file and the reason. A registry lists profiles by class and role.
- Four representative draft profiles (`configs/profiles`): Fury warrior (physical DPS),
  Frost mage (caster DPS), Holy priest (healer), Deep Protection warrior (tank), each weight
  with its basis and source.
- Fixture profiles with round weights for the engine tests (`data/fixtures/profiles`).
- Research notes (`docs/research/`): combat tables, class rules, stat conversions, stat
  weights, data sources - each value with the page it came from and the conflicts found.
- `wowgear check` now loads and reports the rulesets and profiles.

**Decisions** ([0002](decisions/0002-sourced-rulesets-and-profiles.md))

- Every ruleset block cites a source; disputes are resolved by Blizzard's statements first,
  then the majority, with the alternative recorded.
- Profile weights come from 1.12 theorycraft; Pawn's TBC-derived scales and Season of
  Discovery simulator defaults are not used; every profile is draft.
- Melee and ranged attack power are separate stats, damage-only spell damage is its own
  stat, as the game data has them.

**Assumptions**

- The hit-suppression reading for 301-304 skill, the flat 19% dual-wield penalty, the
  dungeon target level (+2) and level-60 conversions at other levels - all listed in the
  ruleset's `assumptions`.
- Profile weights are stage-specific (early raid for Fury, three-minute fights for Holy, 545
  spell power for Frost) and say so.

**Gate**

| Check | Result |
| --- | --- |
| Targeted and full suite | Model, ruleset-loader, profile-loader and shipped-profile tests pass; full suite passes on the committed snapshot |
| Lint and types | `ruff check`, `ruff format --check`, `mypy` (strict) clean |
| Secrets | Hygiene tests pass |
| UI smoke test | No UI change; the shell renders under `streamlit.testing` |
| Configuration | `wowgear check`: ruleset classic_era 1.0.0 with 43 sources, 4 profiles |

## Milestone 1 - Repository foundation (2026-10-07)

**Built**

- A src-layout package `wow_gear` with the thirteen layers of the roadmap (core, models,
  data_sources, processing, repositories, rulesets, profiles, calculations, scoring,
  comparison, optimizer, services, reporting). Each layer's docstring says what it owns
  and may import.
- `core`: settings from `configs/app.yaml` and `configs/providers.yaml` (unknown keys are
  errors), environment overrides (`WOWGEAR_HOME`, `WOWGEAR_DATA_DIR`,
  `WOWGEAR_LOG_LEVEL`), secrets from the environment or `.env` only, logging that masks
  secret values, and the exception hierarchy.
- `configs/providers.yaml` lists the roadmap's providers in its priority order (bundled
  dataset, Warcraft Logs, Blizzard, file import) plus Wowhead as a reference that is never
  fetched; each names the environment variables for its credentials.
- `services/health.py`: the first service, reporting configuration and provider status.
- The `wowgear` command line (`--version`, `check`, `ui`), which calls services.
- A Streamlit shell (`apps/streamlit_app/app.py`) with no feature pages.
- Tests: configuration loading and rejection of bad files, secrets handling, the layer
  boundaries on every import (`tests/unit/test_architecture.py`), repository hygiene (no
  credential in any file git would commit, `.env` ignored, every secret documented blank in
  `.env.example`), the command line, and the app shell through `streamlit.testing`.
- `CLAUDE.md` (the roadmap's constitution plus the layer table and the gate), README,
  architecture and data-model stubs, roadmap status, decision 0001, CI workflow, pinned
  requirements and `scripts/bootstrap.ps1`. The roadmap PDF is in `docs/roadmap/`.

**Decisions** ([0001](decisions/0001-repository-layout.md))

- The folder is `classic-wow-gear-calculator`, as asked; the additions to the roadmap's
  tree are a command line, `data/user/`, dev requirements, CI, decision records, the
  development log and the two rule-enforcing tests.
- Layer boundaries are enforced by a test, including library ownership (`httpx`,
  `sqlalchemy`, `streamlit`, `plotly`) and the rule that provider schemas never reach the
  game math.

**Assumptions**

- None about game mechanics: no formula, ruleset value or profile exists yet. Research into
  the Classic Era mechanics, class rules, item data sources and published stat weights was
  started in parallel for milestone 2.

**Gate**

| Check | Result |
| --- | --- |
| Targeted and full suite | 60 passed |
| Lint and types | `ruff check`, `ruff format --check`, `mypy` (strict) clean |
| Secrets | Hygiene tests pass; `.env` ignored; no credentials in configs |
| UI smoke test | Shell served by `wowgear ui`, opened in Chromium in light and dark: renders, no exception, no page error |
| Architecture | Boundary test passes and is shown to catch a reach-across |
