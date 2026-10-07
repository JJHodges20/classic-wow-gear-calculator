# Research: Classic Era stat conversions (level 60)

Gathered 2026-10-07 for the `conversions` block of the `classic_era` ruleset. The 2006
WoWWiki pages and Wowhead's Classic stats guide were read through Wayback Machine copies
(the live pages return HTTP 402 or render by script). VMaNGOS and wowsims are code, not
Blizzard data; they are cited where no page gives a value.

## Sources

| Key | Source |
| --- | --- |
| W1 | [WoWWiki Formulas:Attack Power, 2006-06-11](https://web.archive.org/web/20061017114614/http://www.wowwiki.com:80/Formulas:Attack_Power) |
| W2 | [WoWWiki Formulas:Ranged Attack Power, 2006-06-30](https://web.archive.org/web/20061026042943/http://www.wowwiki.com:80/Formulas:Ranged_Attack_Power) |
| W3 | [WoWWiki Strength, 2006-11-13](https://web.archive.org/web/20061119183106/http://www.wowwiki.com:80/Strength) |
| W5 | [WoWWiki Formulas:Dodge, 2006-09-14](https://web.archive.org/web/20061017114322/http://www.wowwiki.com:80/Formulas:Dodge) |
| W6 | [WoWWiki Formulas:Critical hit chance, 2006-11-15](https://web.archive.org/web/20061117212018/http://www.wowwiki.com:80/Formulas%3ACritical_hit_chance) |
| W7 | [WoWWiki Formulas:Mana Regen, 2006-11-09](https://web.archive.org/web/20061127174420/http://www.wowwiki.com:80/Formulas%3AMana_Regen) |
| WH | [Wowhead: Classic WoW stats and attributes overview (patch 1.15.8)](https://web.archive.org/web/20250319092954/https://www.wowhead.com/classic/guide/classic-wow-stats-and-attributes-overview) |
| VM | [VMaNGOS](https://github.com/vmangos/core) StatSystem.cpp, Player.cpp |
| WS | [wowsims/classic](https://github.com/wowsims/classic) base_stats.go (Season of Discovery) |

## Attack power

| Class | Melee AP | Ranged AP | Source |
| --- | --- | --- | --- |
| Warrior, Paladin | 3 x level + 2 x Str - 20 | Warrior: level + Agi - 10 | W1, VM, WH |
| Shaman | 2 x level + 2 x Str - 20 | - | W1, VM |
| Rogue | 2 x level + Str + Agi - 20 | level + Agi - 10 | W1, VM, WH |
| Hunter | 2 x level + Str + Agi - 20 | 2 x level + 2 x Agi - 20 | W1, W2 |
| Mage, Priest, Warlock | Str - 10 | - | W1, VM, WH |
| Druid | 2 x Str - 20; in Cat Form + Agi (since patch 1.7.0) and the form bonus | - | W1, VM |

What an item adds per point is the coefficient: 2 attack power per Strength for warriors,
paladins, shamans and druids; 1 for the others; 1 per Agility for rogues, hunters and cat
druids; 2 ranged attack power per Agility for hunters, 1 for warriors and rogues.

Conflict: two 2006 wiki pages give warriors and rogues 2 ranged attack power per Agility;
Wowhead, VMaNGOS and warcraft.wiki.gg give 1. The ruleset uses 1.

## Crit from Agility (level 60)

| Class | Agility per 1% | Source |
| --- | --- | --- |
| Warrior, Druid, Priest, Warlock | 20 | W6, WH, VM |
| Paladin, Shaman | 20 (VM: 19.76, 19.69) | W6, WH; VM |
| Rogue | 29 | W3, quoting Blizzard |
| Hunter | 53 | W3, quoting Blizzard |

## Dodge from Agility (level 60)

Warrior, Druid, Priest, Warlock 20; Rogue 14.5; Hunter 26.5; Paladin 19.767; Shaman 19.697;
Mage 19.444 (WH table, matching VM). W5 gives 20 for Mage, Paladin and Shaman.

## Other conversions

| Conversion | Value | Source |
| --- | --- | --- |
| Armor per Agility | 2 | W3, WH, VM |
| Mana per Intellect | 15 (the first 20 give 1 each) | W3, WH; VM for the first-20 rule |
| Health per Stamina | 10 (the first 20 give 1 each); Tauren +5% maximum health | W3, WH; VM |
| Intellect per 1% spell crit | Warlock 60.6, Druid 60, Shaman 59.5, Mage 59.5, Priest 59.2, Paladin 54 | W3 (quoting Blizzard), WH |
| Block value per Strength | 1 per 20 | WH; VM subtracts 1 from the total |
| Attack power to damage | 14 attack power = 1 damage per second | W4, WH, VM |

Conflict: the paladin's Intellect per spell crit is 54 (Wowhead), 53.77 (VMaNGOS), 29.5
(Warcraft Tavern) or about 59.9 (wowsims). The ruleset uses 54 and records the conflict.

## Regeneration (for profile notes, not ruleset conversions)

Mana per 2-second tick from Spirit: 12.5 + Spirit / 4 for mages and priests; 15 + Spirit /
5 for druids, hunters, paladins and warlocks; 17 + Spirit / 5 for shamans (W7, VM; other
guides differ in the constant). Spirit regeneration stops for 5 seconds after a spell is
cast; mana per 5 from items does not (W7, WH).

## Weapon damage and normalization

Since patch 1.8.0 instant attacks (Mortal Strike, Sinister Strike, Backstab, Whirlwind and
others) add attack power at a fixed speed: 3.3 for two-handers, 1.7 for daggers, 2.4 for
other one-handers; Aimed Shot and Multi-Shot use 2.8 since 1.10.0. White hits and Heroic
Strike use the weapon's own speed. Version 1 values weapon damage per second at 14 attack
power per point (the white-hit rate) and records normalization as an assumption.

## Gaps

No page gives base melee or spell crit per class; only VMaNGOS and wowsims do, and they
differ by up to 3.5 points. Version 1 does not use base values: it scores what an item adds.
