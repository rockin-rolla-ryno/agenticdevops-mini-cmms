"""SQLAlchemy 2.0 typed declarative models — the persisted core schema.

Schema authority: ``docs/data-model.md`` (Rule 12 — moves with this file).

Enum-valued columns are short strings constrained by CHECK constraints and
typed in Python as ``StrEnum`` — never native Postgres ENUM types. This is a
deliberate dual-engine decision (DEC-006): the same DDL runs on SQLite and
Postgres, and adding a value stays an additive CHECK change, not an
``ALTER TYPE``.

All timestamps are UTC.
"""

from datetime import UTC, datetime
from enum import StrEnum

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    MetaData,
    String,
    Text,
    false,
    text,
    true,
)
from sqlalchemy import (
    Enum as SAEnum,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class UserRole(StrEnum):
    USER = "user"
    PLANNER = "planner"


class AssetProvenance(StrEnum):
    """DEC-008: authority splits by provenance."""

    UNS_DISCOVERED = "uns_discovered"
    MANUAL = "manual"


class DowntimeProducer(StrEnum):
    UNS = "uns"
    MANUAL = "manual"


class WorkOrderOrigin(StrEnum):
    """Typed, extensible origin — never assume a WO requires a downtime event."""

    UNS_DOWNTIME = "uns_downtime"
    MANUAL_DOWNTIME = "manual_downtime"
    MANUAL = "manual"


class WorkOrderPriority(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class WorkOrderStatus(StrEnum):
    OPEN = "open"
    PLANNED = "planned"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=NAMING_CONVENTION)


def utcnow() -> datetime:
    return datetime.now(UTC)


def _str_enum(enum_cls: type[StrEnum], name: str) -> SAEnum:
    """String column + CHECK constraint for a StrEnum (never a native enum)."""
    return SAEnum(
        enum_cls,
        name=name,
        native_enum=False,
        length=32,
        values_callable=lambda cls: [member.value for member in cls],
        create_constraint=True,
    )


class User(Base):
    """Seeded config accounts (FS-Q5); T-004 adds auth + `active`.

    ``active`` exists for seeded-config revocation: an account removed from
    the users config must stop logging in, but its row (referenced by
    history FKs) is never deleted.
    """

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(64), unique=True)
    role: Mapped[UserRole] = mapped_column(_str_enum(UserRole, "user_role"))
    password_hash: Mapped[str] = mapped_column(String(255))
    active: Mapped[bool] = mapped_column(Boolean, default=True, server_default=true())
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow
    )


class Session(Base):
    """An opaque bearer session token, stored only as its SHA-256 hex.

    The raw token exists solely in the login response; it is never persisted
    or logged. Expired/orphaned sessions are treated as invalid on read —
    no background sweeper in v1.
    """

    __tablename__ = "sessions"

    id: Mapped[int] = mapped_column(primary_key=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class Asset(Base):
    """Generic, configurable entity keyed by its UNS-style path.

    ``path`` is the identity; its immutability is app-level policy (see
    docs/data-model.md), not a database constraint.
    """

    __tablename__ = "assets"

    id: Mapped[int] = mapped_column(primary_key=True)
    path: Mapped[str] = mapped_column(String(255), unique=True)
    display_name: Mapped[str] = mapped_column(String(255))
    description: Mapped[str | None] = mapped_column(Text)
    provenance: Mapped[AssetProvenance] = mapped_column(
        _str_enum(AssetProvenance, "asset_provenance")
    )
    retired: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default=false()
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )


class DowntimeEvent(Base):
    """A downtime interval on an asset; ``up_at IS NULL`` means ongoing.

    Duration is always derived (``up_at - down_at``), never stored.
    FS-Q1: at most one ongoing event per asset, enforced by a partial
    unique index at the database level on both engines.
    """

    __tablename__ = "downtime_events"
    __table_args__ = (
        Index(
            "uq_downtime_events_ongoing_per_asset",
            "asset_id",
            unique=True,
            sqlite_where=text("up_at IS NULL"),
            postgresql_where=text("up_at IS NULL"),
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    asset_id: Mapped[int] = mapped_column(ForeignKey("assets.id"))
    producer: Mapped[DowntimeProducer] = mapped_column(
        _str_enum(DowntimeProducer, "downtime_producer")
    )
    down_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    up_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    reported_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    ended_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"))


class WorkOrder(Base):
    """FS §5 pairing: ``manual`` origin ⇔ no downtime event; downtime
    origins ⇔ a downtime event — enforced by CHECK at the database level."""

    __tablename__ = "work_orders"
    __table_args__ = (
        CheckConstraint(
            "(origin = 'manual' AND downtime_event_id IS NULL) OR "
            "(origin IN ('uns_downtime', 'manual_downtime') "
            "AND downtime_event_id IS NOT NULL)",
            name="origin_event_pairing",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    asset_id: Mapped[int] = mapped_column(ForeignKey("assets.id"))
    origin: Mapped[WorkOrderOrigin] = mapped_column(
        _str_enum(WorkOrderOrigin, "work_order_origin")
    )
    downtime_event_id: Mapped[int | None] = mapped_column(
        ForeignKey("downtime_events.id")
    )
    title: Mapped[str] = mapped_column(String(255))
    description: Mapped[str | None] = mapped_column(Text)
    priority: Mapped[WorkOrderPriority] = mapped_column(
        _str_enum(WorkOrderPriority, "work_order_priority"),
        default=WorkOrderPriority.MEDIUM,
        server_default=WorkOrderPriority.MEDIUM.value,
    )
    status: Mapped[WorkOrderStatus] = mapped_column(
        _str_enum(WorkOrderStatus, "work_order_status"),
        default=WorkOrderStatus.OPEN,
        server_default=WorkOrderStatus.OPEN.value,
    )
    created_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    assigned_to: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    scheduled_start: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    expected_duration_minutes: Mapped[int | None]
    completion_notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )


class WorkOrderTransition(Base):
    """Audit trail: one row per status transition (including abandon notes).

    Transition logic / state-machine enforcement is a later task; only the
    table lands here.
    """

    __tablename__ = "work_order_transitions"

    id: Mapped[int] = mapped_column(primary_key=True)
    work_order_id: Mapped[int] = mapped_column(ForeignKey("work_orders.id"))
    from_status: Mapped[WorkOrderStatus] = mapped_column(
        _str_enum(WorkOrderStatus, "from_status")
    )
    to_status: Mapped[WorkOrderStatus] = mapped_column(
        _str_enum(WorkOrderStatus, "to_status")
    )
    at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    by_user: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    note: Mapped[str | None] = mapped_column(Text)
