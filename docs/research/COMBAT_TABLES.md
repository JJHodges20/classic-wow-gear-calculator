# Research: Classic Era combat tables and caps

Gathered 2026-10-07 for the `classic_era` ruleset (patch 1.12 rules). Every value comes from a
page that was read; "derived" marks values calculated from sourced formulas. Values the
calculator uses in version 1 are marked **used**; the rest are kept for version 2.

Notes on the sources:

- Blizzard's 2019 posts on the hit tables (us.forums.blizzard.com thread 185675) no longer
  load; they are quoted from the magey Classic Warrior wiki, which added them on 2019-05-30
  and 2019-06-04.
- 2006 WoWWiki revisions are read through warcraft.wiki.gg's page history (`?oldid=`).
- Current warcraft.wiki.gg pages often describe later expansions; that is flagged.

## 1. Melee miss and the hit cap (used)

| Value | Applies to | Source | Note |
| --- | --- | --- | --- |
| Miss = 5% + gap x 0.1% when the gap (target defense - attacker skill) is 10 or less; 5% + gap x 0.2% when it is 11 or more | Player against mob, melee or ranged | [magey: Attack table](https://github.com/magey/classic-warrior/wiki/Attack-table) (2022-07-17); [WoWWiki Miss, 2006-11-30](https://warcraft.wiki.gg/wiki/Miss?oldid=3933316) | Beaza's 2006 formula; testing at +3 levels measured 7.81% miss over 31,779 swings |
| 8% special-attack miss | 300 skill against 315 defense (level 63) | magey, quoting Blizzard (2019) | "Players have an 8% chance to miss a creature that is 3 levels above them." |
| Effective hit cap 9% | Same | magey, quoting Blizzard (2019-06-04) | "the first 1% of +hit ... ignored ... 'hit cap' is in effect 9% rather than 8%" |
| 305 skill: miss and cap 6.0%; 308: 5.7%; 315: 5.0% | Against level 63 | magey; [Marrow compendium](https://bookdown.org/marrowwar/marrow_compendium/mechanics.html) (2020-07-09) | 305 removes the suppression; 5.99% measured at +5 skill |
| 9% *miss* from 7% + (gap - 10) x 0.4% | Level 70 against 73 | [WoWWiki Miss, 2007](https://warcraft.wiki.gg/wiki/Miss?oldid=3933405) | The Burning Crusade, not Classic |

Conflict: for 301 to 304 skill the suppression differs - the Marrow compendium adds a flat
1%, magey adds (gap - 10) x 0.2%. Both give 1% at 300 skill and nothing at 305. The ruleset
uses magey's reading and lists the conflict as an assumption.

## 2. Dual wield (used)

| Value | Applies to | Source | Note |
| --- | --- | --- | --- |
| White miss = normal miss + 19%: 27% at 300 skill, 25% at 305 | White hits against level 63 | magey (2021-03-18) | |
| Dual-wield hit cap 28% at 300 skill | Same | magey | 2021 test: +27% hit left 1.01% misses (48,445 swings), +28% none (5,398) |
| 0.8 x miss + 20% (26.4% at 300) | Same | [Ask Mr. Robot forum](https://forums.askmrrobot.com/t/hit-rating-and-hit-caps-in-wow-classic/8614) (2020-02-12); Marrow (2020) | Older formula, contradicted by the 2021 test |
| The penalty does not apply to special attacks | All | [warcraft.wiki.gg Dual wield](https://warcraft.wiki.gg/wiki/Dual_wield) | |

## 3. Glancing blows

| Value | Applies to | Source |
| --- | --- | --- |
| 40% chance: 10% + (defense - min(level x 5, skill)) x 2% | Level 60 white melee against 63 | magey; [WoWWiki Weapon skill, 2006](https://warcraft.wiki.gg/wiki/Weapon_skill?oldid=2378443) |
| 35% average damage penalty at 300 skill; 15% at 305; 5% from 308 | Same | magey; Marrow |
| No glancing on ranged or special attacks | All | WoWWiki Weapon skill (2006) |

## 4. Boss avoidance (level 63)

| Value | Source |
| --- | --- |
| Dodge 6.5% (6.0% at 305 skill), front and rear | magey, quoting Blizzard |
| Parry 14%, front only | magey, quoting Blizzard |
| Block at most 5%, front only | magey; [WoWWiki Block, 2006](https://warcraft.wiki.gg/wiki/Block?oldid=2356490) |

## 5. Ranged (used)

The melee formula applies to ranged attacks: 8% miss at 300 skill against level 63 (WoWWiki
Miss 2006; Ask Mr. Robot). Hunter guides use a 9% cap, 6% with 305 skill from a racial bonus
([Warcraft Tavern](https://warcrafttavern.com/wow-classic/guides/pve-marksmanship-hunter-stat-priority)).
No direct test shows hit suppression applying to ranged attacks; the ruleset assumes it does,
as the formula is shared.

## 6. Spell hit (used)

| Value | Source | Note |
| --- | --- | --- |
| Hit 96 / 95 / 94 / 83% against targets 0 / 1 / 2 / 3 levels higher, then -11% per level | [WoWWiki Resistance, 2006-10-22](https://warcraft.wiki.gg/wiki/Resistance?oldid=288678) ("From Blizzard") | PvP at +3 is 87% |
| 99% maximum; spell hit beyond 16% is wasted against level 63 | [WoWWiki Critical strike, 2006](https://warcraft.wiki.gg/wiki/Critical_strike?oldid=2034005); [Blizzard resistances page, 2006 archive](https://web.archive.org/web/20060614091913/http://www.worldofwarcraft.com/info/basics/resistances.html) | Patch 3.0.2 later raised it to 100% |
| Spell hit reduces only the level-based miss roll, not resistance-based resists | WoWWiki Resistance | |

## 7. Melee crit against level 63

Crit is reduced 1% per level of difference (3% against 63; magey quoting Blizzard). Crit from
auras is suppressed about 1.8% more ([magey: Crit aura suppression](https://github.com/magey/classic-warrior/wiki/Crit-aura-suppression)).
The white-hit "crit cap" is 100 minus miss, dodge, parry, block and glancing.

## 8. Armor

Damage reduction = armor / (armor + 400 + 85 x attacker level), at most 75%; 5,755 against a
level 63 attacker ([WoWWiki Damage reduction, 2006](https://warcraft.wiki.gg/wiki/Damage_reduction?oldid=4431187)).
The 4.5-per-level variant is The Burning Crusade and later.

## 9. Defense and crushing blows (used: crit immunity)

| Value | Source |
| --- | --- |
| Each defense point: +0.04% to be missed, dodge, parry and block; -0.04% to be crit | [WoWWiki Defense, 2006-09-08](https://warcraft.wiki.gg/wiki/Defense?oldid=4881609) |
| Crit immunity against a raid boss at 440 defense, "a defense skill of 140 from gear" | [warcraft.wiki.gg Defense](https://warcraft.wiki.gg/wiki/Defense) |
| Derived: a level 63 boss (315 skill) crits a level 60 (300 defense) 5% + 15 x 0.04% = 5.6%; 5.6 / 0.04 = 140 points | derived |
| Crushing blows 15% against level 60 from level 63; defense above level x 5 does not reduce it | [WoWWiki Crushing blow, 2006](https://warcraft.wiki.gg/wiki/Crushing_blow?oldid=180174) |

## 10. Resistance

Average resist = resistance / (caster level x 5) x 0.75, at most 75% (315 resistance against
a level 63 caster) - WoWWiki Resistance (2006) and the Blizzard 2006 page.

## 11. Block

Block chance = 5% + items + talents + (defense - attacker skill) x 0.04%. Amount blocked =
shield block value + (Strength / 20 - 1) per [WoWWiki Block, 2006](https://warcraft.wiki.gg/wiki/Block?oldid=2356474);
a 2019 forum analysis gives (Strength - base Strength) / 20 instead.

## Gaps

- No direct test of hit suppression on ranged attacks.
- No formula for how a boss's parry changes with weapon skill.
- Level-based boss spell resistance is unconfirmed.
