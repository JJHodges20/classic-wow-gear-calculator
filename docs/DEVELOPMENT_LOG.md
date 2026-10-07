# Development Log

One entry per milestone: what was built, what was decided, the assumptions made, and the
evidence for the gate in `CLAUDE.md`. Newest first.

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
