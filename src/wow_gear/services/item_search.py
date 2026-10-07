"""Finding items (roadmap section 7, path B): the UI calls this service, never a provider.

Search looks in the local repository first - the bundled dataset, earlier lookups and the
player's own items - and goes online only when asked, through the configured provider.
Online results are validated, cached for at most the provider's allowed lifetime and
returned with the local ones. A provider that fails, times out or is not configured turns
into a notice; local search keeps working.
"""

from __future__ import annotations

import re
import time
from dataclasses import dataclass, field
from datetime import timedelta
from pathlib import Path
from typing import Literal, Protocol

from pydantic import ValidationError

from wow_gear.core.errors import NotFoundError, ProviderError, ProviderNotConfigured
from wow_gear.core.logging import get_logger
from wow_gear.data_sources.files import read_item_file
from wow_gear.models.item import Item
from wow_gear.models.providers.blizzard import BlizzardItem, BlizzardSearchPage
from wow_gear.models.ruleset import Ruleset
from wow_gear.processing.blizzard import normalize_blizzard_item
from wow_gear.processing.imports import ImportedRecord, import_records
from wow_gear.processing.validation import ValidationIssue, validate_item
from wow_gear.repositories.database import utc_now
from wow_gear.repositories.items import (
    NO_FILTERS,
    ItemFilters,
    ItemRepository,
    Origin,
    StoredItem,
)

__all__ = [
    "NO_FILTERS",
    "ImportReport",
    "ItemFilters",
    "ItemSearchService",
    "OnlineProvider",
    "OnlineState",
    "SearchHit",
    "SearchOutcome",
]

LOG = get_logger(__name__)
ID_QUERY = re.compile(r"^(?:classic_era:)?(\d{1,6})$")
OnlineState = Literal["not_requested", "not_configured", "disabled", "ok", "failed"]


class OnlineProvider(Protocol):
    """What the search service needs from an online item provider."""

    @property
    def namespace(self) -> str: ...

    @property
    def region(self) -> str: ...

    def item(self, item_id: int) -> dict[str, object]: ...

    def search(self, name: str, page_size: int = 10) -> dict[str, object]: ...


@dataclass(frozen=True)
class SearchHit:
    item: Item
    origin: Origin
    stale: bool = False


@dataclass(frozen=True)
class SearchOutcome:
    query: str
    hits: tuple[SearchHit, ...]
    notices: tuple[str, ...] = ()
    online: OnlineState = "not_requested"


@dataclass(frozen=True)
class ImportReport:
    imported: tuple[Item, ...]
    rejected: tuple[ImportedRecord, ...]
    issues: dict[str, tuple[ValidationIssue, ...]] = field(default_factory=dict)


