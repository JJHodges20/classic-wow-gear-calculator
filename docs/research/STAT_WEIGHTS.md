# Research: published Classic Era stat weights by spec

Gathered 2026-10-07 for the build profiles. Most current guides publish a stat priority and
conversions, not numeric weights; the numbers below come from 1.12 theorycraft (forums,
community spreadsheets, simulators) and tool presets. Every number was read on its page.
Units: physical specs in attack power (AP), casters in spell damage (SP), healers in
+healing (Heal); "hit" and "crit" mean 1%.

## Source families and how far to trust them

| Key | Source | Note |
| --- | --- | --- |
| IV | Icy Veins Classic stat pages (updated November 2024) | Priorities, conversions; few numbers |
| WH | Wowhead Classic class guides (mostly 2025-03-20) | Priorities; some numbers |
| WT | Warcraft Tavern Classic guides | Priorities and caps |
| SU | Sixty Upgrades Era EP presets, as its gear planner shows them | Undated, mostly uncredited |
| WS | wowsims/classic default EP weights | Only the defaults updated for Era are usable (rogue, cat, enhancement, elemental, warlock); others are Season of Discovery carry-overs |
| PAWN | Pawn addon's built-in Classic scales | Derived from The Burning Crusade (2.4.3) numbers; hit and crit often half the 1.12 sources' values. A fallback only |
| Forum, spreadsheet | Nostalrius, Kronos, Elysium-era posts and Google sheets (2015-2020) | 1.12 theorycraft; each states its assumptions |

Weights depend on gear and buffs: the same spec shows 20 AP per 1% crit pre-raid and 30 or
more later. Profiles state the stage they are written for.

## Warrior: Fury (dual wield)

