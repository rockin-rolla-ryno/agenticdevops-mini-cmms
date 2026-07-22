"""Downtime events API + work-order seeding (FS §4) — the core primitive.

``record_downtime`` is the reusable service: it creates a downtime event and
its seeded work order atomically, with no HTTP machinery, so the future UNS
ingestion task can call it directly from the MQTT client with
``producer="uns"``. The FS-Q1 partial unique index is the race backstop; the
service adds the friendly, pointed rejection.

Explicit independence (FS §4): ending a downtime event never touches its
work order's status, and nothing here ends events from work-order code. The
event log records what the asset did; the WO records what people did.
"""

from datetime import UTC, datetime
from typing import Annotated

import sqlalchemy as sa
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session as OrmSession

from app import models
from app.assets import DowntimeEventOut, WorkOrderSummaryOut
from app.auth import DbSession, require_user

router = APIRouter(tags=["downtime"])


class OngoingDowntimeError(Exception):
    """FS-Q1: the asset already has an ongoing downtime event.

    Carries pointers to the ongoing event and its seeded work order so
    callers can reject with actionable detail.
    """

    def __init__(self, ongoing_event_id: int, work_order_id: int | None) -> None:
        super().__init__("asset already has an ongoing downtime event")
        self.ongoing_event_id = ongoing_event_id
        self.work_order_id = work_order_id


def _ongoing_event(db: OrmSession, asset_id: int) -> models.DowntimeEvent | None:
    return db.scalar(
        sa.select(models.DowntimeEvent).where(
            models.DowntimeEvent.asset_id == asset_id,
            models.DowntimeEvent.up_at.is_(None),
        )
    )


def _work_order_for_event(db: OrmSession, event_id: int) -> int | None:
    return db.scalar(
        sa.select(models.WorkOrder.id).where(
            models.WorkOrder.downtime_event_id == event_id
        )
    )


def _ongoing_conflict(
    db: OrmSession, ongoing: models.DowntimeEvent
) -> OngoingDowntimeError:
    return OngoingDowntimeError(
        ongoing_event_id=ongoing.id,
        work_order_id=_work_order_for_event(db, ongoing.id),
    )


def record_downtime(
    db: OrmSession,
    asset: models.Asset,
    producer: models.DowntimeProducer,
    reported_by: int | None,
) -> tuple[models.DowntimeEvent, models.WorkOrder]:
    """Create a downtime event and its seeded work order — both or neither.

    ``reported_by`` is the reporting user's id for manual producers and
    ``None`` for UNS (system). Raises :class:`OngoingDowntimeError` when the
    asset already has an ongoing event (FS-Q1), including on the insert race
    where two callers pass the pre-check and the partial unique index fires.
    """
    ongoing = _ongoing_event(db, asset.id)
    if ongoing is not None:
        raise _ongoing_conflict(db, ongoing)

    now = datetime.now(UTC)
    event = models.DowntimeEvent(
        asset_id=asset.id,
        producer=producer,
        down_at=now,
        reported_by=reported_by,
    )
    db.add(event)
    try:
        db.flush()  # assigns event.id; the FS-Q1 index fires here on a race
    except IntegrityError:
        db.rollback()
        ongoing = _ongoing_event(db, asset.id)
        if ongoing is None:  # pragma: no cover — the conflicting event
            raise  # vanished between rollback and re-query; surface loudly
        raise _ongoing_conflict(db, ongoing) from None

    work_order = models.WorkOrder(
        asset_id=asset.id,
        origin=(
            models.WorkOrderOrigin.MANUAL_DOWNTIME
            if producer is models.DowntimeProducer.MANUAL
            else models.WorkOrderOrigin.UNS_DOWNTIME
        ),
        downtime_event_id=event.id,
        title=f"Downtime — {asset.path}",
        created_by=reported_by,
    )
    db.add(work_order)
    db.commit()
    db.refresh(event)
    db.refresh(work_order)
    return event, work_order


def _event_out(event: models.DowntimeEvent) -> DowntimeEventOut:
    return DowntimeEventOut(
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


class DowntimeReportOut(BaseModel):
    event: DowntimeEventOut
    work_order: WorkOrderSummaryOut


@router.post(
    "/assets/{asset_id}/downtime-events",
    response_model=DowntimeReportOut,
    status_code=status.HTTP_201_CREATED,
)
def report_downtime(
    asset_id: int,
    db: DbSession,
    user: Annotated[models.User, Depends(require_user)],
) -> DowntimeReportOut:
    """Report an asset down (either role). ``down_at`` is always server
    time — no backdating in v1 (decided absence)."""
    asset = db.get(models.Asset, asset_id)
    if asset is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="asset not found"
        )
    if asset.retired:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="asset is retired — no new activity on retired assets",
        )

    try:
        event, work_order = record_downtime(
            db, asset, models.DowntimeProducer.MANUAL, reported_by=user.id
        )
    except OngoingDowntimeError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "message": "asset already has an ongoing downtime event",
                "ongoing_event_id": exc.ongoing_event_id,
                "work_order_id": exc.work_order_id,
            },
        ) from exc

    return DowntimeReportOut(
        event=_event_out(event),
        work_order=WorkOrderSummaryOut(
            id=work_order.id,
            origin=work_order.origin,
            title=work_order.title,
            priority=work_order.priority,
            status=work_order.status,
            created_at=work_order.created_at,
        ),
    )


@router.post("/downtime-events/{event_id}/end", response_model=DowntimeEventOut)
def end_downtime(
    event_id: int,
    db: DbSession,
    user: Annotated[models.User, Depends(require_user)],
) -> DowntimeEventOut:
    """Mark the asset back up (either role) — manual-producer events only.

    Not idempotent: re-ending would silently rewrite ``ended_by``
    attribution, so an already-ended event is a 409.
    """
    event = db.get(models.DowntimeEvent, event_id)
    if event is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="downtime event not found"
        )
    if event.producer is not models.DowntimeProducer.MANUAL:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "uns-producer events end via the UNS up-signal, not manually"
            ),
        )
    if event.up_at is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="downtime event is already ended",
        )

    event.up_at = datetime.now(UTC)
    event.ended_by = user.id
    db.commit()
    db.refresh(event)
    return _event_out(event)
