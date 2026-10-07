# Roadmap and Status

The product and engineering roadmap is the PDF in `docs/roadmap/`. It is built in the ten
milestones of its Claude Code build plan, each closed by the gate in `CLAUDE.md`.

## Milestones

| # | Deliverable | Status |
| --- | --- | --- |
| 1 | Repository skeleton, CLAUDE.md, configuration, CI/test foundation | Done (2026-10-07) |
| 2 | Canonical models + ruleset/profile loaders + fixtures | Done (2026-10-07) |
| 3 | Core scoring engine + caps/threshold hooks + golden tests | Done (2026-10-07) |
| 4 | Manual item-entry service and validation | Done (2026-10-07) |
| 5 | Item repository + first lookup provider + cache | Done (2026-10-07) |
| 6 | Item comparison service + explainable breakdown | Done (2026-10-07) |
| 7 | Streamlit shell + design system + calculator page | Done (2026-10-07) |
| 8 | Compare, Profiles, Item Database, and Data Health pages | Done (2026-10-07), with a profile for every class and role in the roadmap's matrix |
| 9 | Saved character profile + full gear-set context | Not started |
| 10 | V1 audit: correctness, architecture, UX, tests, docs | Not started |

## Version 1 acceptance criteria

| Area | Acceptance test | Status |
| --- | --- | --- |
| Context | User can select Classic Era, phase, level, class, role, and build profile | Met: the calculator's context bar (M7) |
| Manual item | User can enter an item manually and receive validation plus a score | Met: manual entry with a tooltip reader, a validated preview and a score (M7) |
| Lookup | User can search/select a known item through the provider/cache layer | Met: search with a slot filter and the optional online lookup (M7) |
| Comparison | User can compare at least two items and see a winner, score delta, and component explanation | Met: the calculator page and `wowgear compare` (M6, M7) |
| Caps | At least one cap-sensitive profile demonstrates reduced/zero marginal value correctly | Met: Fury, Deep Protection and Frost reviews reverse at the hit cap (M6) |
| Profiles | User can inspect the profile weights/thresholds used for the result | Met: the Build profiles page and the calculator's tabs; weights can be customised (M7, M8) |
| Traceability | Result records ruleset/profile version and item source | Met: every result, shown in the Raw math tab and on item cards (M3, M6, M7) |
| Reliability | Provider failure does not prevent manual comparison or cached-item use | Met: services and app, with a UI test for a failing provider (M5-M7) |
| UI | Core pages are visually consistent, responsive, and handle empty/error/loading states | Met: Calculator, Compare, Build profiles, Item database and Data health (M7, M8) |
| Tests | All unit/integration/UI tests pass, including hand-reviewed golden comparisons | 785 tests pass, with 100 hand-reviewed comparisons (five per profile) and the roadmap's UI tests (M8) |

## Later versions (not in the build plan)

Version 2.0 (advanced Classic math: weapon models, mitigation, threat, procs, set bonuses,
sensitivity), 3.0 (gear optimizer), 4.0 (encounter-aware recommendations) and 5.0
(validation against logs and simulation) are described in the roadmap and are not part of
its ten-milestone build plan.
