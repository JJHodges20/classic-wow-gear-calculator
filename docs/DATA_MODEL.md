# Data Model

The canonical models live in `src/wow_gear/models`. Every model rejects unknown fields, and
all of them are immutable once built. The vocabularies (classes, roles, races, slots, item
types, stats) are in `models/enums.py`; they are names only - what a class may wear or what a
stat is worth is ruleset and profile data.

## Item (`models/item.py`)

The raw properties of one item, as normalized from any source. An item never carries a
score: the same item can score very differently for a Warrior tank and a Holy Paladin.

| Field | Meaning |
| --- | --- |
| `id` | Canonical id, `namespace:key` - `classic_era:19019` for an item from the game, `custom:<key>` for one entered by hand |
| `external_ids` | The item's id at each provider (`{"blizzard": "19019", "vmangos": "19019"}`) |
| `name`, `ruleset`, `phase`, `required_level`, `item_level`, `quality` | As the game states them; `phase` is the first content phase it is available in, when known |
| `slot` | Where it is worn (`ItemSlot`: head ... two_hand, ranged, relic) |
| `armor_type`, `weapon_type`, `relic_type` | Cloth to plate; dagger to wand; libram, idol, totem |
| `unique` | Unique-equipped |
| `allowed_classes`, `allowed_races` | Restrictions the item itself carries; empty means none |
| `stats` | Flat equip bonuses by `Stat`, as tooltips state them: points, or percent for hit, crit, dodge, parry and block, or skill points for defense and weapon skills. Zeros are dropped |
| `weapon` | `WeaponStats`: minimum and maximum damage, speed in seconds, damage school, bonus damage lines; `dps` is computed |
| `equip_effects`, `on_use_effects` | `ItemEffect`s. A stat effect (with an optional condition, such as "against Undead") can be scored; any other effect keeps its tooltip text and is reported as not scored |
| `set_id`, `set_name` | Item set membership; a name needs its id, an id may come without a name |
| `provenance` | `Provenance`: provider, source, source URL, data version, fetch time, license, and whether the item is a custom (theorycrafted) one |

The roadmap lists `armor`, the primary stats, attack and spell power, hit and crit,
defensive stats and resistances as separate fields; here they are keys of `stats`, so the
same code handles every stat and a ruleset can say which ones it allows. Weapon damage, speed
and DPS live in `weapon`; source, provider, URL, data version and fetch time in `provenance`.

`Item.version` is a hash of the in-game properties: it changes when, and only when, they do.

## CharacterContext (`models/character.py`)

Who the item is evaluated for: ruleset, phase, level, class, role, build profile, faction and
race, content mode, an optional target level and creature type, the melee and ranged weapon
types used, and optional `current_stats` - the totals the character's current gear provides
(what the tooltips add up to), which make cap-sensitive results exact. Buffs and an
encounter are recorded for later versions.

## BuildProfile (`models/profile.py`)

A small, versioned research artifact for one class, role and build:

| Field | Meaning |
| --- | --- |
| `id`, `version`, `label`, `class_name`, `role`, `specialization`, `summary` | Identity |
| `ruleset`, `target_phase`, `target_level`, `default_content_mode` | What the profile was written for |
| `score_unit` | The unit scores are in (for example "attack power equivalents") |
| `stat_weights` | Each valued stat with its weight, its `basis` (mechanic, sourced, derived or assumption), a note and its sources |
| `derived_stats` | Conversions to apply, such as Agility into crit; the ratios are ruleset data |
| `hard_caps`, `soft_caps`, `thresholds` | Each refers to a ruleset cap formula (or a fixed value) and says what the build already provides |
| `exclusive_groups` | Stats that cannot all count at once |
| `weapon_preferences`, `proc_assumptions`, `set_bonus_rules`, `assumptions`, `notes` | Stated assumptions |
| `sources`, `validation_status` | Citations, and draft, experimental or validated |

## Ruleset (`models/ruleset.py`)

One game version: phases, content modes (with the target level each implies), classes
(armor and weapon proficiencies, shields, dual wield, relic, roles), races (faction, weapon
skill bonuses), the stats items may carry, stat conversions per class, named caps with the
formula kind that computes them, the formula inputs (`mechanics`), assumptions, and the
sources every block cites.

## ScoreResult (`models/score.py`)

| Field | Meaning |
| --- | --- |
| `score`, `score_unit` | The overall score: the sum of the components, nothing else |
| `components` | `ScoreComponent`s - stat, derived, threshold, weapon, proc, set bonus or context lines, each with the item's amount, the amount that counts after caps, the weight and the contribution |
| `capped_stats`, `threshold_events` | What a cap cut and what a breakpoint did |
| `warnings`, `assumptions`, `eligible`, `ineligibility` | What to be careful about |
| `profile_id`, `profile_version`, `profile_hash`, `ruleset_id`, `ruleset_version`, `ruleset_hash`, `engine_version`, `context_fingerprint`, `item_version`, `item_provider`, `item_data_version` | Everything needed to reproduce the score |
| `validation_status`, `confidence` | How far to trust it |
| `rank`, `recommendation_label` | Set when items are compared |

## GearSet (`models/gear.py`)

Item ids by equipment slot (`EquipmentSlot`: head ... finger_1, finger_2, trinket_1,
trinket_2, main_hand, off_hand, ranged). Used from milestone 9.
