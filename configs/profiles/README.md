# Build profiles

One YAML file per build profile, in a folder named after the class:
`configs/profiles/<class>/<profile id>.yaml`. The file name is the profile id. Profiles are
data, not code: adding a build means adding a file, never a branch in the app.

A profile is a small, versioned research artifact (roadmap section 10). Bump `version`
whenever a weight, cap or threshold changes; stored results name the version they used, and
the golden fixtures that pin a profile's behavior name it too.

## Fields

```yaml
id: warrior_dps_fury            # matches the file name
version: 1.0.0
label: Fury (dual wield)
class_name: warrior
role: melee_dps                 # one of the class's roles in the ruleset
specialization: Fury
summary: One or two sentences on who this profile is for.
ruleset: classic_era
target_phase: 6                 # optional: the content it was written for
target_level: 60
default_content_mode: raid_pve
score_unit: attack power equivalents
validation_status: draft        # draft, experimental or validated

stat_weights:                   # every stat the profile values
  - stat: attack_power
    weight: 1.0
    basis: derived              # mechanic, sourced, derived or assumption
    note: The score unit.
  - stat: crit
    weight: 25.0
    basis: sourced
    sources: [some_guide]       # mechanic and sourced weights must cite
    note: Value of 1% crit in attack power, as the guide gives it.

derived_stats:                  # conversions the ruleset holds the ratio for
  - {source: strength, target: attack_power}
  - {source: agility, target: crit}

hard_caps:                      # nothing beyond the cap counts
  - stat: hit
    cap: {ruleset_cap: melee_hit, reduced_by: 0}
soft_caps:                      # a fraction counts between starts_at and ends_at
  - stat: hit
    starts_at: {ruleset_cap: melee_hit}
    multiplier: 0.5
    ends_at: {ruleset_cap: dual_wield_hit}
thresholds:                     # reaching the value is worth `bonus` once
  - stat: defense
    at: {ruleset_cap: crit_immunity_defense}
    label: Crit immunity
    bonus: 50
    basis: assumption

assumptions: [Statements a reader needs to trust the numbers.]
proc_assumptions: []            # version 1 does not value procs; say so here
set_bonus_rules: []             # version 1 does not value set bonuses; say so here
sources:
  - {id: some_guide, title: "...", url: "https://...", retrieved: 2026-10-07}
```

A cap refers to a cap formula in the ruleset (`ruleset_cap`) or, rarely, gives a `fixed`
number; `reduced_by` is what the build's talents already provide, so a rogue with 5% hit
from Precision writes `reduced_by: 5` against the melee hit cap.

## Checks at load time

A profile is rejected, with the file and the reason, when it weights a stat twice, cites a
source it does not list, gives a mechanic or sourced weight without a source, caps a stat it
does not value, names a conversion or cap the ruleset lacks, applies a cap to the wrong stat,
or names a role its class does not have in the ruleset.

## Reviews

Each profile has at least five hand-reviewed comparisons it should rank correctly, as golden
fixtures under `data/fixtures/reviews/<profile id>/` (from milestone 6). A change that flips
one of them fails the test suite until the review is re-done.
