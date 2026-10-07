"""The local SQLite database: one file under the user data directory, created on first use."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import (
    DateTime,
    Float,
    Index,
    Integer,
    String,
    Text,
    create_engine,
    event,
)
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, sessionmaker

SCHEMA_VERSION = 1


def utc_now() -> datetime:
    return datetime.now(UTC).replace(microsecond=0)


class Base(DeclarativeBase):
    pass


class ItemRow(Base):
    """A canonical item, from any source. ``payload`` is the full Item as JSON."""

    __tablename__ = "items"

    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    ruleset: Mapped[str] = mapped_column(String(40), index=True)
    name: Mapped[str] = mapped_column(String(120))
    name_key: Mapped[str] = mapped_column(String(120), index=True)
    slot: Mapped[str] = mapped_column(String(24), index=True)
    armor_type: Mapped[str | None] = mapped_column(String(16))
    weapon_type: Mapped[str | None] = mapped_column(String(24))
    relic_type: Mapped[str | None] = mapped_column(String(16))
    quality: Mapped[str | None] = mapped_column(String(16))
    required_level: Mapped[int] = mapped_column(Integer)
    item_level: Mapped[int | None] = mapped_column(Integer)
    phase: Mapped[int | None] = mapped_column(Integer)
    origin: Mapped[str] = mapped_column(String(16), index=True)
    """bundled, cache (a provider lookup) or user (entered or imported by the player)."""
    provider: Mapped[str] = mapped_column(String(40))
    data_version: Mapped[str] = mapped_column(String(80))
    version: Mapped[str] = mapped_column(String(16))
    fetched_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    stored_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    payload: Mapped[str] = mapped_column(Text)

    __table_args__ = (Index("ix_items_ruleset_slot_name", "ruleset", "slot", "name_key"),)


class ProviderCallRow(Base):
    """One call to an online provider: for data health and for the cache lifetime rules."""

    __tablename__ = "provider_calls"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    provider: Mapped[str] = mapped_column(String(40), index=True)
    operation: Mapped[str] = mapped_column(String(40))
    target: Mapped[str] = mapped_column(String(200))
    status: Mapped[str] = mapped_column(String(16))
    detail: Mapped[str | None] = mapped_column(Text)
    called_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    duration_ms: Mapped[float | None] = mapped_column(Float)


class MetaRow(Base):
    __tablename__ = "meta"

    key: Mapped[str] = mapped_column(String(80), primary_key=True)
    value: Mapped[str] = mapped_column(Text)


class Database:
    """Opens (and creates) the SQLite file and hands out sessions."""

    def __init__(self, path: Path | None) -> None:
        if path is None:
            url = "sqlite+pysqlite:///:memory:"
        else:
            path.parent.mkdir(parents=True, exist_ok=True)
            url = f"sqlite+pysqlite:///{path.as_posix()}"
        self.path = path
        self.engine: Engine = create_engine(url, future=True)

        @event.listens_for(self.engine, "connect")
        def _pragmas(connection, _record):  # type: ignore[no-untyped-def]
            cursor = connection.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            if path is not None:
                cursor.execute("PRAGMA journal_mode=WAL")
            cursor.close()

        Base.metadata.create_all(self.engine)
        self._sessions = sessionmaker(self.engine, expire_on_commit=False)
        with self.session() as session:
            if session.get(MetaRow, "schema_version") is None:
                session.add(MetaRow(key="schema_version", value=str(SCHEMA_VERSION)))
                session.commit()

    def session(self) -> Session:
        return self._sessions()

    def get_meta(self, key: str) -> str | None:
        with self.session() as session:
            row = session.get(MetaRow, key)
            return row.value if row else None

    def set_meta(self, key: str, value: str) -> None:
        with self.session() as session:
            session.merge(MetaRow(key=key, value=value))
            session.commit()

    def dispose(self) -> None:
        self.engine.dispose()
