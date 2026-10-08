# Version 1 audit (milestone 10)

Date: 2026-10-07. Scope: the roadmap's version 1 acceptance criteria (section 15), its testing
strategy (section 11), the engineering rules in `CLAUDE.md`, and the version 1.5 work of
milestone 9.

## How it was done

- **Three independent reviews**, each read-only: theorycraft and calculation correctness
  (every ruleset value against `docs/research/`, the formulas at and around every cap, the
  engine, the whole-gear valuation, six profiles in depth); architecture, code quality and
  security (layers beyond imports, escaping, imports and exports, secrets, error handling,
  performance); documentation and test coverage (every doc against the code and the command
  line's help, section 11 mapped test by test, line coverage).
- **A new user's walkthrough in a real browser** on a fresh project: choose the context,
  search an item, enter another from its tooltip, read the recommendation, enter current
  stats and watch a cap-sensitive answer change. Then every page in light and dark, at 1440
  px and on a 420 px phone, checked for exceptions, errors and sideways overflow.
- Every finding was fixed or is listed under the limitations below, with the reason.

## Result

Version 1 meets every acceptance criterion. The audit found three high-severity problems and
a dozen medium ones; all are fixed and tested except one medium finding, scoring speed, which
is deferred with its reason under the limitations below.

| Area | Acceptance test | Evidence |
| --- | --- | --- |
| Context | Select Classic Era, phase, level, class, role and build profile | Context bar; `test_choosing_class_role_and_profile` |
| Manual item | Enter an item, get validation and a score | Manual entry with tooltip reader and preview; `test_a_manual_item_is_previewed_validated_and_scored`, `test_reading_a_tooltip_fills_the_form`, `test_a_manual_item_can_be_kept_in_your_items` |
| Lookup | Search and select a known item through the provider and cache layer | `test_search_finds_items_and_the_comparison_explains_itself`; provider to repository to search in `test_item_search.py` |
| Comparison | A winner, the score difference and a component explanation | Calculator and Compare pages, `wowgear compare`; 102 hand-reviewed comparisons |
| Caps | A cap-sensitive profile shows reduced or zero marginal value | Reviews that reverse at the hit cap; `test_current_stats_change_a_cap_sensitive_recommendation`; the browser walkthrough |
| Profiles | Inspect the weights and thresholds behind a result | Build profiles page; Assumptions on the Calculator, Compare and Gear set pages |
| Traceability | A result records ruleset and profile versions and the item source | Every result and report; fingerprints reproduce in any order |
| Reliability | A provider failure never blocks manual comparison or cached items | `TestCachedItemsWhenTheProviderFails` (search, item, token endpoints failing; expired copies); `test_a_failing_provider_leaves_a_message_and_local_results` |
| UI | Consistent, responsive pages with empty, error and loading states | Six pages clean in light, dark and phone width; `test_app_states.py` |
| Tests | All tests pass, including hand-reviewed golden comparisons | 986 tests pass; 94% line coverage |

## Findings and what was done

### Correctness

- **High - weapon skill counted as a loss in gear sets.** Two sets valued in their own
  contexts differed by the hit a change of weapon skill made surplus, while the skill itself
  (not valued in version 1) earned nothing: Edgemaster's Handguards showed as -2 AP and a
  better swap could read "Worse". Gear is now valued against the caps of the gear as worn; a
  change that would move a cap is shown, not counted ([decision 0008](decisions/0008-gear-sets.md),
  revised). Tests: `test_weapon_skill_is_worth_nothing_not_a_loss_of_hit`,
  `test_a_weapon_of_another_type_is_valued_at_the_current_cap`.
- **Medium - an off-hand weapon was never checked for dual wield** (a paladin's second sword
  was worth 420 AP). Pieces and candidates in the off hand now follow the ruleset's dual wield
  rule, by class and level. Tests: `TestDualWield`.
- **Medium - verdicts shown without their assumptions** on the Compare and Gear set pages and
  in the reports. Each now lists the caps as worked out, the profile's assumptions and what
  version 1 does not value; a profile valued for two weapons, worn with one, says so.
- **Medium - feral attack power was never scored by a test**, and the druid form was a free
  string a typo would silently zero. Forms are now a closed set (`ShapeshiftForm`), and two
  reviews score real feral maces for the cat and bear profiles.
- **Low** - breakpoints already reached or lost, fixed caps, a soft cap without an end and
  every class conversion rate had no test: now tested (`test_formulas.py`). A cap message split
  an amount below zero differently from how it was counted: fixed. Two consequences of the cap
  formulas are now stated as assumptions (`configs/rulesets/README.md`). One research note cited
  an undefined source.

### Data integrity and reliability

- **High - an online lookup replaced the player's own version of an item** (an import under a
  game id), which was then lost when the lookup expired. The repository now refuses it, and
  search shows the player's version.
