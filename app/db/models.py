"""Portable SQLAlchemy inventory schema for PostgreSQL and SQLite."""

from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    MetaData,
    String,
    UniqueConstraint,
    Uuid,
    func,
    text,
    true,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy.types import TypeDecorator


class UTCDateTime(TypeDecorator[datetime]):
    """Keep UTC offsets in API responses even when SQLite drops timezone data."""

    impl = DateTime(timezone=True)
    cache_ok = True

    def process_bind_param(self, value: datetime | None, dialect: Any) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("timestamp must include a timezone")
        return value.astimezone(UTC)

    def process_result_value(self, value: datetime | None, dialect: Any) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is None:
            return value.replace(tzinfo=UTC)
        return value.astimezone(UTC)


class Base(DeclarativeBase):
    metadata = MetaData(
        naming_convention={
            "ix": "ix_%(table_name)s_%(column_0_name)s",
            "uq": "uq_%(table_name)s_%(column_0_name)s",
            "ck": "ck_%(table_name)s_%(constraint_name)s",
            "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
            "pk": "pk_%(table_name)s",
        }
    )


class VersionedRecord:
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default="1")
    created_at: Mapped[datetime] = mapped_column(
        UTCDateTime(), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        UTCDateTime(), nullable=False, server_default=func.now(), onupdate=func.now()
    )


class Host(VersionedRecord, Base):
    __tablename__ = "hosts"
    __table_args__ = (
        CheckConstraint("status IN ('active', 'inactive', 'maintenance')", name="valid_status"),
        CheckConstraint("version >= 1", name="positive_version"),
        Index("ix_hosts_created_at_id", "created_at", "id"),
        Index("ix_hosts_status", "status"),
        Index("ix_hosts_environment", "environment"),
    )

    hostname: Mapped[str] = mapped_column(String(253), nullable=False, unique=True)
    environment: Mapped[str] = mapped_column(
        String(64), nullable=False, default="dev", server_default="dev"
    )
    status: Mapped[str] = mapped_column(
        String(16), nullable=False, default="active", server_default="active"
    )


class Agent(VersionedRecord, Base):
    __tablename__ = "agents"
    __table_args__ = (
        UniqueConstraint("host_id", "name", name="uq_agents_host_id_name"),
        CheckConstraint("state IN ('online', 'offline', 'disabled')", name="valid_state"),
        CheckConstraint("version >= 1", name="positive_version"),
        Index("ix_agents_created_at_id", "created_at", "id"),
        Index("ix_agents_state", "state"),
    )

    host_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("hosts.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    state: Mapped[str] = mapped_column(
        String(16), nullable=False, default="offline", server_default="offline"
    )
    last_seen_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)


class TaskDefinition(VersionedRecord, Base):
    __tablename__ = "task_definitions"
    __table_args__ = (
        CheckConstraint("version >= 1", name="positive_version"),
        Index("ix_task_definitions_created_at_id", "created_at", "id"),
        Index("ix_task_definitions_enabled", "enabled"),
    )

    agent_id: Mapped[UUID | None] = mapped_column(
        Uuid, ForeignKey("agents.id", ondelete="RESTRICT"), nullable=True, index=True
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    command_template_metadata: Mapped[dict[str, Any]] = mapped_column(
        JSON, nullable=False, default=dict, server_default=text("'{}'")
    )
    enabled: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default=true()
    )
