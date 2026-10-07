"""The package installs, imports and reports a version."""

from __future__ import annotations

import importlib

import pytest

import wow_gear

LAYERS = (
    "core",
    "models",
    "data_sources",
    "processing",
    "repositories",
    "rulesets",
    "profiles",
    "calculations",
    "scoring",
    "comparison",
    "optimizer",
    "services",
    "reporting",
)


def test_the_package_reports_its_version() -> None:
    assert wow_gear.__version__.count(".") >= 2


@pytest.mark.parametrize("layer", LAYERS)
def test_every_layer_imports_and_says_what_it_owns(layer: str) -> None:
    module = importlib.import_module(f"wow_gear.{layer}")
    assert module.__doc__ and "May import" in module.__doc__
