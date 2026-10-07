# 0005 - Comparing items and explaining the answer

Date: 2026-10-07. Status: accepted.

## Context

The roadmap asks that a player can compare two or more items and see a winner, the score
difference and a component explanation ("+12.4 from healing power, +5.1 from intellect,
-3.8 from lost regeneration, and 0 from excess hit beyond the selected cap"), that the
answer is "recommended under this profile and these assumptions", and that each profile
ranks at least five hand-reviewed comparisons correctly.

## Decision

1. **One baseline for every candidate**: current gear minus the equipped item. Scores are
   then directly comparable, and the difference against the equipped item is the upgrade.
2. **Usable items rank first.** An unusable item keeps its score and reason, so a player sees
   what it would have been worth; when only one item is usable it is recommended and
   measured against the best unusable one (`only_usable`).
3. **Small differences are ties.** A gap under 0.05 points, or under 0.5% of the larger
   score, is reported as effectively equal with no winner: the weights come from community
   spreadsheets and are not precise to the decimal.
4. **The explanation is a difference of components** between the two deciding items, so its
   lines add up exactly to the score difference. Equal components are left out unless a cap
   or an exclusive group cut one side - a wasted stat is part of the answer. Stats a profile
   does not value and effects version 1 does not score are listed separately, never folded
   into the number.
5. **Items that do not compete for one slot are flagged**, not refused: the comparison still
   scores them, and a note says each is scored alone (and that a two-handed weapon also
   takes the off hand).
6. **Reviews use real items.** Each shipped profile has at least five reviewed comparisons
   of bundled items in `data/fixtures/reviews/`, with the hand calculation and the reason a
   player would agree. Several are pairs whose answer reverses with the player's current hit
   or the content phase, which tests the cap and eligibility logic on real data.

## Consequences

- A ranking that depends on unscored effects (procs, set bonuses) says so and carries lower
  confidence; version 2 can value them without changing how the comparison is explained.
- A review fails when its profile, the ruleset or a reviewed item changes, and must then be
  reviewed again by hand.