| Stat | Value | Source |
| --- | --- | --- |
| Crit, hit, Str, Agi, weapon DPS | 20, 20, 2, 1, 14 AP | SU "Fury EP" preset |
| Crit, hit | Crit 20, hit 15 pre-raid; crit 30+ with world buffs and epics | [Twinstar forum, vido 2016](https://forum.twinstar.cz/threads/dps-warrior-stat-weights.112557/): "20 ap = 1% crit 15 ap = 1% hit ... 1% crit being equivalent to 30+ ap" |
| Hit past the special-attack cap | Under 20 AP | Nostalrius forum t=19010 (HammerDeath, 2016): "1% hit is worth less than 20 AP after the 9% is reached" |
| Conversions | 1 Str = 2 AP; 14 AP = 1 weapon DPS | [Icy Veins](https://www.icy-veins.com/wow-classic/fury-warrior-dps-pve-stat-priority) |

Priority (IV): weapon > weapon skill to 308 > hit > crit > Str/AP > Agi. Caps: 9% special
attacks (6% at 305 skill); white hits 26.4% (WH), 27% (WT), 28% (magey 2021 test).

## Warrior: Arms (two-hander)

Only PAWN (TBC-derived): Str 2.22, Agi 1.53, hit 20.8, crit 16.1, weapon DPS 11.8 AP.
Priority as Fury; the damage range matters for Mortal Strike.

## Warrior: Protection

| Stat | Value | Source |
| --- | --- | --- |
| Tank points | Stam 1.5, Agi 1.5, hit 18, crit 9, dodge 10, parry 12.5, Def 4, block 2, block value 0.33, Str 0.225, AP 0.1, weapon DPS 3.5, weapon skill 2; "50 Armor = 1 TP" | [Twinstar forum, Tank Points by Undertanker, 2016](https://forum.twinstar.cz/threads/tank-points-by-undertanker.115007/); judgment-based; "aim to keep above 400 DEF" |
| Stamina against armor | 10 Stamina about 224 armor | [Satrina 2005 (archive)](https://web.archive.org/web/20070105001726/http://evilempireguild.org/guides/acstamina.php) |

Priorities (WT): Fury/Prot - weapon skill > hit > Agi > Stam > armor > parry > dodge > crit
> Str > defense; deep Prot - weapon skill > hit > Stam > armor > parry > dodge > block value
> defense > Agi > crit > Str. WH on 440 defense: "virtually no situation in which you
actually need 440".

## Rogue: Combat

| Stat | Value | Source |
| --- | --- | --- |
| Crit, hit, Agi, Str (swords; daggers in brackets) | Pre-raid 23 [20], 18 [16], 1.9 [1.8], 1.1; BiS 29 [25], 21 [18], 2.2 [2], 1.1 | Nostalrius forum t=5412 (Oto, 2015); SU presets match |
| Agi, Str, hit, crit | 2.38, 1.26, 29.44, 17.92 | WS rogue (Era) |

Priority: 9% hit > Agi > Str/AP > crit (IV). Caps: 9% specials; white hits 27.2% (WH).

## Hunter: Marksmanship

| Stat | Value | Source |
| --- | --- | --- |
| Hit, crit, Agi | 32, 32, about 2.5 AP (about 3 buffed) | [Icy Veins](https://www.icy-veins.com/wow-classic/marksmanship-hunter-dps-pve-stat-priority) (Impakt) |
| Hit, crit, Agi | 20.98, 27.27, 2.52 (3.23 buffed) | Elysium forum topic 39599 (Guybrush, 2017) |
| Agi, crit, hit | 2.79, 28.57, 21.98 | SU |

Priority (IV): hit to 9% > crit > Agi > AP. WH: crit soft cap around 24-25%.

## Paladin: Holy

| Stat | Value | Source |
| --- | --- | --- |
| Int, crit, MP5 | 1, 12, 2 (pre-raid 1.5, 15, 4) | [Xcellers spreadsheet, 2020](https://docs.google.com/spreadsheets/d/1lSZzNVHKsvG13WRnDuqbAZyQ47ktVytB3Z2CbW7XHdA); judgment-based |
| Int, crit (no mana trouble) | 0.288, 12.8 | Vnm spreadsheet (Kronos, 2016) |

## Paladin: Protection

No 1.12 numbers found. Priority (IV): Stam > defense > Str > Agi > armor > Int; threat: hit >
spell power > Str > Int.

## Paladin: Retribution

| Stat | Value | Source |
| --- | --- | --- |
| Str, Agi, crit, hit | 2, 1, 15, 20 AP | SU |
| Str, Agi, spell power | 1 Str = 2.42 AP with Kings; spell power about 1.36 AP (one-hander) | Nostalrius forum t=13693 (DrearyYew, 2015) |

## Shaman: Restoration

| Stat | Value | Source |
| --- | --- | --- |
| MP5, Int | MP5 11, Int 2.2 Heal ("+11 healing = +5 int = +1 mp5") | [agentmerlin/vanilla-shaman-guide](https://github.com/agentmerlin/vanilla-shaman-guide) (Jelly, Kronos 2017) |
| Crit | "20+" Heal | WH (Woah) |

## Shaman: Enhancement

| Stat | Value | Source |
| --- | --- | --- |
| Str, Agi, crit, hit, weapon DPS | 2, 1.17, 23.38, 24, 14 | SU |
| Str, Agi, hit, crit, spell power | 2.29, 1.12, 9.62, 14.8, 1.15 | WS (Era) |

Caps: 9% (6% at 305 skill); 5% with Nature's Guidance (WT).

## Shaman: Elemental

| Stat | Value | Source |
| --- | --- | --- |
| Hit, crit, Int | 12.37, 7.57, 0.14 SP | WS elemental (Era, 2025-01-14) |
| Hit, crit | "20+" each | WH |

Cap: 16%, 13% with Nature's Guidance.

## Druid: Restoration

| Stat | Value | Source |
| --- | --- | --- |
| Spirit, Int, MP5, crit | BWL: 0.46, 0.3, 3, 10; Naxxramas: 0.225, 0.3, 3, 12 | Taladril spreadsheet (about 2017); judgment-based |

## Druid: Feral Cat

| Stat | Value | Source |
| --- | --- | --- |
| Str, Agi, hit, crit | 2.64, 2.76, 31.85, 30.13 AP | [Wowhead](https://www.wowhead.com/classic/guide/classes/druid/feral/dps-stat-priority-attributes-pve) (NerdEgghead, simulated, end of phase 1, Kings) |
| Str, Agi, hit, crit | 2.4, 2.43, 26.59, 28.68 | WS (Era) |

## Druid: Feral Bear

| Stat | Value | Source |
| --- | --- | --- |
| Weights with AP = 1 | Str 2.53, Agi 2.28, Stam 2.5, hit 28.67, crit 32.85, armor 0.284, dodge 0.709 (per rating-like point), Def 0.450 | NerdEgghead bear calculator v3.1 (Classic 2019-20); inputs: Stamina:AP 2.5 |
| Stam = 1 | Armor 0.23, Str 1, Agi 1.37, dodge 16.67, Def 2, AP 0.5, crit 8.97, hit 6.69 | Taladril bear list (2019) |

## Druid: Balance

Int, crit, hit 0.16, 9.60, 12.22 SP (Keftenk spreadsheet v1.5, 2020; formula-based, phase
4 gear). Cap 16%; no hit talent.

## Priest: Holy

| Stat | Value | Source |
| --- | --- | --- |
| Spirit, MP5, Int, crit (3-minute fight) | 1.09, 3.39, 1.50, 5 | [Umber spreadsheet (Priest Discord)](https://docs.google.com/spreadsheets/d/15heFli2p4yjWeOVR8VtLPM9jIKRlBwlYcjC4BH6gOzw); 1 to 10 minutes: MP5 2.65 to 4.41, Int 3.40 to 0.64 |
| Spirit, Int, MP5, crit (15-minute fight) | 0.83, 0.44, 3.5, 8 | res spreadsheet (2015); judgment-based |

## Priest: Shadow

Hit "about 13-17 +dmg" (Nostalrius forum t=38147, 2016). Cap 16%, with 10% from Shadow
Focus. Shadow Word: Pain and Mind Flay cannot crit in Classic, so crit is worth little.

## Mage: Frost

| Stat | Value | Source |
| --- | --- | --- |
| Hit, crit, 10 Int | 12.16, 7.94, 1.33 SP at 545 SP | [Zephriel spreadsheet, 2019-11-02](https://docs.google.com/spreadsheets/d/1WgQzyXeemIGIlY6GXIEZtYDa8vEFr5FxsPuaeFf9ZxA) |
| Crit, hit | 10.54, 12.97 (9.71, 14.46 at 769 SP) | Nostalrius forum t=17068 (Sheepstick, 2015) |

Cap 16%, 10% from gear with Elemental Precision. Zephriel's Intellect value equals what its
crit is worth (10 Int = 0.168% crit x 7.94 = 1.33): no mana value.

## Mage: Fire

Crit 12.8, hit 15.0 SP ([ronkuby fire mage simulation](https://github.com/ronkuby-mage/fire-mage-simulation), Classic Era mechanics, 5 mages).

## Warlock: Destruction

| Stat | Value | Source |
| --- | --- | --- |
| Int, crit, hit, MP5 | 0.36, 14.08, 12.73, 0.27 | [cphaarmeyer/warlockr](https://github.com/cphaarmeyer/warlockr) (simulation regression) |
| Hit, crit, Int, MP5 | 12.79, 7.92, 0.23, 0.14 | WS warlock (Era) |

## Warlock: Affliction

No 1.12 numbers; damage-over-time spells cannot crit, so spell power is the main stat.
