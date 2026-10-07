"""Data sources: clients that fetch item data and readers for bundled or imported files.

Owns: provider adapters (bundled dataset reader, Blizzard and Warcraft Logs clients, file
import readers). An adapter fetches and returns provider-shaped payloads; it never scores.

May import: ``wow_gear.core``, ``wow_gear.models``. Only this layer may use ``httpx``.
"""
