"""Repositories: local persistence in SQLite through SQLAlchemy.

Owns: the item cache and repository, saved characters and gear sets, custom profiles and
stored scoring runs. Only this layer may use ``sqlalchemy``.

May import: ``wow_gear.core``, ``wow_gear.models``.
"""
