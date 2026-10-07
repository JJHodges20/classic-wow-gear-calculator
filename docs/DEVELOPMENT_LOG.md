# Development Log

One entry per milestone: what was built, what was decided, the assumptions made, and the
evidence for the gate in `CLAUDE.md`. Newest first.

## Milestone 7 - Streamlit shell, design system and calculator page (2026-10-07)

**Built**

- `.streamlit/config.toml`: light and dark palettes - a warm neutral page, navy and
  charcoal text, gold for what is selected or recommended, green and red kept for
  differences - with Streamlit's bundled fonts, no Deploy button and no usage statistics.
- The shell (`app.py`): page setup, the design system, top navigation, a footer.
- The calculator page, in the roadmap's layout: the context bar and breadcrumb; item A and
  item B by search (slot filter that follows the other item, optional online lookup) or by
  hand (a tooltip reader, the stat fields the slot needs, a validated preview before use);
  the recommendation (recommended item, scores, the difference with ▲/▼, the component
  lines, notes, confidence, "recommended under this profile and these assumptions"); and
  advanced tabs for assumptions, caps, current stats and the raw math.
- The current stats tab asks only for the totals that can change the answer
  (`CalculatorService.gear_total_stats`), plus race and main-hand weapon when a hit cap
  depends on weapon skill, and which item is worn now so its stats come out of the totals.
- `services/errors.py` so the app can catch service errors without importing `core`.
- App tests under `streamlit.testing` on a throwaway fixture project: choosing class, role
  and profile; search to comparison; a manual item previewed, validated and scored; an
  invalid manual item refused; current stats reversing a cap-sensitive answer; the worn item
  taken out of the totals; an unusable item explained; a failing provider leaving a message
  and local results. The fixture dataset gained Truestrike Shoulders and Drake Talon
  Pauldrons for the cap test.
- `mypy` strict now covers the app as well as the package.

**Decisions** ([0006](decisions/0006-app-design-system.md))

- The palette lives in Streamlit's theme; custom elements are escaped HTML styled by CSS
  variables for the reported theme; colour never signals alone; pages are functions behind
  `st.navigation`; one cached workspace per project.

**Assumptions**

- "Phone width" is checked at 420 pixels; Streamlit stacks the columns there.

**Found on the way**

- Streamlit treats a `None` stored in session state as "nothing chosen", so options such as
  "Any slot" and "Not given" use string sentinels.
- The app's first test opened the user's own workspace; app tests now always run on a
  fixture project.

**Gate**

| Check | Result |
| --- | --- |
| Targeted and full suite | App tests and the service additions pass; the full suite passes on the committed snapshot (515 tests) |
| Lint and types | `ruff check`, `ruff format --check`, `mypy` (strict, package and app) clean |
| Secrets | None added; `.streamlit/secrets.toml` ignored; hygiene tests pass |
| UI smoke test | In Chromium: the empty page, a search comparison, the current-stats change and the manual entry flow in light and dark, and the comparison at 420 pixels wide - no exceptions, no page errors, no requests leaving the machine |

## Milestone 6 - Item comparison service and explainable breakdown (2026-10-07)

**Built**

- `comparison/compare.py` and `models/comparison.py`: two or more items scored from one
  baseline (current gear minus the equipped item), ranked with usable items first, and an
  outcome - a winner, a tie (within 0.05 points or 0.5%), the only usable item, none usable,
  or one item scored. The explanation is the per-component difference between the two
  deciding items; its lines add up to the score difference, keep a stat a cap wasted ("0
  from hit (Gauntlets of Might: none of its 1 counts)"), and list separately the stats the
  profile does not value and the effects version 1 does not score. Items that do not fill
  the same slot are flagged (a two-hander against a one-hander especially). With an equipped
  item, each candidate's change against it is reported.
- `services/calculator.py`: what the app and command line call - the classes, roles and
  profiles a ruleset offers, a checked context with the profile's defaults, the same
  validation for every item whatever its source, scoring and comparing.
- `reporting/text.py` and `wowgear compare <items> -p <profile> [--phase] [--current
  hit=5] [--replacing] [--json]`.
- Twenty hand-reviewed comparisons of real items, five per shipped profile, in
  `data/fixtures/reviews/` (`tests/regression/test_profile_reviews.py`). Several are pairs
  whose answer reverses with the player's current hit (Truestrike Shoulders and Drake Talon
  Pauldrons for Fury; Seal of the Damned and Ring of Spell Power for Frost) or with the
  phase, class or armor type (an unavailable, a restricted or an unwearable item recommended
  against). Every expected number was worked out by hand first; the engine agreed with all
  twenty on the first run.

**Decisions** ([0005](decisions/0005-comparison-and-explanation.md))

