"""The local item repository: bundled items, provider lookups kept as a cache, and the
player's own items, all stored as canonical items and searched the same way."""

from __future__ import annotations

import re
import time
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Literal

from sqlalchemy import case, delete, func, or_, select

from wow_gear.models.enums import ArmorType, ItemSlot, WeaponType
from wow_gear.models.item import Item
from wow_gear.repositories.database import Database, ItemRow, ProviderCallRow, utc_now

Origin = Literal["bundled", "cache", "user"]


def _aware(moment: datetime) -> datetime:
    """SQLite hands datetimes back without a zone; everything is stored in UTC."""
    return moment if moment.tzinfo is not None else moment.replace(tzinfo=UTC)


def name_key(name: str) -> str:
    """Lowercase, accents and punctuation folded, for matching what a player types."""
    import unicodedata

    folded = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode("ascii")
    return re.sub(r"[^a-z0-9]+", " ", folded.lower()).strip()


@dataclass(frozen=True)
class ItemFilters:
    ruleset: str | None = None
    slots: tuple[ItemSlot, ...] = ()
    armor_types: tuple[ArmorType, ...] = ()
    weapon_types: tuple[WeaponType, ...] = ()
    max_phase: int | None = None
    max_required_level: int | None = None
    min_quality_rank: int | None = None
    origins: tuple[Origin, ...] = ()


NO_FILTERS = ItemFilters()

QUALITY_RANK = {"poor": 0, "common": 1, "uncommon": 2, "rare": 3, "epic": 4, "legendary": 5}


@dataclass(frozen=True)
class StoredItem:
    item: Item
    origin: Origin
    stored_at: datetime
    expires_at: datetime | None

    @property
    def stale(self) -> bool:
        return self.expires_at is not None and self.expires_at <= utc_now()


@dataclass(frozen=True)
class ProviderCall:
    provider: str
    operation: str
    target: str
    status: str
    detail: str | None
    called_at: datetime
    duration_ms: float | None


