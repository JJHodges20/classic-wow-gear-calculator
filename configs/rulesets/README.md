# Rulesets

One YAML file per ruleset (for example `classic_era.yaml`): the game-version mechanics the
calculator uses - phases, level range, classes and races, item eligibility, the stats a
ruleset allows, and formula parameters such as stat conversions and cap inputs.

Every value cites the source it was taken from. A ruleset is versioned; a change to any value
bumps its version so that stored results stay reproducible. The schema is
`src/wow_gear/models/ruleset.py`; `docs/DATA_MODEL.md` describes it.

Two consequences of the cap formulas are assumptions rather than sourced statements, and
the calculator labels them so:

- **Talent hit covers the suppressed hit first.** Against a target whose defense exceeds
  the attacker's skill by more than 10, the first part of the hit bonus is ignored. The
  sources state it for the total bonus, so hit from talents (`reduced_by` in a profile)
  fills that part before gear does: a rogue with Precision needs no gear hit to cover it.
- **Skill above the target's defense keeps the 5% base miss.** A gap below zero is held at
  zero; no source used here gives the miss chance for skill above the target's defense.
