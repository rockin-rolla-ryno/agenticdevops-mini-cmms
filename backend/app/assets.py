"""Assets API — registry browse + manual-asset lifecycle (FS §3, DEC-008).

Derived vs. authoritative: an asset's up/down ``status`` and every downtime
``duration_seconds`` are computed from ``downtime_events`` at read time —
never stored, no caching column, no denormalized flag.

Provenance rules (DEC-008): ``uns_discovered`` rows are a cache rebuilt from
UNS discovery — edit/retire are manual-only and 409 otherwise. All assets
share one UNS-style path namespace, so duplicate paths are surfaced as 409,
never mangled.
"""

from datetime import datetime
from typing import Literal

import sqlalchemy as sa
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict, field_validator
from sqlalchemy.exc import IntegrityError

from app import models
from app.auth import DbSession, require_user

# Router-level dependency: every assets endpoint requires a valid session
# (DEC-005 — server-side, per endpoint). Both roles may browse, register,
# edit, and retire (FS §2/§3; PM default flagged to the Architect).
router = APIRouter(
    prefix="/assets", tags=["assets"], dependencies=[Depends(require_user)]
)


class AssetOut(BaseModel):
    id: int
    path: str
    display_name: str
    description: str | None
    provenance: models.AssetProvenance
    retired: bool
    status: Literal["up", "down"]
    created_at: datetime
    updated_at: datetime


class DowntimeEventOut(BaseModel):
    id: int
    producer: models.DowntimeProducer
    down_at: datetime
    up_at: datetime | None
    duration_seconds: float | None
    reported_by: int | None
    ended_by: int | None


class WorkOrderSummaryOut(BaseModel):
    """Deliberately a summary — T-007 owns the full work-order surface."""

    id: int
    origin: models.WorkOrderOrigin
    title: str
    priority: models.WorkOrderPriority
    status: models.WorkOrderStatus
    created_at: datetime


class AssetDetailOut(AssetOut):
    downtime_history: list[DowntimeEventOut]
    work_orders: list[WorkOrderSummaryOut]


def _validate_path(raw: str) -> str:
    """FS §3 path shape: 1–255 chars, no leading/trailing '/', segments
    non-empty and non-whitespace. Raises ValueError → 422 via Pydantic."""
    path = raw.strip()
    if not 1 <= len(path) <= 255:
        raise ValueError("path must be 1-255 characters")
    if path.startswith("/") or path.endswith("/"):
        raise ValueError("path must not start or end with '/'")
    segments = path.split("/")
    if any(not segment.strip() for segment in segments):
        raise ValueError("path segments must be non-empty and non-whitespace")
    return path


class AssetCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    path: str
    display_name: str
    description: str | None = None

    @field_validator("path")
    @classmethod
    def _path_shape(cls, value: str) -> str:
        return _validate_path(value)


class AssetUpdate(BaseModel):
    """``path`` is deliberately absent — path immutability (FS §3) is enforced
    by the model having no such field; ``extra="forbid"`` turns a client
    sending ``path`` (or anything else) into a 422, not a silent drop."""

    model_config = ConfigDict(extra="forbid")

    display_name: str | None = None
    description: str | None = None


def _asset_out(asset: models.Asset, down: bool) -> AssetOut:
    return AssetOut(
        id=asset.id,
        path=asset.path,
        display_name=asset.display_name,
        description=asset.description,
        provenance=asset.provenance,
        retired=asset.retired,
        status="down" if down else "up",
        created_at=asset.created_at,
        updated_at=asset.updated_at,
    )


def _is_down(db: DbSession, asset_id: int) -> bool:
    ongoing = db.scalar(
        sa.select(models.DowntimeEvent.id)
        .where(
            models.DowntimeEvent.asset_id == asset_id,
            models.DowntimeEvent.up_at.is_(None),
        )
        .limit(1)
    )
    return ongoing is not None


def _get_asset_or_404(db: DbSession, asset_id: int) -> models.Asset:
    asset = db.get(models.Asset, asset_id)
    if asset is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="asset not found"
        )
    return asset


def _require_manual(asset: models.Asset) -> None:
    if asset.provenance is not models.AssetProvenance.MANUAL:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "uns_discovered assets are a cache of the UNS and cannot be "
                "edited or retired manually (DEC-008)"
            ),
        )


