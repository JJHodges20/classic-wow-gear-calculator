# Data Model

The canonical models live in `src/wow_gear/models` (milestone 2). This stub records the shapes
the roadmap asks for; each section is replaced by the real field list when the model exists.

## Item

Raw properties of one item, as normalized from any source: ids (ours and the provider's),
name, ruleset, phase, required level, slot, armor or weapon type, armor, primary stats,
attack and spell power, hit and crit, defensive stats, resistances, weapon damage and speed,
equip and on-use effects, set membership, and provenance (source, provider, URL, data
version, fetch time).

An item never carries a score. A score is the result of evaluating an item against a
character context and a build profile; the same item can score very differently for a
Warrior tank and a Holy Paladin.

## CharacterContext

Ruleset, phase, level, class, role, build profile, faction and race, content mode, and the
optional current stats, current gear, buff assumptions and encounter profile.

## BuildProfile

Profile id and version, class, role and specialization label, stat weights, hard caps, soft
caps, threshold rules, weapon preferences, derived-stat rules, proc and set-bonus assumptions,
default content mode, and notes, citations and validation status.

## ScoreResult

Overall score, rank and recommendation label, component breakdown, capped stats, threshold
events, warnings, assumptions, profile id and version, ruleset version, data source and item
version, confidence and validation status.

## GearSet

A character's equipped items by slot, used from milestone 9 for whole-character deltas.
