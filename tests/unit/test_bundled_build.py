"""The bundled-dataset build script's curation rules (the script itself needs a snapshot)."""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "build_bundled_dataset.py"
_spec = importlib.util.spec_from_file_location("build_bundled_dataset", SCRIPT)
assert _spec is not None and _spec.loader is not None
build = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(build)


@pytest.mark.parametrize(
    "name",
    [
        "90 Epic Frost Belt",
        "63 Green Agility Ring",
        "Monster - Sword, Long",
        "Test Plate Helm",
        "Deprecated Robe",
        "[PH] Shoulders",
    ],
)
def test_developer_items_are_dropped(name: str) -> None:
    assert build.PLACEHOLDER.search(name)


@pytest.mark.parametrize(
    "name",
    ["Band of Accuria", "The Green Tower", "Blue Dragonscale Shoulders", "Seal of the Dawn"],
)
def test_game_items_are_kept(name: str) -> None:
    assert not build.PLACEHOLDER.search(name)
