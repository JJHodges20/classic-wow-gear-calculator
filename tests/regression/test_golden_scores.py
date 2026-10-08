"""Hand-calculated golden scores (data/fixtures/golden): the engine's arithmetic, pinned.

Each fixture names the ruleset version its numbers were worked out against. If the ruleset
changes, these fail until someone recalculates them by hand; never edit an expected number
just to make a test pass.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from wow_gear.models.character import CharacterContext
from wow_gear.models.item import Item
from wow_gear.profiles.loader import load_profile
from wow_gear.rulesets.loader import RulesetRegistry
from wow_gear.scoring.engine import score_item

ROOT = Path(__file__).resolve().parents[2]
GOLDEN = ROOT / "data" / "fixtures" / "golden"
PROFILES = ROOT / "data" / "fixtures" / "profiles"
RULESETS = RulesetRegistry.from_directory(ROOT / "configs" / "rulesets")
CASES = sorted(GOLDEN.glob("*.json"))
TOLERANCE = 1e-6


def _case(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))  # type: ignore[no-any-return]


def test_there_are_golden_cases() -> None:
    assert len(CASES) >= 10


@pytest.mark.parametrize("path", CASES, ids=[path.stem for path in CASES])
def test_golden_score(path: Path) -> None:
    case = _case(path)
    ruleset = RULESETS.get(case["ruleset"]["id"])
    assert ruleset.version == case["ruleset"]["version"], (
        f"{path.name} was calculated for ruleset {case['ruleset']['version']}; recalculate it "
        f"by hand for {ruleset.version}"
    )
    profile_path = next(PROFILES.glob(f"*/{case['profile']}.yaml"))
    profile = load_profile(profile_path, RULESETS)
    context = CharacterContext.model_validate(case["context"])
    item = Item.model_validate(case["item"])
    replacing = Item.model_validate(case["replacing"]) if case["replacing"] else None
    result = score_item(item, context, profile, ruleset, replacing=replacing)
    expected = case["expected"]

    assert result.score == pytest.approx(expected["score"], abs=TOLERANCE)
    assert result.eligible is expected["eligible"]
    contributions = {component.key: component.contribution for component in result.components}
    for key, value in expected["components"].items():
        assert key in contributions, f"no component {key}; have {sorted(contributions)}"
        assert contributions[key] == pytest.approx(value, abs=TOLERANCE), key
    assert sum(contributions.values()) == pytest.approx(result.score, abs=TOLERANCE)

    capped = {event.stat.value: event for event in result.capped_stats}
    assert set(capped) == set(expected["capped_stats"])
    for stat, numbers in expected["capped_stats"].items():
        for field, value in numbers.items():
            assert getattr(capped[stat], field) == pytest.approx(value, abs=TOLERANCE), (
                stat,
                field,
            )

    thresholds = {event.label: event for event in result.threshold_events}
    assert set(thresholds) == set(expected["threshold_events"])
    for label, numbers in expected["threshold_events"].items():
        for field, value in numbers.items():
            assert getattr(thresholds[label], field) == pytest.approx(value), (label, field)

    codes = {warning.code for warning in result.warnings if warning.severity == "warning"}
    codes |= {w.code for w in result.warnings if w.code == "conditional_not_counted"}
    assert codes == set(expected["warnings"])
    assert result.confidence.level == expected["confidence"]


@pytest.mark.parametrize("path", CASES, ids=[path.stem for path in CASES])
def test_golden_scores_are_reproducible(path: Path) -> None:
    case = _case(path)
    ruleset = RULESETS.get(case["ruleset"]["id"])
    profile = load_profile(next(PROFILES.glob(f"*/{case['profile']}.yaml")), RULESETS)
    context = CharacterContext.model_validate(case["context"])
    item = Item.model_validate(case["item"])
    replacing = Item.model_validate(case["replacing"]) if case["replacing"] else None
    first = score_item(item, context, profile, ruleset, replacing=replacing)
    second = score_item(item, context, profile, ruleset, replacing=replacing)
    assert first == second
    assert first.context_fingerprint == second.context_fingerprint
