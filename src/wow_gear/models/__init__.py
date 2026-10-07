"""Models: the canonical data shapes every layer exchanges.

Owns: Item, CharacterContext, BuildProfile, Ruleset, ScoreResult, GearSet and the provider
response schemas (kept in their own module so calculation code never sees them).

May import: ``wow_gear.core``. Models hold data and validate it; they compute no game math.
"""
