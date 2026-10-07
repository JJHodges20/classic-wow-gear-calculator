"""The workspace: everything the calculator needs, opened once and shared by the services.

Opening a workspace reads the configuration, loads the rulesets and profiles, opens the
local database, loads the bundled dataset into it when its version changed, drops expired
lookups (restoring the bundled version of each), and builds the online client when its
credentials are set. The app and the command line each open one.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
from pathlib import Path

from pydantic import ValidationError

from wow_gear.core import ConfigError, ProviderError, Settings, load_settings
from wow_gear.core.logging import get_logger
from wow_gear.data_sources.blizzard import BlizzardClient
from wow_gear.data_sources.bundled import read_bundled, read_metadata
from wow_gear.models.item import Item
from wow_gear.models.ruleset import Ruleset
from wow_gear.profiles.loader import ProfileRegistry
from wow_gear.repositories.database import Database
from wow_gear.repositories.items import ItemRepository
from wow_gear.rulesets.loader import RulesetRegistry
from wow_gear.services.health import BundledStatus, HealthService
from wow_gear.services.item_entry import ItemEntryService
from wow_gear.services.item_search import ItemSearchService, OnlineProvider, OnlineState

LOG = get_logger(__name__)
BUNDLED_VERSION_KEY = "bundled_version"


@dataclass(frozen=True)
class OnlineSetup:
    client: OnlineProvider | None
    state: OnlineState
    detail: str


class Workspace:
    def __init__(
        self,
        settings: Settings,
        *,
        database: Database | None = None,
        online: OnlineProvider | None = None,
    ) -> None:
        self.settings = settings
        self.rulesets = RulesetRegistry.from_directory(settings.config_dir / "rulesets")
        self.profiles = ProfileRegistry.from_directory(
            settings.config_dir / "profiles", self.rulesets
        )
        try:
            self.ruleset: Ruleset = self.rulesets.get(settings.app.app.default_ruleset)
        except Exception as error:
            raise ConfigError(f"default ruleset: {error}") from error
        self.database = database or Database(settings.database_path)
        self.items = ItemRepository(self.database)
        self.bundled = self._load_bundled()
        self._restore_expired()
        setup = (
            OnlineSetup(online, "ok", "Injected") if online is not None else self._online_setup()
        )
        self.online = setup
        self.entry = ItemEntryService(self.ruleset)
        self.search = ItemSearchService(
            self.items,
            self.ruleset,
            online=setup.client,
            online_state=setup.state,
            cache_ttl=timedelta(days=settings.app.cache.item_ttl_days),
        )
        self.health = HealthService(
            settings, repository=self.items, bundled=self.bundled, online_detail=setup.detail
        )

    @classmethod
    def open(cls, root: Path | None = None) -> Workspace:
        return cls(load_settings(root))

    def close(self) -> None:
        client = self.online.client
        if isinstance(client, BlizzardClient):
            client.close()
        self.database.dispose()

    # --- bundled dataset ----------------------------------------------------------------

    def _bundled_items(self) -> tuple[str, list[Item], int]:
        dataset = read_bundled(self.settings.bundled_dir)
        items, rejected = [], 0
        for record in dataset.items:
            try:
                items.append(Item.model_validate(record))
            except ValidationError:
                rejected += 1
        return dataset.version, items, rejected

    def _load_bundled(self) -> BundledStatus:
        metadata = read_metadata(self.settings.bundled_dir)
        if metadata is None:
            return BundledStatus(version=None, loaded=0, metadata={}, problem="No bundled dataset")
        version = str(metadata.get("version"))
        stored = self.database.get_meta(BUNDLED_VERSION_KEY)
        counts = self.items.counts()
        if stored == version and counts.get("bundled", 0) > 0:
            return BundledStatus(version=version, loaded=counts["bundled"], metadata=metadata)
        try:
            version, items, rejected = self._bundled_items()
        except ProviderError as error:
            return BundledStatus(version=None, loaded=0, metadata=metadata, problem=str(error))
        loaded = self.items.replace_origin(items, "bundled")
        self.database.set_meta(BUNDLED_VERSION_KEY, version)
        LOG.info("loaded bundled dataset %s: %d items (%d rejected)", version, loaded, rejected)
        problem = f"{rejected} bundled items failed validation" if rejected else None
        return BundledStatus(version=version, loaded=loaded, metadata=metadata, problem=problem)

    def _restore_expired(self) -> None:
        expired = self.items.purge_expired()
        if not expired or self.bundled.version is None:
            return
        try:
            _, items, _ = self._bundled_items()
        except ProviderError:
            return
        wanted = set(expired)
        restored = self.items.restore((item for item in items if item.id in wanted), "bundled")
        LOG.info("dropped %d expired lookups, restored %d bundled items", len(expired), restored)

    # --- online provider ----------------------------------------------------------------

    def _online_setup(self) -> OnlineSetup:
        try:
            provider = self.settings.providers.get("blizzard")
        except ConfigError:
            return OnlineSetup(None, "disabled", "Not configured in providers.yaml")
        if not provider.enabled or provider.status != "active":
            return OnlineSetup(None, "disabled", "Turned off in providers.yaml")
        if not self.settings.has_credentials(provider):
            return OnlineSetup(None, "not_configured", "Credentials not set; see .env.example")
        names = provider.secrets
        try:
            client = BlizzardClient(
                self.settings.secret(names[0]),
                self.settings.secret(names[1]),
                region=str(provider.settings.get("region", "us")),
                locale=str(provider.settings.get("locale", "en_US")),
                timeout=float(provider.settings.get("timeout_seconds", 10)),
            )
        except ProviderError as error:
            return OnlineSetup(None, "not_configured", str(error))
        return OnlineSetup(client, "ok", f"Ready ({client.namespace})")

    # --- convenience --------------------------------------------------------------------

    def ruleset_for(self, ruleset_id: str | None = None) -> Ruleset:
        return self.rulesets.get(ruleset_id) if ruleset_id else self.ruleset
