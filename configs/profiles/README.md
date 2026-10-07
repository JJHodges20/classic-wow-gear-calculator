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

## The profiles

The roadmap's initial class and role matrix, one profile per entry (two for the Holy
paladin, whose raid and pre-raid values differ). Numbers and their sources are in
`docs/research/STAT_WEIGHTS.md`; `draft` means sourced but not yet checked against logs.

| Class | Profile | Role | Status | Weights from |
| --- | --- | --- | --- | --- |
| Warrior | `warrior_tank_deep_prot` Deep Protection | Tank | draft | Undertanker's tank points |
| Warrior | `warrior_dps_fury` Fury (dual wield) | Melee DPS | draft | Sixty Upgrades, Twinstar |
| Warrior | `warrior_dps_arms` Arms (two-hander) | Melee DPS | experimental | The Fury values, as an assumption (no Arms source) |
| Paladin | `paladin_healer_holy` Holy (raid) | Healer | draft | Xcellers |
| Paladin | `paladin_healer_pre_raid` Holy (pre-raid dungeons) | Healer | draft | Xcellers (pre-raid values) |
| Paladin | `paladin_tank_prot` Protection (survival only) | Tank | experimental | A warrior's tank points, as an assumption (no paladin source) |
| Paladin | `paladin_dps_ret` Retribution (two-hander) | Melee DPS | draft | Sixty Upgrades |
| Druid | `druid_tank_bear` Feral tank (Dire Bear) | Tank | draft | Taladril |
| Druid | `druid_healer_resto` Restoration (raid) | Healer | draft | Taladril |
| Druid | `druid_dps_cat` Feral DPS (Cat) | Melee DPS | draft | NerdEgghead (Wowhead) |
| Druid | `druid_dps_balance` Balance (raid) | Caster DPS | draft | Keftenk |
| Priest | `priest_healer_holy` Holy (raid, 3-minute fights) | Healer | draft | Umber |
| Priest | `priest_dps_shadow` Shadow (raid) | Caster DPS | draft | Nostalrius forum |
| Shaman | `shaman_healer_resto` Restoration (raid) | Healer | draft | Jelly's guide |
| Shaman | `shaman_dps_enhancement` Enhancement (two-hander) | Melee DPS | draft | Sixty Upgrades |
| Shaman | `shaman_dps_elemental` Elemental (raid) | Caster DPS | draft | wowsims (Classic Era) |
| Rogue | `rogue_dps_combat` Combat (swords) | Melee DPS | draft | Oto (Nostalrius forum) |
| Hunter | `hunter_dps_marksmanship` Marksmanship (raid) | Ranged DPS | draft | Icy Veins (Impakt) |
| Mage | `mage_dps_frost` Frost (raid) | Caster DPS | draft | Zephriel |
| Warlock | `warlock_dps_destruction` Destruction (Shadow Bolt) | Caster DPS | draft | warlockr simulation |

Not built: a Fury/Prot warrior tank (the roadmap's example of a second tank build) - no 1.12
source gives numbers for it, and Deep Protection covers the warrior tank role.
