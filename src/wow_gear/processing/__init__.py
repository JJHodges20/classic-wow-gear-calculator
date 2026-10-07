"""Processing: normalization, deduplication, tooltip and stat parsing, item validation.

Owns: turning a provider payload or a manual form into the canonical Item, and checking an
item for impossible combinations. Manual and looked-up items take the same path.

May import: ``wow_gear.core``, ``wow_gear.models``, ``wow_gear.rulesets``.
"""
