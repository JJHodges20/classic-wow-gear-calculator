"""Provider response -> normalization -> repository -> search result, and what happens when
a provider fails (roadmap section 11, integration tests)."""

from __future__ import annotations

import json
from collections.abc import Callable
from datetime import timedelta
from pathlib import Path

import pytest

from wow_gear.models.character import CharacterContext
from wow_gear.models.enums import ArmorType, ItemSlot, Stat
from wow_gear.models.providers.blizzard import BlizzardItem
from wow_gear.processing.blizzard import normalize_blizzard_item
from wow_gear.processing.manual import form_to_item, read_tooltip
from wow_gear.repositories.database import ItemRow, utc_now
from wow_gear.repositories.items import ItemFilters
from wow_gear.scoring.engine import score_item
from wow_gear.services.workspace import Workspace

from .conftest import BLIZZARD

Opener = Callable[..., Workspace]


class TestBundledDataset:
    def test_it_is_loaded_once_per_version(self, open_workspace: Opener) -> None:
        first = open_workspace()
        assert first.bundled.version == "fixture-1" and first.bundled.loaded == 15
        assert first.items.counts() == {"bundled": 15}
        second = open_workspace()
        assert (
            second.bundled.loaded == 15
            and second.database.get_meta("bundled_version") == "fixture-1"
        )

    def test_health_reports_it(self, open_workspace: Opener) -> None:
        checks = {check.name: check for check in open_workspace().health.checks()}
        assert checks["bundled dataset"].status == "ok"
        assert "15 items" in checks["bundled dataset"].detail
        assert checks["provider blizzard"].status == "warning"  # no credentials in the test


class TestLocalSearch:
    def test_by_name_prefix_and_words_in_any_order(self, open_workspace: Opener) -> None:
        search = open_workspace().search
        assert search.search("Lionheart Helm").hits[0].item.name == "Lionheart Helm"
        assert search.search("helm lion").hits[0].item.name == "Lionheart Helm"
        names = [hit.item.name for hit in search.search("helm").hits]
        assert {"Lionheart Helm", "Expert Goldminer's Helmet"} <= set(names)

    def test_exact_names_come_first(self, open_workspace: Opener) -> None:
        names = [hit.item.name for hit in open_workspace().search.search("hand of justice").hits]
        assert names[0] == "Hand of Justice"

    def test_filters(self, open_workspace: Opener) -> None:
        search = open_workspace().search
        heads = search.search("e", ItemFilters(slots=(ItemSlot.HEAD,))).hits
        assert heads and all(hit.item.slot == ItemSlot.HEAD for hit in heads)
        early = [hit.item.name for hit in search.search("talisman", ItemFilters(max_phase=2)).hits]
        assert "Drake Fang Talisman" not in early  # a Blackwing Lair item, phase 3
        cloth = search.search("e", ItemFilters(armor_types=(ArmorType.CLOTH,))).hits
        assert all(hit.item.armor_type in (None, ArmorType.CLOTH) for hit in cloth)

    def test_by_id(self, open_workspace: Opener) -> None:
        search = open_workspace().search
        assert search.search("12640").hits[0].item.name == "Lionheart Helm"
        assert search.search("classic_era:12640").hits[0].item.name == "Lionheart Helm"
        missing = search.search("900001")
        assert not missing.hits and "No item 900001" in missing.notices[0]

    def test_an_empty_query_finds_nothing(self, open_workspace: Opener) -> None:
        assert open_workspace().search.search("   ").hits == ()


class TestOnlineLookup:
    def test_without_credentials_local_results_and_a_notice(self, open_workspace: Opener) -> None:
        outcome = open_workspace().search.search("lionheart", online=True)
        assert outcome.hits and outcome.online == "not_configured"
        assert "needs Blizzard API credentials" in outcome.notices[0]

    def test_an_online_search_caches_what_it_finds(self, open_workspace: Opener) -> None:
        workspace = open_workspace(online=True)
        outcome = workspace.search.search("girdle", online=True)
        assert outcome.online == "ok"
        hit = next(hit for hit in outcome.hits if hit.item.name == "Test Girdle of Lookups")
        assert hit.origin == "cache"
        stored = workspace.items.get("classic_era:900001")
        assert stored is not None and stored.expires_at is not None
        assert timedelta(days=29) < stored.expires_at - utc_now() <= timedelta(days=30)
        assert [call.status for call in workspace.items.recent_calls()] == ["ok", "ok"]
        # The second search is answered from the cache: no new item call.
        workspace.search.search("girdle", online=True)
        operations = [call.operation for call in workspace.items.recent_calls()]
        assert operations.count("item") == 1

    def test_a_lookup_by_id(self, open_workspace: Opener) -> None:
        outcome = open_workspace(online=True).search.search("900001", online=True)
        assert outcome.hits[0].item.name == "Test Girdle of Lookups"
        unknown = open_workspace(online=True).search.search("900002", online=True)
        assert not unknown.hits and "Blizzard has no item 900002" in unknown.notices[0]

    @pytest.mark.parametrize("fail", ["connect", "timeout", "500", "429", "garbage"])
    def test_a_failing_provider_leaves_local_search_working(
        self, open_workspace: Opener, fail: str
    ) -> None:
        outcome = open_workspace(online=True, fail=fail).search.search("lionheart", online=True)
        assert outcome.online == "failed"
        assert outcome.hits[0].item.name == "Lionheart Helm"  # the local copy
        assert outcome.notices[0].startswith("Online lookup failed")

    def test_cached_lookups_expire_and_the_bundled_item_returns(
        self, open_workspace: Opener
    ) -> None:
        workspace = open_workspace(online=True)
        workspace.search.fetch_online(12640)
        assert workspace.items.get("classic_era:12640").origin == "cache"  # type: ignore[union-attr]
        with workspace.database.session() as session:
            row = session.get(ItemRow, "classic_era:12640")
            assert row is not None
            row.expires_at = utc_now() - timedelta(minutes=1)
            session.commit()
        reopened = open_workspace()
        stored = reopened.items.get("classic_era:12640")
        assert stored is not None and stored.origin == "bundled"


