"""Scoring engine behavior the golden fixtures do not pin: inputs, traceability, confidence."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from wow_gear.core import DataValidationError
from wow_gear.models.character import CharacterContext
from wow_gear.models.enums import ClassName, ContentMode, ItemSlot, Role, Stat, ValidationStatus
from wow_gear.models.item import EffectTrigger, Item, ItemEffect, Provenance
from wow_gear.models.score import ComponentKind
from wow_gear.profiles.loader import load_profile
from wow_gear.rulesets.loader import RulesetRegistry
from wow_gear.scoring.engine import ENGINE_VERSION, score_item

ROOT = Path(__file__).resolve().parents[2]
RULESETS = RulesetRegistry.from_directory(ROOT / "configs" / "rulesets")
RULESET = RULESETS.get("classic_era")
FURY = load_profile(ROOT / "data/fixtures/profiles/warrior/fixture_warrior_fury.yaml", RULESETS)
FIXTURE = Provenance(provider="fixture", source="Test", data_version="t-1", custom=True)


def context(**changes: Any) -> CharacterContext:
    data: dict[str, Any] = {
        "ruleset": "classic_era",
        "phase": 6,
        "level": 60,
        "class_name": ClassName.WARRIOR,
        "role": Role.MELEE_DPS,
        "profile_id": FURY.id,
        "content_mode": ContentMode.RAID,
        "current_stats": {Stat.HIT: 5},
    }
    data.update(changes)
    return CharacterContext(**data)


def item(**changes: Any) -> Item:
    data: dict[str, Any] = {
        "id": "custom:ring",
        "name": "Test Ring",
        "ruleset": "classic_era",
        "slot": ItemSlot.FINGER,
        "stats": {Stat.STRENGTH: 10},
        "provenance": FIXTURE,
    }
    data.update(changes)
    return Item(**data)


class TestInputs:
    def test_the_context_must_name_the_profile(self) -> None:
        with pytest.raises(DataValidationError, match="names profile"):
            score_item(item(), context(profile_id="other"), FURY, RULESET)

    def test_the_profile_must_fit_the_class_and_role(self) -> None:
        mage = context(class_name=ClassName.MAGE, role=Role.CASTER_DPS)
        with pytest.raises(DataValidationError, match="profile is for a warrior"):
            score_item(item(), mage, FURY, RULESET)

    def test_rulesets_must_agree(self) -> None:
        with pytest.raises(DataValidationError, match="ruleset mismatch"):
            score_item(item(ruleset="season_of_discovery"), context(), FURY, RULESET)


class TestTraceability:
    def test_the_result_names_every_version(self) -> None:
        result = score_item(item(), context(), FURY, RULESET)
        assert (result.profile_id, result.profile_version) == (FURY.id, FURY.version)
        assert result.profile_hash == FURY.content_hash
        assert (result.ruleset_id, result.ruleset_version) == ("classic_era", RULESET.version)
        assert result.engine_version.startswith(ENGINE_VERSION)
        assert result.item_provider == "fixture" and result.item_data_version == "t-1"

    def test_the_fingerprint_follows_every_input(self) -> None:
        base = score_item(item(), context(), FURY, RULESET).context_fingerprint
        assert score_item(item(), context(), FURY, RULESET).context_fingerprint == base
        assert score_item(item(), context(level=59), FURY, RULESET).context_fingerprint != base
        changed = item(stats={Stat.STRENGTH: 11})
        assert score_item(changed, context(), FURY, RULESET).context_fingerprint != base
        replaced = score_item(item(), context(), FURY, RULESET, replacing=item(id="custom:old"))
        assert replaced.context_fingerprint != base

    def test_the_assumptions_say_what_the_target_and_caps_were(self) -> None:
        result = score_item(item(stats={Stat.HIT: 1}), context(), FURY, RULESET)
        assert result.assumptions[0] == "Target: level 63 (Raid)."
        assert any(line.startswith("Hit cap:") for line in result.assumptions)


class TestComponents:
    def test_procs_and_set_bonuses_are_listed_with_no_value(self) -> None:
        proc = ItemEffect(trigger=EffectTrigger.CHANCE_ON_HIT, description="Chance on hit: zap.")
        use = ItemEffect(trigger=EffectTrigger.USE, description="Use: shout.")
        result = score_item(
            item(equip_effects=(proc,), on_use_effects=(use,), set_id="209"),
            context(),
            FURY,
            RULESET,
        )
        kinds = [c.kind for c in result.components if c.contribution == 0]
        assert kinds.count(ComponentKind.PROC) == 2 and ComponentKind.SET_BONUS in kinds
        codes = {w.code for w in result.warnings}
        assert {"unscored_effects", "set_bonus_not_scored"} <= codes

    def test_a_converted_stat_is_not_also_listed_as_unvalued(self) -> None:
        result = score_item(
            item(stats={Stat.STRENGTH: 10, Stat.STAMINA: 5}), context(), FURY, RULESET
        )
        keys = {c.key for c in result.components}
        assert "derived:strength->attack_power" in keys and "stat:strength" not in keys
        stamina = result.component("stat:stamina")
        assert stamina is not None and stamina.note == "Not valued by this profile"

    def test_components_are_ordered_by_size(self) -> None:
        result = score_item(item(stats={Stat.STRENGTH: 10, Stat.CRIT: 1}), context(), FURY, RULESET)
        sizes = [abs(c.contribution) for c in result.components]
        assert sizes == sorted(sizes, reverse=True)


class TestConfidence:
    def test_a_validated_profile_with_current_gear_is_high(self) -> None:
        validated = FURY.model_copy(update={"validation_status": ValidationStatus.VALIDATED})
        result = score_item(item(), context(), validated, RULESET)
        assert result.confidence.level == "high" and result.confidence.reasons == ()

    def test_far_from_the_profile_level_lowers_it(self) -> None:
        result = score_item(item(), context(level=40), FURY, RULESET)
        assert result.confidence.level == "low"
        assert {"profile_level", "conversions_at_other_level"} <= {w.code for w in result.warnings}


class TestWeaponSkill:
    TANK = load_profile(ROOT / "configs/profiles/warrior/warrior_tank_deep_prot.yaml", RULESETS)

    def tank(self, **changes: Any) -> CharacterContext:
        data: dict[str, Any] = {
            "class_name": ClassName.WARRIOR,
            "role": Role.TANK,
            "profile_id": self.TANK.id,
        }
        data.update(changes)
        return context(**data)

    def test_skill_counts_only_with_its_weapon(self) -> None:
        gloves = item(slot=ItemSlot.HANDS, stats={Stat.SWORD_SKILL: 7, Stat.AXE_SKILL: 7})
        with_sword = score_item(gloves, self.tank(main_hand_type="sword"), self.TANK, RULESET)
        assert with_sword.score == 14.0
        with_mace = score_item(gloves, self.tank(main_hand_type="mace"), self.TANK, RULESET)
        assert with_mace.score == 0.0
        notes = [c.note for c in with_mace.components if c.key.startswith("inactive")]
        assert notes and "you fight with maces" in notes[0]
        unset = score_item(gloves, self.tank(), self.TANK, RULESET)
        assert unset.score == 0.0 and any("not set" in (c.note or "") for c in unset.components)
