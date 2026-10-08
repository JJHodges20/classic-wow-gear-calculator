# Data Model

The canonical models live in `src/wow_gear/models`. Every model rejects unknown fields - except
the provider response schemas in `models/providers/`, which ignore what the app does not
read - and all of them are immutable once built. The vocabularies (classes, roles, races, slots, item
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
| `shapeshift_form` | The druid form the profile fights in (`cat`, `bear`, `dire_bear`), so bonuses "in Cat, Bear and Dire Bear forms only" count |
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

## ComparisonResult (`models/comparison.py`)

| Field | Meaning |
| --- | --- |
| `results` | Every item's `ScoreResult`, ranked (usable first, then by score), with `rank` and `recommendation_label` |
| `outcome` | `winner`, `tie`, `only_usable`, `none_usable` or `single` |
| `winner_id` | The recommended item (`winner` and `only_usable`) |
| `first_id`, `second_id`, `score_delta` | The two items the explanation compares, and the first's score minus the second's |
| `headline`, `why` | The answer in one sentence, and the largest component differences in one phrase |
| `lines` | `ExplanationLine`s: per component, each item's amount and contribution, the difference, a note when a cap or an exclusive group cut an amount, and the line as a phrase |
| `not_valued`, `not_scored` | Stats the profile gives no value; effects and set memberships version 1 does not score |
| `replaced`, `upgrades` | The equipped item scored from the same gear, and each candidate's change against it |
| `notes`, `confidence` | Slot footprints, unusable items, missing current gear; the lower confidence of the deciding items |
| `profile_*`, `ruleset_*`, `score_unit`, `unit_abbreviation`, `fingerprint` | Traceability, and a hash that is the same for the same inputs in any order |

## GearSet and SavedCharacter (`models/gear.py`)

`GearSet`: a name and item ids by equipment slot (`EquipmentSlot`: head ... finger_1,
finger_2, trinket_1, trinket_2, main_hand, off_hand, ranged); an empty slot is absent.
`EQUIPMENT_SLOTS` maps each item slot type to the equipment slots it can fill (a one-hander:
main or off hand; a ring: either finger); a two-handed weapon also leaves the off hand empty
(`BLOCKS_OFF_HAND`).

`SavedCharacter`:

| Field | Meaning |
| --- | --- |
| `id` | Lowercase letters, digits and underscores, from the name when first saved |
| `name`, `notes` | What the player calls it |
| `ruleset`, `class_name`, `race`, `level`, `phase`, `content_mode` | The character's context; the class follows the profile |
| `profile_id` | The build profile its gear is valued with |
| `gear` | Its `GearSet` |
| `version`, `saved_at` | Goes up with every save; when it was last saved (UTC) |

Saved characters are rows of the `characters` table in `data/user/wowgear.sqlite3` (schema
version 2): `id`, `name`, `ruleset`, `class_name`, `version`, `saved_at` and the whole
character as JSON in `payload`. A character exported as JSON is the same object; a gear
list CSV has the columns `slot`, `item_id`, `item_name`, `item_level` and `value_<unit>`
(only `slot` and `item_id` are read back; a bare number is a game item id).

## GearAnalysis and ReplacementResult (`models/gear.py`)

| Field | Meaning |
| --- | --- |
| `score`, `components` | The whole set's value under the profile and every item's components summed by key, largest first |
| `totals` | What the gear adds up to, in the ruleset's order of stats: the current gear totals of a calculation |
| `slots` | `SlotValue` per worn piece: its item level and `score` - what the character loses without it - and whether it is usable |
| `empty` | Slots with nothing in them (the off hand beside a two-hander is not empty) |
| `caps` | `CapStatus` per hard cap, soft cap and breakpoint: `label`, `kind`, `target`, `total` (conversions included), `state` (short, reached, over), `worth` (what reaching it adds), `message`, `derivation` |
| `under_served` | The caps and breakpoints the gear falls short of, with what reaching them is worth |
| `not_valued` | Stats the gear gives that the profile does not value ("Stamina 79") |
| `not_scored` | Procs, on-use effects and unmet conditions no score counts |
| `weakest` | `WeakSlot`s: pieces worth nothing, or ten or more item levels below the set's median |
| `sets` | `SetPieces`: sets with two or more pieces worn, named from their pieces |
| `notes`, `assumptions` | Empty slots, unusable pieces (an off-hand weapon a class cannot dual wield), set bonuses not scored, a two-weapon profile worn with one weapon, items missing from the data; the caps as worked out, the profile's assumptions and what version 1 does not value |
| `fingerprint` | A hash of the gear, context, profile, ruleset and engine |

`ReplacementResult`: the slot and candidate, the items it takes off, `delta` (the whole
set's value with it less as it is, both against the current caps), `outcome` (better,
worse, or a tie within the comparison's margin), both values, both sets' totals, the caps
now and where they would stand after the change, the explanation lines (they add up to
`delta`), whether the candidate is usable, and notes (a two-hander replacing two weapons, a
change of weapon skill that would move a cap).