class TestNormalizationEquivalence:
    """Manual and provider normalization produce equivalent canonical items (section 11)."""

    def blizzard(self, item_id: int):  # type: ignore[no-untyped-def]
        payload = BlizzardItem.model_validate(
            json.loads((BLIZZARD / f"item_{item_id}.json").read_text())
        )
        return normalize_blizzard_item(
            payload, namespace="static-classic1x-us", region="us", fetched_at=utc_now()
        )

    def test_blizzard_and_bundled_agree(self, open_workspace: Opener) -> None:
        bundled = open_workspace().items.get("classic_era:12640")
        assert bundled is not None
        online = self.blizzard(12640)
        assert online.stats == bundled.item.stats
        assert (online.slot, online.armor_type, online.required_level) == (
            bundled.item.slot,
            bundled.item.armor_type,
            bundled.item.required_level,
        )
        blade = self.blizzard(18832)
        bundled_blade = open_workspace().items.get("classic_era:18832")
        assert bundled_blade is not None
        assert blade.weapon == bundled_blade.item.weapon and blade.stats == bundled_blade.item.stats

    def test_blizzard_and_a_pasted_tooltip_agree(self) -> None:
        reading = read_tooltip(
            "Lionheart Helm\nHead  Plate\n565 Armor\n+18 Strength\nRequires Level 56\n"
            "Equip: Improves your chance to get a critical strike by 2%.\n"
            "Equip: Improves your chance to hit by 2%."
        )
        assert reading.form is not None
        manual = form_to_item(reading.form, "classic_era")
        assert manual.stats == self.blizzard(12640).stats

    def test_conditional_and_unscored_effects_survive(self) -> None:
        girdle = self.blizzard(900001)
        assert girdle.stats[Stat.HIT] == 1 and girdle.stats[Stat.FIRE_RESISTANCE] == 7
        conditional = [e for e in girdle.equip_effects if e.condition is not None]
        assert {e.stat for e in conditional} == {Stat.ATTACK_POWER, Stat.RANGED_ATTACK_POWER}
        assert any(
            e.stat is None and "nobody has modeled" in e.description for e in girdle.equip_effects
        )
        assert girdle.provenance.provider == "blizzard" and "Blizzard" in (
            girdle.provenance.license or ""
        )


class TestImports:
    def test_csv_rows_become_your_items(self, open_workspace: Opener, tmp_path: Path) -> None:
        source = tmp_path / "items.csv"
        source.write_text(
            "name,slot,armor_type,required_level,strength,stamina,effects\n"
            "My Helm,head,plate,60,20,15,Equip: Improves your chance to hit by 1%.\n"
            "Broken Row,elbow,plate,60,5,,\n"
            "My Ring,finger,,60,,10,Chance on hit: Sparkles.\n",
            encoding="utf-8",
        )
        workspace = open_workspace()
        report = workspace.search.import_file(source)
        assert [item.name for item in report.imported] == ["My Helm", "My Ring"]
        assert report.rejected[0].row == 2 and "slot" in report.rejected[0].errors[0]
        helm = report.imported[0]
        assert helm.stats[Stat.HIT] == 1 and helm.provenance.provider == "file_import"
        assert workspace.items.counts()["user"] == 2
        assert workspace.search.search("my helm").hits[0].origin == "user"

    def test_unknown_columns_are_rejected(self, open_workspace: Opener, tmp_path: Path) -> None:
        source = tmp_path / "items.csv"
        source.write_text("name,slot,haste\nFast Boots,feet,5\n", encoding="utf-8")
        report = open_workspace().search.import_file(source)
        assert not report.imported and "haste" in report.rejected[0].errors[0]

    def test_canonical_json_round_trips(self, open_workspace: Opener, tmp_path: Path) -> None:
        workspace = open_workspace()
        helm = workspace.items.get("classic_era:12640")
        assert helm is not None
        exported = helm.item.model_copy(update={"id": "custom:my-copy", "name": "My Copy"})
        source = tmp_path / "items.json"
        source.write_text(
            json.dumps({"items": [exported.model_dump(mode="json")]}), encoding="utf-8"
        )
        report = workspace.search.import_file(source)
        assert report.imported[0].stats == helm.item.stats


def test_a_searched_item_scores_like_any_other(open_workspace: Opener) -> None:
    workspace = open_workspace()
    helm = workspace.search.search("lionheart").hits[0].item
    profile = workspace.profiles.get("warrior_dps_fury")
    context = CharacterContext(
        ruleset="classic_era",
        phase=6,
        level=60,
        class_name="warrior",  # type: ignore[arg-type]
        role="melee_dps",  # type: ignore[arg-type]
        profile_id=profile.id,
        current_stats={Stat.HIT: 6},
    )
    result = score_item(helm, context, profile, workspace.ruleset)
    assert result.score == 116.0 and result.item_provider == "bundled"