- One baseline for all candidates; usable items rank first; ties below the precision of the
  weights; the explanation is a difference of components; slot mismatches are flagged, not
  refused; reviews use real items and a check that they still match the bundled dataset.

**Assumptions**

- The tie margin (0.05 points or 0.5% of the larger score) is a judgment about how precise
  community stat weights are, not a sourced value.

**Found on the way**

- The phase heuristic counted loot rows from patches 1.2 and 1.3 (when some Molten Core
  bosses dropped tier 2 belts and bracers) and missed raid bosses VMaNGOS summons by script,
  which have no spawn row (Nefarian, Ragnaros, the Zul'Gurub summons, Ouro, Sapphiron). 40
  Blackwing Lair items were marked phase 1, two Ragnaros items phase 3, three Ouro items
  phase 6 and 26 world drops phase 2. Loot is now read at patch 1.12 only, the summoned
  bosses are placed by a documented table, and the build lists any boss it cannot place.
- 118 of Blizzard's stat-budget test items ("90 Epic Frost Belt", "63 Green ...") had passed
  the placeholder filter; the dataset now holds 7,741 items.
- Proc and use-effect texts showed wrong numbers: a proc takes its number from the spell it
  triggers (`$18817s1`), which the renderer ignored ("stealing 1 life" for 35). It now
  follows the reference and writes ranges, periods and chain targets as the game does; 143
  texts were corrected and no stat changed.
- The dataset version now ends with a digest of its items, so a rebuilt dataset is reloaded
  by existing workspaces even on the same day and snapshot.
- The log handler kept the stderr of the moment it was created; a second command in one
  process wrote to a closed stream. It now writes to the current stderr.
- Streamlit sends usage statistics to Streamlit's servers by default; `wowgear ui` turns
  them off.

**Gate**

| Check | Result |
| --- | --- |
| Targeted and full suite | Comparison, service, command line, reviews, VMaNGOS reader and build tests pass; the full suite passes on the committed snapshot (495 tests, from 385) |
| Lint and types | `ruff check`, `ruff format --check`, `mypy` (strict) clean |
| Secrets | None added; hygiene tests pass |
| Real data | `wowgear compare 12640 "Mask of the Unforgiven" -p warrior_dps_fury --current hit=5`: Lionheart Helm by 56.0 AP, with its explanation; unknown items, profiles and stats are refused with a reason |
| UI smoke test | No UI change; the shell renders in a real browser in light and dark with no exceptions or page errors, and no longer contacts Streamlit's servers |

## Milestone 5 - Item repository, first lookup provider, cache (2026-10-07)

**Built**

- The bundled dataset: `scripts/build_bundled_dataset.py` converts a VMaNGOS database
  snapshot (`data_sources/vmangos.py`, `processing/vmangos.py`) into
  `data/bundled/classic_era_items.json.gz` - 7,859 items, every equippable one of uncommon
  quality or better at its patch 1.12 version, with phases by drop source or first patch.
  Equip spells map to stats by aura; spell-specific bonuses, procs and profession skills are
  kept as text. The build cross-checks each mapped spell against its tooltip text: 432
  agree, 3 differ (data quirks inside VMaNGOS, two of them developer items).
- `repositories/`: SQLite through SQLAlchemy - canonical items by origin (bundled, cache,
  user) with search, filters, paging, expiry, and a log of provider calls.
- `data_sources/blizzard.py` and `processing/blizzard.py`: the Blizzard Game Data API
  (Classic Era namespace, OAuth client credentials, item and item search) and its
  normalizer, which reads equip lines with the same tooltip parser as manual entry.
- `data_sources/files.py` and `processing/imports.py`: CSV and JSON import through the
  manual form.
- `services/item_search.py` and `services/workspace.py`: local search first, online on
  request, validation, caching for at most 30 days, notices instead of failures; the
  workspace that opens it all. `wowgear check` loads the data; `wowgear items search` and
  `wowgear items import`.

**Decisions** ([0004](decisions/0004-item-providers.md))

- Bundled data from VMaNGOS; Blizzard as the first lookup provider; Warcraft Logs not an
  item provider (no stats); Wowhead linked, never fetched; file import through the form.

**Assumptions**

- The Blizzard response shape follows its documentation and published examples; the tests
  use constructed responses, and no live call was made (no credentials).
- Phases of non-raid items follow the patch they first appear in.

**Found on the way**

- "+X Attack Power" carries two auras, melee and ranged: attack power and ranged attack
  power are separate stats. Some items grant different amounts of spell damage and healing;
  the shared amount is spell power and the excess is damage-only or healing-only.
- Mana per 5 is stored as the base value plus one, like every other equip spell.

**Gate**

| Check | Result |
| --- | --- |
| Targeted and full suite | Repository, provider, normalization, import and search tests pass: provider response to search result, cache fallback on five kinds of failure, expiry restoring the bundled item, manual and provider normalization agreeing, search to score; the full suite passes on the committed snapshot |
| Lint and types | `ruff check`, `ruff format --check`, `mypy` (strict) clean |
| Secrets | Credentials only from the environment; masked in logs; hygiene tests pass |
| Real data | `wowgear check` loads 7,859 items; `wowgear items search lionheart` finds Lionheart Helm; `--online` without credentials falls back with a notice |
| UI smoke test | No UI change; the shell renders under `streamlit.testing` |

## Milestone 4 - Manual item entry and validation (2026-10-07)

**Built**

- `models/forms.py`: the manual form - slot and type first, numeric stats, an optional
  weapon block, effect rows (a stat, a conditional stat against creature types, or text),
  and a custom flag.
- `processing/manual.py`: a form into a canonical item (content-derived id, manual
  provenance); a pasted tooltip into a form (name, slot and type line, damage and speed,
  required level, stat and effect lines; what it cannot place is listed).
- `processing/tooltip.py`: Classic tooltip wordings into stats - primary stats, armor,
  block, resistances, hit and crit, spell hit and crit, attack power (melee and ranged, and
  against creature types), feral attack power, spell damage and healing (including the
  split wording), school spell damage, regeneration, defense, dodge, parry, block, weapon
  skills, spell penetration. Procs, on-use effects and unknown lines are kept as text.
- `processing/validation.py`: errors, warnings and notes against the ruleset.
- `services/item_entry.py`: type choices by slot, stat fields grouped for the slot, and a
  preview with readable form errors and validation.

**Decisions**

- Manual items get a content-derived id, so entering the same item twice is harmless.
- A custom item may break plausibility rules; an item claimed to be from the game may not.

**Assumptions**

- "Unusually high" means more than 5% of a percentage stat on one item, and usual weapon
  speeds are 1.0 to 4.0 seconds; both are review prompts, not rules of the game.

**Gate**

| Check | Result |
| --- | --- |
| Targeted and full suite | Tooltip, manual entry, validation and service tests pass, including a pasted Lionheart Helm scoring 116 AP for Fury exactly as hand-calculated; the full suite passes on the committed snapshot |
| Lint and types | `ruff check`, `ruff format --check`, `mypy` (strict) clean |
| UI smoke test | No UI change; the shell renders under `streamlit.testing` |

## Milestone 3 - Scoring engine, cap and threshold hooks, golden tests (2026-10-07)

**Built**

- `calculations/`: target level and weapon skill for a context (`levels.py`); the cap
  formulas - melee, dual-wield and ranged miss with hit suppression, spell miss, crit
  immunity (`caps.py`); value curves with a dead zone, a full band and a soft band
  (`curves.py`); per-class stat conversions (`conversions.py`).
- `rulesets/eligibility.py`: level, phase, class and race restrictions, armor by level,
  weapon proficiency, shields, relics and dual wield, with readable reasons.
- `scoring/amounts.py` and `scoring/engine.py`: an item scored for a context and profile,
  as a sum of components (stats, conversions, weapon damage, conditional bonuses,
  thresholds, and zero-valued procs and set bonuses), with cap and threshold events,
  warnings, assumptions, confidence and a reproducibility fingerprint. Exclusive groups keep
  only the most valuable stat.
- Eleven hand-calculated golden fixtures (`data/fixtures/golden`), each with its working
  written out: the hit dead zone and soft band with and without current gear, replacing an
  item, weapon damage, the crit-immunity breakpoint reached and missed, a talent-reduced
  spell hit cap with Intellect converted to crit, an exclusive group, a conditional bonus
  on and off, and an unusable item.

**Decisions** ([0003](decisions/0003-scoring-model.md))

- A score is the sum of its components; caps are curves evaluated from the character's
  current gear minus the replaced item; eligibility marks rather than blocks; confidence is
  a count of reasons for doubt; every result records the versions and a fingerprint.
- A weapon-skill bonus counts only with a weapon of its type (the context's main-hand or
  ranged weapon).

**Assumptions**

- Procs, on-use effects and set bonuses are worth zero in version 1, and say so.
- Weapon damage per second is valued at a flat weight; weapon speed and normalization are
  version 2.

**Gate**

| Check | Result |
| --- | --- |
| Targeted and full suite | Calculation, eligibility, engine and golden tests pass; the full suite passes on the committed snapshot |
| Golden fixtures | 11 hand-calculated cases, each score equal to its components' sum; scoring is deterministic |
| Lint and types | `ruff check`, `ruff format --check`, `mypy` (strict) clean |
| Architecture | Boundary test passes: calculations import only core, models and rulesets |
| UI smoke test | No UI change; the shell renders under `streamlit.testing` |

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
