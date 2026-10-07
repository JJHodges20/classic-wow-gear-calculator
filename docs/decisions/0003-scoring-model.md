# 0003 - The version 1 scoring model

Date: 2026-10-07. Status: accepted.

## Context

The roadmap asks for an explainable weighted model in version 1, structured so that later
formulas can replace simple weights, with hard caps, soft caps, breakpoints, conditional
stats and mutually exclusive effects, and a score that is never presented as absolute truth.

## Decision

1. **A score is a sum of components.** Each component is an amount of something (a stat, a
   converted stat, weapon damage, a conditional bonus) times its weight, or a threshold
   bonus. Procs, on-use effects and set bonuses appear as components worth zero, so they are
   visible and never silently valued.
2. **Caps are curves, evaluated against the character.** A curve has a dead zone, a full
   band, an optional soft band and a nothing-beyond region; an item counts for the area it
   covers between the character's current total and the total with it. This handles hard
   caps, soft caps and suppressed hit with one rule, and makes the same item worth less to a
   character already near a cap.
3. **The baseline is current gear minus the item replaced.** Comparing two helms means
   removing the equipped helm's stats first. Without current gear the baseline is zero and
   the result carries a cap-sensitivity warning, as the roadmap requires.
4. **Primary stats are valued through conversions.** A profile values attack power, crit and
   the like; Strength and Agility reach them through the ruleset's conversion for the class,
   and the breakdown shows each conversion as its own line.
5. **Eligibility does not block scoring.** An unusable item is scored and marked with the
   reasons; comparisons rank usable items first.
6. **Confidence is a count of reasons for doubt**: a profile that is not validated, missing
   current gear for a cap-sensitive stat, unscored effects, conversions used away from their
   level, a profile written for another level. None is high, one is medium, more is low.
7. **Every result is reproducible**: it records the item version, the profile version and
   hash, the ruleset version and hash, the engine version and a fingerprint of all inputs.

## Consequences

- Golden fixtures pin the arithmetic; a change to the engine's math bumps `ENGINE_VERSION`.
- Version 2 can replace a stat's weight with a formula (weapon models, mitigation, threat)
  by adding component kinds, without changing how results are read or explained.