@router.get("", response_model=list[AssetOut])
def list_assets(db: DbSession, include_retired: bool = False) -> list[AssetOut]:
    """Flat list ordered by path — the renderer builds the hierarchy."""
    query = sa.select(models.Asset).order_by(models.Asset.path)
    if not include_retired:
        query = query.where(models.Asset.retired.is_(False))
    assets = db.scalars(query).all()

    # Derived status without N+1: one IN-clause query over the listed ids.
    down_ids: set[int] = set()
    if assets:
        down_ids = set(
            db.scalars(
                sa.select(models.DowntimeEvent.asset_id).where(
                    models.DowntimeEvent.asset_id.in_([a.id for a in assets]),
                    models.DowntimeEvent.up_at.is_(None),
                )
            ).all()
        )
    return [_asset_out(asset, asset.id in down_ids) for asset in assets]


@router.get("/{asset_id}", response_model=AssetDetailOut)
def asset_detail(asset_id: int, db: DbSession) -> AssetDetailOut:
    """Reachable even when retired (FS-Q7: hidden, not gone)."""
    asset = _get_asset_or_404(db, asset_id)

    events = db.scalars(
        sa.select(models.DowntimeEvent)
        .where(models.DowntimeEvent.asset_id == asset_id)
        .order_by(models.DowntimeEvent.down_at.desc(), models.DowntimeEvent.id.desc())
    ).all()
    work_orders = db.scalars(
        sa.select(models.WorkOrder)
        .where(models.WorkOrder.asset_id == asset_id)
        .order_by(models.WorkOrder.created_at.desc(), models.WorkOrder.id.desc())
    ).all()

    base = _asset_out(asset, any(event.up_at is None for event in events))
    return AssetDetailOut(
        **base.model_dump(),
        downtime_history=[
            DowntimeEventOut(
                id=event.id,
                producer=event.producer,
                down_at=event.down_at,
                up_at=event.up_at,
                duration_seconds=(
                    (event.up_at - event.down_at).total_seconds()
                    if event.up_at is not None
                    else None
                ),
                reported_by=event.reported_by,
                ended_by=event.ended_by,
            )
            for event in events
        ],
        work_orders=[
            WorkOrderSummaryOut(
                id=wo.id,
                origin=wo.origin,
                title=wo.title,
                priority=wo.priority,
                status=wo.status,
                created_at=wo.created_at,
            )
            for wo in work_orders
        ],
    )


@router.post("", response_model=AssetOut, status_code=status.HTTP_201_CREATED)
def register_asset(payload: AssetCreate, db: DbSession) -> AssetOut:
    duplicate = db.scalar(
        sa.select(models.Asset.id).where(models.Asset.path == payload.path)
    )
    if duplicate is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="an asset with this path already exists",
        )

    asset = models.Asset(
        path=payload.path,
        display_name=payload.display_name,
        description=payload.description,
        provenance=models.AssetProvenance.MANUAL,
        retired=False,
    )
    db.add(asset)
    try:
        db.commit()
    except IntegrityError as exc:  # race on the unique path constraint
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="an asset with this path already exists",
        ) from exc
    db.refresh(asset)
    return _asset_out(asset, down=False)


@router.patch("/{asset_id}", response_model=AssetOut)
def edit_asset(asset_id: int, payload: AssetUpdate, db: DbSession) -> AssetOut:
    """Manual assets only; editing a retired manual asset is allowed."""
    asset = _get_asset_or_404(db, asset_id)
    _require_manual(asset)

    # Omitted fields stay unchanged; an explicit `description: null` clears it.
    fields = payload.model_fields_set
    if "display_name" in fields and payload.display_name is not None:
        asset.display_name = payload.display_name
    if "description" in fields:
        asset.description = payload.description
    db.commit()
    db.refresh(asset)
    return _asset_out(asset, _is_down(db, asset.id))


@router.post("/{asset_id}/retire", response_model=AssetOut)
def retire_asset(asset_id: int, db: DbSession) -> AssetOut:
    """Manual assets only. Idempotent; no un-retire endpoint in v1 (decided)."""
    asset = _get_asset_or_404(db, asset_id)
    _require_manual(asset)

    if not asset.retired:
        asset.retired = True
        db.commit()
        db.refresh(asset)
    return _asset_out(asset, _is_down(db, asset.id))
