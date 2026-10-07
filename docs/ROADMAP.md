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
| 7 | Streamlit shell + design system + calculator page | Not started |
| 8 | Compare, Profiles, Item Database, and Data Health pages | Not started |
| 9 | Saved character profile + full gear-set context | Not started |
| 10 | V1 audit: correctness, architecture, UX, tests, docs | Not started |

## Version 1 acceptance criteria

| Area | Acceptance test | Status |
| --- | --- | --- |
| Context | User can select Classic Era, phase, level, class, role, and build profile | Open |
| Manual item | User can enter an item manually and receive validation plus a score | Open |
| Lookup | User can search/select a known item through the provider/cache layer | Open |
| Comparison | User can compare at least two items and see a winner, score delta, and component explanation | Service and command line (M6); app in M7 |
| Caps | At least one cap-sensitive profile demonstrates reduced/zero marginal value correctly | Met: Fury, Deep Protection and Frost reviews reverse at the hit cap (M6) |
| Profiles | User can inspect the profile weights/thresholds used for the result | Open |
| Traceability | Result records ruleset/profile version and item source | Met in results (M3, M6); shown in the app in M7 |
| Reliability | Provider failure does not prevent manual comparison or cached-item use | Met in services (M5, M6); app in M7 |
| UI | Core pages are visually consistent, responsive, and handle empty/error/loading states | Open |
| Tests | All unit/integration/UI tests pass, including hand-reviewed golden comparisons | 20 reviewed comparisons pass (M6); UI tests grow in M7 and M8 |

## Later versions (not in the build plan)

Version 2.0 (advanced Classic math: weapon models, mitigation, threat, procs, set bonuses,
sensitivity), 3.0 (gear optimizer), 4.0 (encounter-aware recommendations) and 5.0
(validation against logs and simulation) are described in the roadmap and are not part of
its ten-milestone build plan.
