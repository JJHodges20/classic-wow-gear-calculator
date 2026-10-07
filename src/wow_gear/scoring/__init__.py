"""Scoring: turns an item's contribution into a build-specific, explainable value.

Owns: the weighted model, cap and threshold application, and the ScoreResult with its
component breakdown, warnings and assumptions.

May import: ``wow_gear.core``, ``wow_gear.models``, ``wow_gear.rulesets``,
``wow_gear.profiles``, ``wow_gear.calculations``.
"""
