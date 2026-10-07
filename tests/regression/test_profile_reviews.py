"""Hand-reviewed comparisons each shipped profile must rank correctly (roadmap section 10:
"at least five hand-reviewed item comparisons that the profile should rank correctly").

Each file in data/fixtures/reviews/<profile id>/ holds a context, real items copied from the
bundled dataset, the expected outcome, winner, score delta, per-component differences and cap
events, the hand calculation and the reason a player would agree. The numbers were worked out
by hand: if a profile or the ruleset changes, these fail until someone reviews them again -
never edit an expected number to make a test pass.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from wow_gear.comparison.compare import compare_items
from wow_gear.data_sources.bundled import read_bundled
from wow_gear.models.character import CharacterContext
from wow_gear.models.item import Item
from wow_gear.profiles.loader import ProfileRegistry
from wow_gear.rulesets.loader import RulesetRegistry

ROOT = Path(__file__).resolve().parents[2]
REVIEWS = ROOT / "data" / "fixtures" / "reviews"
RULESETS = RulesetRegistry.from_directory(ROOT / "configs" / "rulesets")
PROFILES = ProfileRegistry.from_directory(ROOT / "configs" / "profiles", RULESETS)
CASES = sorted(REVIEWS.glob("*/*.json"))
TOLERANCE = 1e-6
MINIMUM_PER_PROFILE = 5


def _case(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))  # type: ignore[no-any-return]


def _ids(path: Path) -> str:
    return f"{path.parent.name}/{path.stem}"


def _compare(case: dict[str, Any]) -> Any:
    ruleset = RULESETS.get(case["ruleset"]["id"])
    profile = PROFILES.get(case["profile"]["id"])
    items = [Item.model_validate(record) for record in case["items"]]
    replacing = Item.model_validate(case["replacing"]) if case["replacing"] else None
    context = CharacterContext.model_validate(case["context"])
    return compare_items(items, context, profile, ruleset, replacing=replacing)


@pytest.mark.parametrize("profile_id", [profile.id for profile in PROFILES])
def test_every_shipped_profile_has_its_reviews(profile_id: str) -> None:
    count = len(list((REVIEWS / profile_id).glob("*.json")))
    assert count >= MINIMUM_PER_PROFILE, f"{profile_id} has {count} reviewed comparisons"


@pytest.mark.parametrize("path", CASES, ids=[_ids(path) for path in CASES])
def test_the_profile_ranks_the_review_as_expected(path: Path) -> None:
    case = _case(path)
    ruleset = RULESETS.get(case["ruleset"]["id"])
    profile = PROFILES.get(case["profile"]["id"])
    assert path.parent.name == profile.id
    for name, model, stated in (
        ("ruleset", ruleset, case["ruleset"]["version"]),
        ("profile", profile, case["profile"]["version"]),
    ):
        assert model.version == stated, (
            f"{path.name} was reviewed against {name} {stated}; review it again by hand for "
            f"{model.version}"
        )
    result = _compare(case)
    expected = case["expected"]

    assert result.outcome == expected["outcome"]
    assert result.winner_id == expected["winner"]
    assert (result.first_id, result.second_id) == (expected["first"], expected["second"])
    assert result.score_delta == pytest.approx(expected["score_delta"], abs=TOLERANCE)
    scores = {r.item_id: r.score for r in result.results}
    assert scores == pytest.approx(expected["scores"], abs=TOLERANCE)

    deltas = {line.key: line.delta for line in result.lines}
    assert set(deltas) == set(expected["component_deltas"])
    assert deltas == pytest.approx(expected["component_deltas"], abs=TOLERANCE)
    assert sum(deltas.values()) == pytest.approx(result.score_delta, abs=TOLERANCE)

    capped = {
        (r.item_id, event.stat.value): event for r in result.results for event in r.capped_stats
    }
    wanted = {
        (item_id, stat): numbers
        for item_id, by_stat in expected["capped_stats"].items()
        for stat, numbers in by_stat.items()
    }
    assert set(capped) == set(wanted)
    for key, numbers in wanted.items():
        for field, value in numbers.items():
            assert getattr(capped[key], field) == pytest.approx(value, abs=TOLERANCE), (key, field)

    unusable = {r.item_id: list(r.ineligibility) for r in result.results if not r.eligible}
    assert unusable == expected["not_usable"]
    assert result.confidence.level == expected["confidence"]


@pytest.mark.parametrize("path", CASES, ids=[_ids(path) for path in CASES])
def test_reviews_are_reproducible_in_any_order(path: Path) -> None:
    case = _case(path)
    first = _compare(case)
    assert _compare(case) == first
    reversed_case = {**case, "items": list(reversed(case["items"]))}
    again = _compare(reversed_case)
    assert [r.item_id for r in again.results] == [r.item_id for r in first.results]
    assert again.fingerprint == first.fingerprint


def test_reviewed_items_still_match_the_bundled_dataset() -> None:
    """A rebuilt dataset that changes a reviewed item means reviewing that comparison again.

    Reads the committed bundled dataset (read-only).
    """
    bundled = {record["id"]: record for record in read_bundled(ROOT / "data" / "bundled").items}
    stale = []
    for path in CASES:
        case = _case(path)
        for record in [*case["items"], *([case["replacing"]] if case["replacing"] else [])]:
            current = bundled.get(record["id"])
            reviewed = {key: value for key, value in record.items() if key != "provenance"}
            if current is None:
                stale.append(f"{_ids(path)}: {record['name']} is no longer in the dataset")
            elif {key: value for key, value in current.items() if key != "provenance"} != reviewed:
                stale.append(f"{_ids(path)}: {record['name']} changed in the dataset")
    assert not stale, "review these comparisons again by hand:\n" + "\n".join(stale)
