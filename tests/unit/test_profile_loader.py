"""Profiles load only when their ruleset supports everything they name."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
import yaml

from wow_gear.core import ConfigError, NotFoundError
from wow_gear.models.enums import ClassName, Role
from wow_gear.profiles.loader import ProfileRegistry, load_profile
from wow_gear.rulesets.loader import RulesetRegistry

ROOT = Path(__file__).resolve().parents[2]
RULESETS = RulesetRegistry.from_directory(ROOT / "configs" / "rulesets")


def base_profile(**changes: Any) -> dict[str, Any]:
    data: dict[str, Any] = {
        "id": "warrior_test",
        "version": "1.0.0",
        "label": "Test",
        "class_name": "warrior",
        "role": "melee_dps",
        "specialization": "Fury",
        "summary": "A profile for loader tests.",
        "ruleset": "classic_era",
        "target_level": 60,
        "default_content_mode": "raid_pve",
        "score_unit": "attack power equivalents",
        "validation_status": "draft",
        "stat_weights": [
            {"stat": "attack_power", "weight": 1.0, "basis": "derived", "note": "The unit."},
            {"stat": "hit", "weight": 20.0, "basis": "assumption"},
            {"stat": "crit", "weight": 20.0, "basis": "assumption"},
        ],
        "derived_stats": [
            {"source": "strength", "target": "attack_power"},
            {"source": "agility", "target": "crit"},
        ],
        "hard_caps": [{"stat": "hit", "cap": {"ruleset_cap": "melee_hit"}}],
    }
    data.update(changes)
    return data


def write(tmp_path: Path, data: dict[str, Any], folder: str | None = None) -> Path:
    directory = tmp_path / (folder or data["class_name"])
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"{data['id']}.yaml"
    path.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")
    return path


def test_a_valid_profile_loads(tmp_path: Path) -> None:
    profile = load_profile(write(tmp_path, base_profile()), RULESETS)
    assert profile.id == "warrior_test" and profile.weight_of("hit") == 20.0  # type: ignore[arg-type]


@pytest.mark.parametrize(
    ("changes", "message"),
    [
        ({"role": "healer"}, "no healer role"),
        ({"target_level": 70}, "outside the ruleset"),
        ({"target_phase": 9}, "not a ruleset phase"),
        (
            {"derived_stats": [{"source": "intellect", "target": "spell_crit"}]},
            "no value for warrior",
        ),
        (
            {"hard_caps": [{"stat": "hit", "cap": {"ruleset_cap": "haste_cap"}}]},
            "not in the ruleset",
        ),
        (
            {"hard_caps": [{"stat": "hit", "cap": {"ruleset_cap": "spell_hit"}}]},
            "a cap on spell_hit",
        ),
        ({"ruleset": "retail"}, "no ruleset"),
    ],
)
def test_a_profile_the_ruleset_does_not_support(
    tmp_path: Path, changes: dict[str, Any], message: str
) -> None:
    with pytest.raises(ConfigError, match=message):
        load_profile(write(tmp_path, base_profile(**changes)), RULESETS)


def test_the_file_name_and_folder_must_match(tmp_path: Path) -> None:
    path = write(tmp_path, base_profile())
    renamed = path.with_name("other.yaml")
    path.rename(renamed)
    with pytest.raises(ConfigError, match="file name"):
        load_profile(renamed, RULESETS)
    with pytest.raises(ConfigError, match="folder"):
        load_profile(write(tmp_path, base_profile(), folder="mage"), RULESETS)


def test_schema_errors_name_the_file(tmp_path: Path) -> None:
    path = write(tmp_path, base_profile(stat_weights=[]))
    with pytest.raises(ConfigError, match="not a valid build profile"):
        load_profile(path, RULESETS)


def test_the_registry_groups_by_class_and_role(tmp_path: Path) -> None:
    write(tmp_path, base_profile())
    write(tmp_path, base_profile(id="warrior_test_tank", role="tank", hard_caps=[]))
    registry = ProfileRegistry.from_directory(tmp_path, RULESETS)
    assert len(registry) == 2
    assert registry.classes("classic_era") == [ClassName.WARRIOR]
    assert registry.roles("classic_era", ClassName.WARRIOR) == [Role.TANK, Role.MELEE_DPS]
    assert [p.id for p in registry.profiles("classic_era", ClassName.WARRIOR, Role.TANK)] == [
        "warrior_test_tank"
    ]
    with pytest.raises(NotFoundError):
        registry.get("nope")


def test_duplicate_ids_are_rejected(tmp_path: Path) -> None:
    profile = load_profile(write(tmp_path, base_profile()), RULESETS)
    with pytest.raises(ConfigError, match="share the id"):
        ProfileRegistry([profile, profile])
