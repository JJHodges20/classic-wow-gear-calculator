# Rulesets

One YAML file per ruleset (for example `classic_era.yaml`): the game-version mechanics the
calculator uses - phases, level range, classes and races, item eligibility, the stats a
ruleset allows, and formula parameters such as stat conversions and cap inputs.

Every value cites the source it was taken from. A ruleset is versioned; a change to any value
bumps its version so that stored results stay reproducible. The schema arrives in milestone 2.