- **Medium - expired Blizzard lookups outlived 30 days in a running app** (they were dropped
  only at start-up). They are now dropped while the app runs, at most a minute late.
- **Medium - cached items when the provider fails** were tested only for the search endpoint.
  Item and token failures, garbage responses and expired copies are now covered.
- **Low** - one unreadable row broke every search that found it: it is now logged and skipped.

### Architecture, security and the interface

- **High - CSV exports turned negative numbers into text** (the formula guard applied to every
  cell). Numbers are written as numbers; only text is guarded.
- **Medium - inputs that ended in a traceback**: an imported character for an unknown ruleset,
  a long tooltip first line or a zero weapon speed, a CSV field too large to read, deeply
  nested JSON, a character file that is not UTF-8. Each is now an explained refusal; uploads
  are capped at the 5 MB import limit.
- **Medium - the online search ran again on every click** with the online toggle on. It is now
  reused for five minutes.
- **Medium - tables overflowed the screen on phones** (Build profiles, Data health). They now
  scroll within themselves with readable columns.
- **Low** - names from data reached Markdown widgets unescaped (an item named like an image
  could load one): escaped. Secrets were masked only by the command line and not in
  tracebacks, and the settings' repr held them: masked everywhere, the repr leaves them out.
  The replacement verdict used its own margin: it now uses the comparison's tie rule.
  Formatting was written five times and could print "-0.0": one copy in `models/formatting.py`.
  Nine unused functions and the unused `plotly` dependency were removed. Manual items could
  not be kept, as the docs said: "Keep in my items" now does it.

### Documentation

Corrected: the architecture's statement that the player's items are never overwritten (now
true), data sources (manual items, log masking, cache expiry), the data model (provider
schemas, the druid form, the new analysis and replacement fields), decisions 0001, 0006 and
0008, the rulesets README, the README's commands and layout, and `configs/app.yaml`'s
reserved `cache_dir`.

## Limitations of version 1

By design (the roadmap's later versions):

- Weapon skill, procs, on-use effects and set bonuses are listed, not valued (version 2).
- An off-hand weapon is valued like a main-hand one in the dual-wield profiles, and the
  dual-wield hit band follows the profile rather than the weapons worn (stated assumptions;
  version 2's weapon models).
- Profiles are draft or experimental: their weights come from cited guides and simulations,
  not validation against logs (version 5).

Found by the audit and left, with the reason:

- **Talents not modelled for skill**: Combat rogues' Weapon Expertise (extra weapon skill)
  and whether a Retribution paladin takes Precision need research before a profile states
  them; the profiles say which talents they assume.
- **Speed**: a score takes about 1 ms, mostly re-hashing the ruleset and profile for its
  fingerprint; Data health re-reads the YAML on each click (about 0.1 s). Caching them is
  safe only with care for copied models, so it waits for the optimizer (version 3), which
  needs it.
- **Live data**: the Blizzard adapter is tested against recorded responses, not the live API.
- **Item data terms**: the bundled dataset comes from VMaNGOS (GPL-2.0 tools; the game data is
  Blizzard Entertainment's).

## Gate

| Check | Result |
| --- | --- |
| Tests | 986 pass (unit, integration, regression with 102 hand-reviewed comparisons, UI) |
| Coverage | 94% of lines (package and app) |
| Lint and types | `ruff check`, `ruff format --check`, `mypy` (strict, package and app) clean |
| Secrets | Hygiene tests pass; secrets masked in both processes' logs |
| Browser | The walkthrough and 24 page views clean in light, dark and on a phone |
