# 0002 - Rulesets and profiles are built from cited sources

Date: 2026-10-07. Status: accepted.

## Context

The roadmap forbids inventing Classic mechanics and asks that every profile cite its
sources and carry a validation status. Classic Era runs on patch 1.12 rules, but the live
wikis mostly describe later expansions, several mechanics were debated for years (the hit
cap, the dual-wield penalty), and current guides publish stat priorities rather than
numbers.

## Decision

1. **Every ruleset block cites a source**, and the schema rejects a block that cites none or
   cites one not listed. The research behind each value, with conflicts, is in
   `docs/research/` (combat tables, class rules, stat conversions, stat weights, data
   sources). Where sources disagree the ruleset takes Blizzard's own statements first (the
   2019 hit-table posts), then the majority of independent sources, and records the
   alternative in `assumptions` or a conversion `note`.
2. **Version 1 uses these mechanics:** the melee miss formula with hit suppression (9% cap
   at 300 skill against a level 63 boss, 6% at 305), the flat 19% dual-wield penalty (28%
   cap), spell hit 83% against +3 levels with a 99% maximum (16% cap), crit immunity at
   440 defense, and per-class conversions at level 60.
3. **Profile weights come from 1.12 theorycraft** (forum posts, community spreadsheets,
   simulators, tool presets) and say which. Pawn's built-in Classic scales are not used:
   their own file says they were designed for The Burning Crusade. wowsims defaults that are
   Season of Discovery carry-overs are not used.
4. **Every profile is `draft`** until it has hand-reviewed comparisons (milestone 6) and a
   check against simulation or logs (roadmap version 5).
5. **The stat vocabulary follows the game data:** melee and ranged attack power are separate
   stats ("+X Attack Power" grants both), damage-only spell damage is separate from spell
   damage and healing, and a weapon-skill bonus counts only with a weapon of its type.

## Consequences

- A ruleset value without a source cannot be added; a disputed one is visible as such.
- Profiles are honest about their stage: the Fury profile states early-raid weights, the
  Holy priest profile a three-minute fight, the Frost mage profile 545 spell power.
- Weapon skill, procs, set bonuses and normalized weapon damage are listed as not modeled;
  they belong to version 2.