class ItemRepository:
    def __init__(self, database: Database) -> None:
        self._db = database

    # --- writing -----------------------------------------------------------------------

    def _row(self, item: Item, origin: Origin, expires_at: datetime | None) -> ItemRow:
        return ItemRow(
            id=item.id,
            ruleset=item.ruleset,
            name=item.name,
            name_key=name_key(item.name),
            slot=item.slot.value,
            armor_type=item.armor_type.value if item.armor_type else None,
            weapon_type=item.weapon_type.value if item.weapon_type else None,
            relic_type=item.relic_type.value if item.relic_type else None,
            quality=item.quality.value if item.quality else None,
            required_level=item.required_level,
            item_level=item.item_level,
            phase=item.phase,
            origin=origin,
            provider=item.provenance.provider,
            data_version=item.provenance.data_version,
            version=item.version,
            fetched_at=item.provenance.fetched_at,
            stored_at=utc_now(),
            expires_at=expires_at,
            payload=item.model_dump_json(),
        )

    def save(self, item: Item, origin: Origin, *, ttl: timedelta | None = None) -> None:
        """Store or replace one item. A cached lookup expires after ``ttl``."""
        expires_at = utc_now() + ttl if ttl is not None else None
        with self._db.session() as session:
            session.merge(self._row(item, origin, expires_at))
            session.commit()

    def replace_origin(self, items: Iterable[Item], origin: Origin) -> int:
        """Replace every item of one origin with ``items`` (for loading the bundled dataset).

        An id already held by another origin - the player's own item, or a fresher lookup
        from an online provider - is kept, not overwritten.
        """
        rows = [self._row(item, origin, None) for item in items]
        with self._db.session() as session:
            session.execute(delete(ItemRow).where(ItemRow.origin == origin))
            taken = set(session.scalars(select(ItemRow.id)).all())
            kept = [row for row in rows if row.id not in taken]
            session.add_all(kept)
            session.commit()
        return len(kept)

    def restore(self, items: Iterable[Item], origin: Origin) -> int:
        """Insert items of ``origin`` whose ids are free (after a cached lookup expires)."""
        with self._db.session() as session:
            taken = set(session.scalars(select(ItemRow.id)).all())
            rows = [self._row(item, origin, None) for item in items if item.id not in taken]
            session.add_all(rows)
            session.commit()
        return len(rows)

    def delete(self, item_id: str) -> bool:
        with self._db.session() as session:
            result = session.execute(delete(ItemRow).where(ItemRow.id == item_id))
            session.commit()
            return bool(result.rowcount)  # type: ignore[attr-defined]

    def purge_expired(self) -> list[str]:
        """Drop cached lookups past their lifetime (Blizzard's terms allow 30 days).

        Returns the ids dropped, so the bundled version of each can be put back.
        """
        now = utc_now()
        with self._db.session() as session:
            expired = list(
                session.scalars(
                    select(ItemRow.id).where(
                        ItemRow.expires_at.is_not(None), ItemRow.expires_at <= now
                    )
                ).all()
            )
            if expired:
                session.execute(delete(ItemRow).where(ItemRow.id.in_(expired)))
                session.commit()
        return expired

    # --- reading -----------------------------------------------------------------------

    @staticmethod
    def _stored(row: ItemRow) -> StoredItem:
        return StoredItem(
            item=Item.model_validate_json(row.payload),
            origin=row.origin,  # type: ignore[arg-type]
            stored_at=_aware(row.stored_at),
            expires_at=_aware(row.expires_at) if row.expires_at is not None else None,
        )

    def get(self, item_id: str) -> StoredItem | None:
        with self._db.session() as session:
            row = session.get(ItemRow, item_id)
            return self._stored(row) if row else None

    def get_many(self, item_ids: Iterable[str]) -> dict[str, StoredItem]:
        ids = list(dict.fromkeys(item_ids))
        if not ids:
            return {}
        with self._db.session() as session:
            rows = session.scalars(select(ItemRow).where(ItemRow.id.in_(ids))).all()
            return {row.id: self._stored(row) for row in rows}

    def search(
        self, text: str, filters: ItemFilters = NO_FILTERS, limit: int = 25
    ) -> list[StoredItem]:
        """Items whose name contains every word typed, best matches first.

        Exact names come first, then names starting with the text, then the rest - each
        group by item level, highest first.
        """
        key = name_key(text)
        statement = select(ItemRow)
        for word in key.split():
            statement = statement.where(ItemRow.name_key.contains(word))
        statement = self._filtered(statement, filters)
        rank = case(
            (ItemRow.name_key == key, 0),
            (ItemRow.name_key.startswith(key), 1),
            else_=2,
        )
        statement = statement.order_by(
            rank, ItemRow.item_level.desc().nulls_last(), ItemRow.name
        ).limit(limit)
        with self._db.session() as session:
            return [self._stored(row) for row in session.scalars(statement).all()]

    @staticmethod
    def _filtered(statement, filters: ItemFilters):  # type: ignore[no-untyped-def]
        if filters.ruleset:
            statement = statement.where(ItemRow.ruleset == filters.ruleset)
        if filters.slots:
            statement = statement.where(ItemRow.slot.in_([s.value for s in filters.slots]))
        if filters.armor_types:
            statement = statement.where(
                or_(
                    ItemRow.armor_type.is_(None),
                    ItemRow.armor_type.in_([a.value for a in filters.armor_types]),
                )
            )
        if filters.weapon_types:
            statement = statement.where(
                ItemRow.weapon_type.in_([w.value for w in filters.weapon_types])
            )
        if filters.max_phase is not None:
            statement = statement.where(
                or_(ItemRow.phase.is_(None), ItemRow.phase <= filters.max_phase)
            )
        if filters.max_required_level is not None:
            statement = statement.where(ItemRow.required_level <= filters.max_required_level)
        if filters.min_quality_rank is not None:
            allowed = [q for q, rank in QUALITY_RANK.items() if rank >= filters.min_quality_rank]
            statement = statement.where(ItemRow.quality.in_(allowed))
        if filters.origins:
            statement = statement.where(ItemRow.origin.in_(filters.origins))
        return statement

    def browse(
        self, filters: ItemFilters = NO_FILTERS, *, offset: int = 0, limit: int = 50
    ) -> tuple[list[StoredItem], int]:
        """A page of items matching the filters, by name, and the total count."""
        statement = self._filtered(select(ItemRow), filters)
        count_statement = self._filtered(select(func.count()).select_from(ItemRow), filters)
        with self._db.session() as session:
            total = int(session.scalar(count_statement) or 0)
            rows = session.scalars(
                statement.order_by(ItemRow.name).offset(offset).limit(limit)
            ).all()
            return [self._stored(row) for row in rows], total

    def counts(self) -> dict[str, int]:
        with self._db.session() as session:
            rows = session.execute(
                select(ItemRow.origin, func.count()).group_by(ItemRow.origin)
            ).all()
            return {origin: int(count) for origin, count in rows}

    # --- provider calls -----------------------------------------------------------------

    def record_call(
        self,
        provider: str,
        operation: str,
        target: str,
        status: str,
        detail: str | None = None,
        started: float | None = None,
    ) -> None:
        duration = (time.perf_counter() - started) * 1000 if started is not None else None
        with self._db.session() as session:
            session.add(
                ProviderCallRow(
                    provider=provider,
                    operation=operation,
                    target=target[:200],
                    status=status,
                    detail=detail,
                    called_at=utc_now(),
                    duration_ms=duration,
                )
            )
            session.commit()

    def recent_calls(self, provider: str | None = None, limit: int = 20) -> list[ProviderCall]:
        statement = select(ProviderCallRow).order_by(ProviderCallRow.id.desc()).limit(limit)
        if provider:
            statement = statement.where(ProviderCallRow.provider == provider)
        with self._db.session() as session:
            return [
                ProviderCall(
                    provider=row.provider,
                    operation=row.operation,
                    target=row.target,
                    status=row.status,
                    detail=row.detail,
                    called_at=row.called_at,
                    duration_ms=row.duration_ms,
                )
                for row in session.scalars(statement).all()
            ]