class ItemSearchService:
    PROVIDER = "blizzard"

    def __init__(
        self,
        repository: ItemRepository,
        ruleset: Ruleset,
        *,
        online: OnlineProvider | None = None,
        online_state: OnlineState = "not_configured",
        cache_ttl: timedelta = timedelta(days=30),
    ) -> None:
        self._items = repository
        self._ruleset = ruleset
        self._online = online
        self._online_state: OnlineState = online_state if online is None else "ok"
        self._ttl = min(cache_ttl, timedelta(days=30))

    @property
    def online_available(self) -> bool:
        return self._online is not None

    @property
    def online_state(self) -> OnlineState:
        return self._online_state

    # --- searching ----------------------------------------------------------------------

    def search(
        self,
        text: str,
        filters: ItemFilters = NO_FILTERS,
        *,
        limit: int = 25,
        online: bool = False,
        online_limit: int = 10,
    ) -> SearchOutcome:
        query = " ".join(text.split())
        if not query:
            return SearchOutcome(query="", hits=())
        id_match = ID_QUERY.match(query)
        if id_match:
            return self._by_id(query, int(id_match.group(1)), online=online)
        local = [self._hit(stored) for stored in self._items.search(query, filters, limit)]
        if not online:
            return SearchOutcome(query=query, hits=tuple(local))
        if self._online is None:
            return SearchOutcome(
                query=query,
                hits=tuple(local),
                notices=(self._unavailable_notice(),),
                online=self._online_state,
            )
        found, notices, state = self._search_online(query, online_limit)
        merged = {hit.item.id: hit for hit in local}
        for hit in found:
            merged[hit.item.id] = hit
        hits = sorted(
            merged.values(), key=lambda hit: (hit.item.name.lower() != query.lower(), hit.item.name)
        )
        return SearchOutcome(
            query=query, hits=tuple(hits[: max(limit, len(found))]), notices=notices, online=state
        )

    def _by_id(self, query: str, game_id: int, *, online: bool) -> SearchOutcome:
        stored = self._items.get(f"classic_era:{game_id}")
        if stored is not None and not (online and stored.stale):
            return SearchOutcome(query=query, hits=(self._hit(stored),))
        if not online:
            notices = () if stored else (f"No item {game_id} in the local data.",)
            return SearchOutcome(
                query=query, hits=(self._hit(stored),) if stored else (), notices=notices
            )
        if self._online is None:
            return SearchOutcome(
                query=query,
                hits=(self._hit(stored),) if stored else (),
                notices=(self._unavailable_notice(),),
                online=self._online_state,
            )
        try:
            item = self.fetch_online(game_id)
        except NotFoundError:
            return SearchOutcome(
                query=query, hits=(), notices=(f"Blizzard has no item {game_id}.",), online="ok"
            )
        except ProviderError as error:
            hits = (self._hit(stored),) if stored else ()
            return SearchOutcome(
                query=query, hits=hits, notices=(self._failure_notice(error),), online="failed"
            )
        return SearchOutcome(query=query, hits=(SearchHit(item, "cache"),), online="ok")

    def _search_online(
        self, query: str, limit: int
    ) -> tuple[list[SearchHit], tuple[str, ...], OnlineState]:
        assert self._online is not None
        started = time.perf_counter()
        try:
            page = BlizzardSearchPage.model_validate(self._online.search(query, page_size=limit))
        except ValidationError as error:
            self._items.record_call(
                self.PROVIDER, "search", query, "failed", "unexpected response", started
            )
            return (
                [],
                (f"Online search sent an unexpected response ({error.error_count()} problems).",),
                "failed",
            )
        except ProviderError as error:
            self._items.record_call(self.PROVIDER, "search", query, "failed", str(error), started)
            return [], (self._failure_notice(error),), "failed"
        self._items.record_call(
            self.PROVIDER, "search", query, "ok", f"{len(page.results)} results", started
        )
        hits: list[SearchHit] = []
        notices: list[str] = []
        for result in page.results[:limit]:
            item_id = f"classic_era:{result.data.id}"
            cached = self._items.get(item_id)
            if cached is not None and cached.origin == "cache" and not cached.stale:
                hits.append(self._hit(cached))
                continue
            try:
                hits.append(SearchHit(self.fetch_online(result.data.id), "cache"))
            except NotFoundError:
                continue
            except ProviderError as error:
                notices.append(self._failure_notice(error))
                break
        return hits, tuple(dict.fromkeys(notices)), "failed" if notices and not hits else "ok"

    def fetch_online(self, game_id: int) -> Item:
        """Look one item up online, validate it, cache it, and return it."""
        if self._online is None:
            raise ProviderNotConfigured(self._unavailable_notice())
        started = time.perf_counter()
        try:
            payload = BlizzardItem.model_validate(self._online.item(game_id))
            item = normalize_blizzard_item(
                payload,
                namespace=self._online.namespace,
                region=self._online.region,
                fetched_at=utc_now(),
            )
        except NotFoundError:
            self._items.record_call(self.PROVIDER, "item", str(game_id), "not_found", None, started)
            raise
        except ValidationError as error:
            self._items.record_call(
                self.PROVIDER, "item", str(game_id), "failed", "unexpected response", started
            )
            raise ProviderError(
                f"Blizzard sent an item that could not be read ({error.error_count()} problems)"
            ) from error
        except ProviderError as error:
            self._items.record_call(
                self.PROVIDER, "item", str(game_id), "failed", str(error), started
            )
            raise
        except Exception as error:  # normalization errors are data errors
            self._items.record_call(
                self.PROVIDER, "item", str(game_id), "failed", str(error), started
            )
            raise ProviderError(f"item {game_id} could not be normalized: {error}") from error
        report = validate_item(item, self._ruleset)
        if report.errors:
            detail = "; ".join(issue.message for issue in report.errors)
            self._items.record_call(self.PROVIDER, "item", str(game_id), "invalid", detail, started)
            raise ProviderError(f"item {game_id} failed validation: {detail}")
        self._items.save(item, "cache", ttl=self._ttl)
        self._items.record_call(self.PROVIDER, "item", str(game_id), "ok", item.name, started)
        return item

    # --- single items -------------------------------------------------------------------

    def get(self, item_id: str) -> Item | None:
        stored = self._items.get(item_id)
        return stored.item if stored else None

    def save_user_item(self, item: Item) -> None:
        """Keep a manual or imported item, searchable like any other."""
        self._items.save(item, "user")

    def import_file(self, path: Path) -> ImportReport:
        records = read_item_file(path)
        results = import_records(
            records, ruleset_id=self._ruleset.id, source=f"Imported from {path.name}"
        )
        imported: list[Item] = []
        rejected: list[ImportedRecord] = []
        issues: dict[str, tuple[ValidationIssue, ...]] = {}
        for record in results:
            if record.item is None:
                rejected.append(record)
                continue
            report = validate_item(record.item, self._ruleset)
            if not report.ok:
                messages = tuple(issue.message for issue in report.errors)
                rejected.append(ImportedRecord(row=record.row, item=None, errors=messages))
                continue
            self._items.save(record.item, "user")
            imported.append(record.item)
            if report.issues:
                issues[record.item.id] = report.issues
        LOG.info(
            "imported %d item(s) from %s, rejected %d", len(imported), path.name, len(rejected)
        )
        return ImportReport(tuple(imported), tuple(rejected), issues)

    # --- helpers ------------------------------------------------------------------------

    @staticmethod
    def _hit(stored: StoredItem) -> SearchHit:
        return SearchHit(stored.item, stored.origin, stored.stale)

    def _unavailable_notice(self) -> str:
        if self._online_state == "disabled":
            return "Online lookup is turned off in configs/providers.yaml; showing local results."
        return (
            "Online lookup needs Blizzard API credentials (see .env.example); showing local "
            "results."
        )

    @staticmethod
    def _failure_notice(error: Exception) -> str:
        return f"Online lookup failed ({error}); showing local results."
