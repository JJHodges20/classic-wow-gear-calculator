"""The shipped ruleset loads, and a ruleset with a mistake in it is rejected with the reason."""

from __future__ import annotations

import shutil
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest
import yaml

from wow_gear.core import ConfigError, NotFoundError
from wow_gear.models.enums import ClassName, ContentMode, Race, Stat
from wow_gear.rulesets.loader import RulesetRegistry, load_ruleset

ROOT = Path(__file__).resolve().parents[2]
RULESETS = ROOT / "configs" / "rulesets"


@pytest.fixture(scope="module")
def classic_era():  # type: ignore[no-untyped-def]
    return load_ruleset(RULESETS / "classic_era.yaml")


class TestShippedRuleset:
    def test_it_loads_and_is_versioned(self, classic_era) -> None:  # type: ignore[no-untyped-def]
        assert classic_era.id == "classic_era"
        assert classic_era.version.count(".") == 2
        assert len(classic_era.content_hash) == 16

    def test_it_covers_every_class_and_race(self, classic_era) -> None:  # type: ignore[no-untyped-def]
        assert {c.name for c in classic_era.classes} == set(ClassName)
        assert {r.name for r in classic_era.races} == set(Race)

    def test_it_covers_every_content_mode(self, classic_era) -> None:  # type: ignore[no-untyped-def]
        assert {m.mode for m in classic_era.content_modes} == set(ContentMode)

    def test_every_block_cites_a_listed_source(self, classic_era) -> None:  # type: ignore[no-untyped-def]
        listed = {source.id for source in classic_era.sources}
        assert classic_era._cited() <= listed
        for source in classic_era.sources:
            assert source.url.startswith("https://")

    def test_every_allowed_stat_has_a_label_and_unit(self, classic_era) -> None:  # type: ignore[no-untyped-def]
        for stat_def in classic_era.stats:
            assert stat_def.label and stat_def.unit and stat_def.description

    def test_the_hit_and_spell_caps_are_defined(self, classic_era) -> None:  # type: ignore[no-untyped-def]
        caps = classic_era.caps
        assert caps["melee_hit"].stat == Stat.HIT
        assert caps["spell_hit"].stat == Stat.SPELL_HIT
        assert caps["crit_immunity_defense"].stat == Stat.DEFENSE

    def test_the_registry_finds_it(self) -> None:
        registry = RulesetRegistry.from_directory(RULESETS)
        assert registry.ids() == ["classic_era"]
        with pytest.raises(NotFoundError):
            registry.get("retail")


def _mutated(tmp_path: Path, change: Callable[[dict[str, Any]], None]) -> Path:
    data = yaml.safe_load((RULESETS / "classic_era.yaml").read_text(encoding="utf-8"))
    change(data)
    path = tmp_path / "classic_era.yaml"
    path.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")
    return path


class TestRejectedRulesets:
    def test_an_unknown_key(self, tmp_path: Path) -> None:
        path = _mutated(tmp_path, lambda data: data.update(hit_cap=9))
        with pytest.raises(ConfigError, match="hit_cap"):
            load_ruleset(path)

    def test_a_block_citing_an_unlisted_source(self, tmp_path: Path) -> None:
        def change(data: dict[str, Any]) -> None:
            data["phases"][0]["sources"] = ["nowhere"]

        with pytest.raises(ConfigError, match="nowhere"):
            load_ruleset(_mutated(tmp_path, change))

    def test_a_block_citing_nothing(self, tmp_path: Path) -> None:
        def change(data: dict[str, Any]) -> None:
            data["phases"][0]["sources"] = []

        with pytest.raises(ConfigError, match="sources"):
            load_ruleset(_mutated(tmp_path, change))

    def test_phases_out_of_order(self, tmp_path: Path) -> None:
        def change(data: dict[str, Any]) -> None:
            data["phases"][0]["number"] = 9

        with pytest.raises(ConfigError, match="numbered"):
            load_ruleset(_mutated(tmp_path, change))

    def test_a_conversion_between_unknown_stats(self, tmp_path: Path) -> None:
        def change(data: dict[str, Any]) -> None:
            data["conversions"]["by_class"]["warrior"]["strength->haste"] = {"per_point": 1}

        with pytest.raises(ConfigError, match="haste"):
            load_ruleset(_mutated(tmp_path, change))

    def test_a_conversion_with_both_forms(self, tmp_path: Path) -> None:
        def change(data: dict[str, Any]) -> None:
            data["conversions"]["by_class"]["warrior"]["agility->crit"] = {
                "per_point": 1,
                "points_per_unit": 20,
            }

        with pytest.raises(ConfigError, match="not both"):
            load_ruleset(_mutated(tmp_path, change))

    def test_a_cap_formula_that_does_not_exist(self, tmp_path: Path) -> None:
        def change(data: dict[str, Any]) -> None:
            data["caps"]["melee_hit"]["kind"] = "made_up"

        with pytest.raises(ConfigError, match="kind"):
            load_ruleset(_mutated(tmp_path, change))

    def test_a_class_with_an_unknown_race(self, tmp_path: Path) -> None:
        def change(data: dict[str, Any]) -> None:
            data["races"] = [race for race in data["races"] if race["name"] != "gnome"]

        with pytest.raises(ConfigError, match="gnome"):
            load_ruleset(_mutated(tmp_path, change))

    def test_an_id_that_does_not_match_the_file(self, tmp_path: Path) -> None:
        source = RULESETS / "classic_era.yaml"
        target = tmp_path / "other.yaml"
        shutil.copy(source, target)
        with pytest.raises(ConfigError, match="file name"):
            load_ruleset(target)
