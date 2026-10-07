"""Every shipped profile meets the roadmap's profile checklist (section 10)."""

from __future__ import annotations

from pathlib import Path

import pytest

from wow_gear.models.enums import ClassName, Role
from wow_gear.models.profile import BuildProfile, WeightBasis
from wow_gear.profiles.loader import ProfileRegistry
from wow_gear.rulesets.loader import RulesetRegistry

ROOT = Path(__file__).resolve().parents[2]
RULESETS = RulesetRegistry.from_directory(ROOT / "configs" / "rulesets")
PROFILES = ProfileRegistry.from_directory(ROOT / "configs" / "profiles", RULESETS)
ALL = list(PROFILES)


def test_the_four_representative_roles_are_covered() -> None:
    covered = {(p.class_name, p.role) for p in ALL}
    assert {
        (ClassName.WARRIOR, Role.MELEE_DPS),
        (ClassName.MAGE, Role.CASTER_DPS),
        (ClassName.PRIEST, Role.HEALER),
        (ClassName.WARRIOR, Role.TANK),
    } <= covered


@pytest.mark.parametrize("profile", ALL, ids=[p.id for p in ALL])
def test_a_profile_states_its_target_and_status(profile: BuildProfile) -> None:
    assert profile.ruleset and profile.target_level and profile.default_content_mode
    assert profile.label and profile.summary and profile.score_unit
    assert profile.validation_status is not None


@pytest.mark.parametrize("profile", ALL, ids=[p.id for p in ALL])
def test_every_valuation_cites_or_says_it_is_an_assumption(profile: BuildProfile) -> None:
    for weight in profile.stat_weights:
        if weight.basis in (WeightBasis.SOURCED, WeightBasis.MECHANIC):
            assert weight.sources, weight.stat
        else:
            assert weight.note or weight.basis == WeightBasis.ASSUMPTION, weight.stat
    assert profile.sources, "a profile lists its sources"
    for source in profile.sources:
        assert source.url.startswith("https://")


@pytest.mark.parametrize("profile", ALL, ids=[p.id for p in ALL])
def test_proc_and_set_bonus_handling_is_stated(profile: BuildProfile) -> None:
    assert profile.proc_assumptions, "say how procs are handled"
    assert profile.set_bonus_rules, "say how set bonuses are handled"
    assert profile.assumptions, "list the assumptions a reader needs"


@pytest.mark.parametrize("profile", ALL, ids=[p.id for p in ALL])
def test_a_capped_stat_has_a_weight(profile: BuildProfile) -> None:
    for cap in profile.hard_caps:
        assert profile.weight_of(cap.stat) > 0
