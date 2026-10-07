"""Custom build profiles (saved, versioned, used by the calculator), profile caps for the
Profiles page, browsing the item data, and refreshing the cache."""

from __future__ import annotations

from collections.abc import Callable
from datetime import timedelta

import pytest

from wow_gear.core.errors import DataValidationError
from wow_gear.models.enums import ClassName, ItemSlot, Role, Stat, ValidationStatus
from wow_gear.models.profile import WeightBasis
from wow_gear.repositories.database import ItemRow, utc_now
from wow_gear.repositories.items import ItemFilters
from wow_gear.services.workspace import Workspace

Opener = Callable[..., Workspace]
FURY = "warrior_dps_fury"
LIONHEART, MASK = "classic_era:12640", "classic_era:13404"


def fury_weights(workspace: Workspace, **changes: float) -> dict[Stat, float]:
    weights = {w.stat: w.weight for w in workspace.profile_service.get(FURY).stat_weights}
    weights.update({Stat(stat): value for stat, value in changes.items()})
    return weights


class TestCustomProfiles:
    def test_saving_a_copy_with_other_weights(self, open_workspace: Opener) -> None:
        workspace = open_workspace()
        service = workspace.profile_service
        profile = service.save_custom(FURY, "My Fury", fury_weights(workspace, crit=30))
        assert (profile.id, profile.version) == ("custom_my_fury", "1.0.0")
        assert profile.validation_status == ValidationStatus.EXPERIMENTAL
        assert profile.notes == "Based on warrior_dps_fury 1.0.0."
        crit = next(w for w in profile.stat_weights if w.stat == Stat.CRIT)
        assert (crit.weight, crit.basis) == (30.0, WeightBasis.ASSUMPTION)
        assert crit.note == "Set by you; Fury (dual wield) 1.0.0 has 20."
        hit = next(w for w in profile.stat_weights if w.stat == Stat.HIT)
        assert hit.basis == WeightBasis.SOURCED and hit.sources  # unchanged weights keep sources
        saved = workspace.settings.user_dir / "profiles" / "warrior" / "custom_my_fury.yaml"
        assert saved.is_file()
        assert service.history("custom_my_fury") == ["1.0.0"]

    def test_the_calculator_offers_and_uses_it(self, open_workspace: Opener) -> None:
        workspace = open_workspace()
        workspace.profile_service.save_custom(FURY, "My Fury", fury_weights(workspace, crit=30))
        calculator = workspace.calculator
        offered = calculator.profiles("classic_era", ClassName.WARRIOR, Role.MELEE_DPS)
        assert [p.id for p in offered] == ["custom_my_fury", "warrior_dps_arms", FURY]
        context = calculator.context("custom_my_fury", current_stats={Stat.HIT: 5})
        result = calculator.compare_ids([LIONHEART, MASK], context)
        # Lionheart Helm: 36 from Strength, 2% crit x 30, 2% hit x 20 = 136; the mask 30 + 40.
        assert result.result(LIONHEART).score == pytest.approx(136.0)
        assert result.score_delta == pytest.approx(66.0)
        assert result.result(LIONHEART).profile_id == "custom_my_fury"

    def test_saving_again_makes_a_new_version_and_keeps_the_old(
        self, open_workspace: Opener
    ) -> None:
        workspace = open_workspace()
        service = workspace.profile_service
        service.save_custom(FURY, "My Fury", fury_weights(workspace, crit=30))
        again = service.save_custom("custom_my_fury", "My Fury", fury_weights(workspace, crit=25))
        assert again.version == "1.0.1"
        assert service.history("custom_my_fury") == ["1.0.0", "1.0.1"]
        assert next(w for w in again.stat_weights if w.stat == Stat.CRIT).weight == 25.0

    def test_it_comes_back_when_the_workspace_reopens(self, open_workspace: Opener) -> None:
        first = open_workspace()
        first.profile_service.save_custom(FURY, "My Fury", fury_weights(first))
        reopened = open_workspace()
        assert reopened.profile_service.get("custom_my_fury").label == "My Fury"

    def test_a_broken_file_is_reported_not_fatal(self, open_workspace: Opener) -> None:
        workspace = open_workspace()
        folder = workspace.settings.user_dir / "profiles" / "warrior"
        folder.mkdir(parents=True)
        (folder / "custom_broken.yaml").write_text("id: custom_broken\n", encoding="utf-8")
        reopened = open_workspace()
        assert any("custom_broken" in problem for problem in reopened.profile_service.problems)

    @pytest.mark.parametrize(
        ("label", "changes", "reason"),
        [
            ("", {}, "needs a name"),
            ("!!!", {}, "letters or digits"),
            ("No Hit", {"hit": None}, "a cap on hit, which the profile does not value"),
        ],
    )
    def test_an_invalid_profile_is_refused(
        self, open_workspace: Opener, label: str, changes: dict[str, None], reason: str
    ) -> None:
        workspace = open_workspace()
        weights = fury_weights(workspace)
        for stat in changes:
            weights.pop(Stat(stat))
        with pytest.raises(DataValidationError, match=reason):
            workspace.profile_service.save_custom(FURY, label, weights)

    def test_only_custom_profiles_can_be_deleted(self, open_workspace: Opener) -> None:
        workspace = open_workspace()
        service = workspace.profile_service
        service.save_custom(FURY, "My Fury", fury_weights(workspace))
        with pytest.raises(DataValidationError, match="only custom"):
            service.delete_custom(FURY)
        service.delete_custom("custom_my_fury")
        assert "custom_my_fury" not in [p.id for p in service.all()]
        assert service.history("custom_my_fury") == ["1.0.0"]


class TestProfileCaps:
    def test_caps_are_shown_as_numbers_for_the_profile_context(
        self, open_workspace: Opener
    ) -> None:
        service = open_workspace().profile_service
        (fury,) = service.caps(FURY)
        assert (fury.stat, fury.kind, fury.value) == (Stat.HIT, "soft cap", 9.0)
        assert "counts 50% beyond until 28" in fury.detail
        (frost,) = service.caps("mage_dps_frost")
        assert (frost.kind, frost.value) == ("hard cap", 10.0)
        assert service.caps("priest_healer_holy") == []

    def test_profiles_are_listed_by_class(self, open_workspace: Opener) -> None:
        classes = [p.class_name for p in open_workspace().profile_service.all()]
        assert classes == sorted(classes, key=list(ClassName).index)


class TestItemDatabase:
    def test_browsing_pages_through_the_items(self, open_workspace: Opener) -> None:
        search = open_workspace().search
        first, total = search.browse(limit=5)
        second, _ = search.browse(offset=5, limit=5)
        assert total == 17 and len(first) == 5
        assert {hit.item.id for hit in first}.isdisjoint(hit.item.id for hit in second)
        assert all(hit.origin == "bundled" and hit.stored_at for hit in first)
        heads, heads_total = search.browse(ItemFilters(slots=(ItemSlot.HEAD,)))
        assert heads_total == len(heads) == 3

    def test_refreshing_drops_expired_lookups(self, open_workspace: Opener) -> None:
        workspace = open_workspace(online=True)
        assert workspace.refresh_cache() == (0, 0)
        workspace.search.fetch_online(12640)
        with workspace.database.session() as session:
            row = session.get(ItemRow, LIONHEART)
            assert row is not None
            row.expires_at = utc_now() - timedelta(minutes=1)
            session.commit()
        assert workspace.refresh_cache() == (1, 1)
        stored = workspace.items.get(LIONHEART)
        assert stored is not None and stored.origin == "bundled"
