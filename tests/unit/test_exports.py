"""Exports: JSON that reads back, CSV a spreadsheet opens safely, a self-contained report."""

from __future__ import annotations

import csv
import io
import re
from pathlib import Path
from typing import Any

from wow_gear.comparison.compare import compare_items
from wow_gear.comparison.gear import analyse_gear, replacement
from wow_gear.models.character import CharacterContext
from wow_gear.models.comparison import ComparisonResult
from wow_gear.models.enums import ClassName, ContentMode, EquipmentSlot, ItemSlot, Role, Stat
from wow_gear.models.gear import GearAnalysis, GearSet, SavedCharacter
from wow_gear.models.item import Item, Provenance
from wow_gear.processing.gear_files import gear_from_rows
from wow_gear.profiles.loader import load_profile
from wow_gear.reporting.export import (
    analysis_json,
    character_json,
    comparison_csv,
    comparison_html,
    comparison_json,
    components_csv,
    gear_csv,
    gear_html,
)
from wow_gear.reporting.text import gear_text
from wow_gear.rulesets.loader import RulesetRegistry

ROOT = Path(__file__).resolve().parents[2]
RULESETS = RulesetRegistry.from_directory(ROOT / "configs" / "rulesets")
RULESET = RULESETS.get("classic_era")
FURY = load_profile(ROOT / "data/fixtures/profiles/warrior/fixture_warrior_fury.yaml", RULESETS)
FIXTURE = Provenance(provider="fixture", source="Test", data_version="t-1", custom=True)
CONTEXT = CharacterContext(
    ruleset="classic_era",
    phase=6,
    level=60,
    class_name=ClassName.WARRIOR,
    role=Role.MELEE_DPS,
    profile_id=FURY.id,
    content_mode=ContentMode.RAID,
    current_stats={Stat.HIT: 5},
)
HOSTILE = '<script>alert("x")</script> & Co'


def ring(name: str, **stats: float) -> Item:
    return Item(
        id=f"custom:{re.sub(r'[^a-z0-9]+', '-', name.lower()).strip('-')}",
        name=name,
        ruleset="classic_era",
        slot=ItemSlot.FINGER,
        stats={Stat(stat): value for stat, value in stats.items()},
        provenance=FIXTURE,
    )


def comparison() -> ComparisonResult:
    items = [
        ring("Strong", strength=10, hit=2),
        ring(HOSTILE, crit=1),
        ring("=SUM(A1:A2)", stamina=5),
    ]
    return compare_items(items, CONTEXT, FURY, RULESET)


def character_and_analysis() -> tuple[SavedCharacter, GearAnalysis, Any]:
    gear = {
        EquipmentSlot.FINGER_1: ring(HOSTILE, hit=4),
        EquipmentSlot.FINGER_2: ring("Band", crit=1),
    }
    character = SavedCharacter(
        id="grom",
        name=HOSTILE,
        ruleset="classic_era",
        class_name=ClassName.WARRIOR,
        level=60,
        phase=6,
        profile_id=FURY.id,
        gear=GearSet(items={slot: item.id for slot, item in gear.items()}),
    )
    context = CONTEXT.model_copy(update={"current_stats": None})
    analysis = analyse_gear(gear, context, FURY, RULESET)
    tried = replacement(
        gear, EquipmentSlot.FINGER_2, ring("Better", crit=2), context, FURY, RULESET
    )
    return character, analysis, tried


def rows(text: str) -> list[dict[str, str]]:
    return list(csv.DictReader(io.StringIO(text)))


def self_contained(html: str) -> None:
    """Nothing to run and nothing loaded from elsewhere: a page safe to open and share."""
    lowered = html.lower()
    for forbidden in ("<script", "src=", "@import", "url(", "<link", "<iframe", "javascript:"):
        assert forbidden not in lowered, forbidden


class TestComparisons:
    def test_the_json_is_the_result_and_reads_back(self) -> None:
        result = comparison()
        assert ComparisonResult.model_validate_json(comparison_json(result)) == result

    def test_the_ranking_csv_has_a_row_per_item_in_rank_order(self) -> None:
        result = comparison()
        table = rows(comparison_csv(result))
        # Strong: 10 Strength (20) and 2% hit from 5% (20); the crit ring 20; stamina nothing.
        assert [row["item_name"] for row in table] == ["Strong", HOSTILE, "'=SUM(A1:A2)"]
        assert [row["score"] for row in table] == ["40.00", "20.00", "0.00"]
        assert table[0]["status"] == "Recommended under this profile"
        assert {row["fingerprint"] for row in table} == {result.fingerprint}

    def test_text_that_a_spreadsheet_would_run_is_neutralised(self) -> None:
        text = comparison_csv(comparison())
        assert "'=SUM(A1:A2)" in text
        assert ",=SUM" not in text

    def test_the_components_csv_lists_every_component_of_every_item(self) -> None:
        result = comparison()
        table = rows(components_csv(result))
        assert len(table) == sum(len(r.components) for r in result.results)
        strong = [row for row in table if row["item_name"] == "Strong"]
        assert {row["component"] for row in strong} >= {"Strength into attack power", "Hit"}

    def test_the_report_is_escaped_and_self_contained(self) -> None:
        html = comparison_html(comparison(), CONTEXT)
        self_contained(html)
        assert "&lt;script&gt;alert(&quot;x&quot;)&lt;/script&gt; &amp; Co" in html
        assert "Level 60, phase 6, Raid PvE, current gear totals given" in html
        assert "Recommended under the named build profile" in html


class TestGear:
    def test_the_character_json_reads_back(self) -> None:
        character, analysis, _ = character_and_analysis()
        assert SavedCharacter.model_validate_json(character_json(character)) == character
        assert GearAnalysis.model_validate_json(analysis_json(analysis)) == analysis

    def test_the_gear_csv_lists_every_slot_and_imports_back(self) -> None:
        character, analysis, _ = character_and_analysis()
        text = gear_csv(character, analysis)
        table = rows(text)
        assert len(table) == len(EquipmentSlot)
        assert list(table[0]) == [
            "slot",
            "item_id",
            "item_name",
            "item_level",
            "value_fixture_points",
        ]
        assert gear_from_rows(table, "classic_era", "Raid").items == character.gear.items

    def test_the_gear_report_is_escaped_and_self_contained(self) -> None:
        character, analysis, tried = character_and_analysis()
        html = gear_html(character, analysis, RULESET, tried)
        self_contained(html)
        assert "<script>" not in html
        assert "&lt;script&gt;" in html
        assert "Trying Better" in html
        assert 'Hit</td><td class="num">4%</td>' in html

    def test_the_gear_text_names_the_profile_value_and_replacement(self) -> None:
        character, analysis, tried = character_and_analysis()
        text = gear_text(character, analysis, tried)
        assert f"This gear is worth {analysis.score:.1f} fixture points." in text
        assert "Trying Better in the finger 2 slot (replacing Band): +20.0 fixture points" in text
        assert analysis.fingerprint in text
