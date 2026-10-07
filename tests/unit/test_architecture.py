"""Layer boundaries, checked on the import statements of every module.

The rules are the ones in docs/ARCHITECTURE.md and in each layer's docstring. A failure here
means a module reached across a boundary: move the code to the layer that owns it rather
than widening the rule.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
PACKAGE = ROOT / "src" / "wow_gear"
APP = ROOT / "apps" / "streamlit_app"

ALL_LAYERS = {
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
}

# What each layer may import from inside wow_gear (besides itself and the package root).
ALLOWED = {
    "core": set(),
    "models": {"core"},
    "rulesets": {"core", "models"},
    "profiles": {"core", "models", "rulesets"},
    "processing": {"core", "models", "rulesets"},
    "data_sources": {"core", "models"},
    "repositories": {"core", "models"},
    "calculations": {"core", "models", "rulesets"},
    "scoring": {"core", "models", "rulesets", "profiles", "calculations"},
    "comparison": {"core", "models", "rulesets", "profiles", "calculations", "scoring"},
    "optimizer": {
        "core",
        "models",
        "rulesets",
        "profiles",
        "calculations",
        "scoring",
        "comparison",
    },
    "reporting": {"core", "models"},
    "services": ALL_LAYERS - {"services"},
    "cli": {"core", "models", "services", "reporting"},
    "app": {"models", "services", "reporting"},
}

# Third-party libraries that belong to exactly one place.
OWNED_LIBRARIES = {
    "httpx": {"data_sources"},
    "sqlalchemy": {"repositories"},
    "streamlit": {"app"},
    "plotly": {"app"},
}

# Provider-shaped data never reaches the game math.
PROVIDER_SCHEMAS = "wow_gear.models.providers"
NO_PROVIDER_SCHEMAS = {"rulesets", "profiles", "calculations", "scoring", "comparison", "optimizer"}


def _modules() -> list[tuple[str, Path]]:
    found = []
    for path in sorted(PACKAGE.rglob("*.py")):
        parts = path.relative_to(PACKAGE).with_suffix("").parts
        if parts == ("__init__",):
            continue
        layer = "cli" if parts[0] == "cli" else parts[0]
        found.append((layer, path))
    found.extend(("app", path) for path in sorted(APP.rglob("*.py")))
    return found


def _imports(path: Path) -> list[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    names: list[str] = []
    package_parts = path.relative_to(ROOT / "src").parent.parts if PACKAGE in path.parents else ()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            if node.level:
                base = list(package_parts[: len(package_parts) - node.level + 1])
                names.append(".".join([*base, node.module] if node.module else base))
            elif node.module:
                names.append(node.module)
    return names


def _violations(layer: str, names: list[str]) -> list[str]:
    violations = []
    for name in names:
        parts = name.split(".")
        if parts[0] == "wow_gear" and len(parts) > 1 and parts[1] in ALL_LAYERS:
            target = parts[1]
            if target != layer and target not in ALLOWED[layer]:
                violations.append(f"{name} ({layer} may not import {target})")
            if name.startswith(PROVIDER_SCHEMAS) and layer in NO_PROVIDER_SCHEMAS:
                violations.append(f"{name} (provider schemas stay out of {layer})")
        owners = OWNED_LIBRARIES.get(parts[0])
        if owners is not None and layer not in owners:
            violations.append(f"{name} (only {sorted(owners)} may use {parts[0]})")
    return violations


MODULES = _modules()


def test_every_module_belongs_to_a_known_layer() -> None:
    unknown = {layer for layer, _ in MODULES} - set(ALLOWED)
    assert not unknown, f"modules outside any layer: {unknown}"


def test_the_rules_catch_a_reach_across() -> None:
    assert _violations("calculations", ["wow_gear.scoring.engine"])
    assert _violations("app", ["wow_gear.calculations.caps"])
    assert _violations("app", ["wow_gear.data_sources.blizzard"])
    assert _violations("scoring", ["httpx"])
    assert _violations("services", ["streamlit"])
    assert _violations("scoring", ["wow_gear.models.providers.blizzard"])
    assert not _violations("scoring", ["wow_gear.calculations.caps", "pydantic", "math"])
    assert not _violations("app", ["wow_gear.services.calculator", "streamlit", "plotly"])


@pytest.mark.parametrize(
    ("layer", "path"), MODULES, ids=[str(p.relative_to(ROOT)) for _, p in MODULES]
)
def test_imports_respect_the_layer_rules(layer: str, path: Path) -> None:
    violations = _violations(layer, _imports(path))
    assert not violations, f"{path.relative_to(ROOT)}: " + "; ".join(violations)
