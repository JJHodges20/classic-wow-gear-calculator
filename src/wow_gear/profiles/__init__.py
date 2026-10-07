"""Profiles: class, role and build priorities as versioned configuration.

Owns: loading and validating ``configs/profiles/**/*.yaml`` - stat weights, caps,
thresholds, assumptions, sources, validation status - and user customizations of them.

May import: ``wow_gear.core``, ``wow_gear.models``, ``wow_gear.rulesets``.
"""
