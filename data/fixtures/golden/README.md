# Golden scoring fixtures

Each file is one hand-calculated scoring case (roadmap section 11): a context, a fixture
profile, an item (and, when replacing, the item it replaces), the expected score and the
expected contribution of each component, with the hand calculation written out in
`hand_calculation`. `tests/regression/test_golden_scores.py` runs every file.

The fixture profiles (`data/fixtures/profiles/`) have round weights chosen for arithmetic,
not play; the stat conversions and cap formulas are the real `classic_era` ruleset's. Each
file names the ruleset version it was calculated against, and the test refuses to compare
against another version: a ruleset change means recalculating these by hand, not editing
the expected numbers until the test passes.

Ruleset values used (classic_era 1.0.0, level 60, raid target level 63):

- Warrior: 2 attack power per Strength; 20 Agility per 1% crit and per 1% dodge; 20
  Strength per block value.
- Mage: 59.5 Intellect per 1% spell crit.
- Melee hit cap at 300 weapon skill: 9%, of which the first 1% is suppressed; dual-wield
  cap 28%. Spell hit cap 16%, 10% with 6% from talents. Crit immunity: 140 defense from
  gear.
