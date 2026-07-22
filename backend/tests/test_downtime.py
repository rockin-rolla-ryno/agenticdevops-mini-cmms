"""Downtime API + WO-seeding integration tests — tmp-path DBs only,
following the existing fixture pattern.
"""

from collections.abc import Iterator
from pathlib import Path

import bcrypt
import pytest
import sqlalchemy as sa
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session as OrmSession

from app import config, db, downtime, models
from app.downtime import OngoingDowntimeError, record_downtime
from app.main import app
from tests.test_migrations import upgrade_to_head

PLANNER_PW = "planner-secret"
USER_PW = "tech-secret"
_PLANNER_HASH = bcrypt.hashpw(PLANNER_PW.encode(), bcrypt.gensalt(rounds=4)).decode()
_USER_HASH = bcrypt.hashpw(USER_PW.encode(), bcrypt.gensalt(rounds=4)).decode()

_USERS_TOML = f'''
[[users]]
username = "planner1"
password_hash = "{_PLANNER_HASH}"
role = "planner"

[[users]]
username = "tech1"
password_hash = "{_USER_HASH}"
role = "user"
'''


@pytest.fixture()
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    url = f"sqlite:///{tmp_path / 'downtime.db'}"
    upgrade_to_head(url)
    users_file = tmp_path / "users.toml"
    users_file.write_text(_USERS_TOML)
    monkeypatch.setenv(config.ENV_DATABASE_URL, url)
    monkeypatch.setenv(config.ENV_USERS_FILE, str(users_file))
    db.get_engine.cache_clear()
    db.get_session_factory.cache_clear()
    with TestClient(app) as test_client:
        yield test_client
    db.get_engine.cache_clear()
    db.get_session_factory.cache_clear()


def _login(client: TestClient, username: str, password: str) -> dict[str, str]:
    response = client.post(
        "/auth/login", json={"username": username, "password": password}
    )
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['token']}"}


@pytest.fixture()
def user_auth(client: TestClient) -> dict[str, str]:
    return _login(client, "tech1", USER_PW)


@pytest.fixture()
def planner_auth(client: TestClient) -> dict[str, str]:
    return _login(client, "planner1", PLANNER_PW)


def _register_asset(
    client: TestClient, auth: dict[str, str], path: str = "plant/line/mixer-1"
) -> int:
    response = client.post(
        "/assets", json={"path": path, "display_name": "Mixer"}, headers=auth
    )
    assert response.status_code == 201
    asset_id = response.json()["id"]
    assert isinstance(asset_id, int)
    return asset_id


def _counts() -> tuple[int, int]:
    with db.get_session_factory()() as session:
        events = session.scalar(
            sa.select(sa.func.count()).select_from(models.DowntimeEvent)
        )
        wos = session.scalar(sa.select(sa.func.count()).select_from(models.WorkOrder))
        assert events is not None and wos is not None
        return events, wos


def test_endpoints_401_without_token(client: TestClient) -> None:
    assert client.post("/assets/1/downtime-events").status_code == 401
    assert client.post("/downtime-events/1/end").status_code == 401


def test_both_roles_can_report_and_end(
    client: TestClient, user_auth: dict[str, str], planner_auth: dict[str, str]
) -> None:
    for i, auth in enumerate((user_auth, planner_auth)):
        asset_id = _register_asset(client, auth, path=f"plant/roles/asset-{i}")
        reported = client.post(f"/assets/{asset_id}/downtime-events", headers=auth)
        assert reported.status_code == 201
        event_id = reported.json()["event"]["id"]
        ended = client.post(f"/downtime-events/{event_id}/end", headers=auth)
        assert ended.status_code == 200


def test_report_seeds_event_and_wo_atomically(
    client: TestClient, user_auth: dict[str, str]
) -> None:
    asset_id = _register_asset(client, user_auth, path="plant/line/press-9")
    response = client.post(f"/assets/{asset_id}/downtime-events", headers=user_auth)
    assert response.status_code == 201
    body = response.json()

    event = body["event"]
    assert event["producer"] == "manual"
    assert event["up_at"] is None
    assert event["duration_seconds"] is None

    wo = body["work_order"]
    assert wo["origin"] == "manual_downtime"
    assert wo["title"] == "Downtime — plant/line/press-9"
    assert wo["priority"] == "medium"
    assert wo["status"] == "open"

    with db.get_session_factory()() as session:
        me = session.scalar(
            sa.select(models.User).where(models.User.username == "tech1")
        )
        assert me is not None
        stored_wo = session.get(models.WorkOrder, wo["id"])
        assert stored_wo is not None
        assert stored_wo.downtime_event_id == event["id"]
        assert stored_wo.created_by == me.id
        stored_event = session.get(models.DowntimeEvent, event["id"])
        assert stored_event is not None
        assert stored_event.reported_by == me.id
    assert _counts() == (1, 1)

    # Derived status (T-005 endpoints) flips to "down".
    assert (
        client.get(f"/assets/{asset_id}", headers=user_auth).json()["status"]
        == "down"
    )


def test_second_report_409_pointer_then_new_wo_after_end(
    client: TestClient, user_auth: dict[str, str]
) -> None:
    asset_id = _register_asset(client, user_auth)
    first = client.post(f"/assets/{asset_id}/downtime-events", headers=user_auth)
    event_id = first.json()["event"]["id"]
    wo_id = first.json()["work_order"]["id"]

    second = client.post(f"/assets/{asset_id}/downtime-events", headers=user_auth)
    assert second.status_code == 409
    assert second.json()["detail"] == {
        "message": "asset already has an ongoing downtime event",
        "ongoing_event_id": event_id,
        "work_order_id": wo_id,
    }
    assert _counts() == (1, 1)  # no rows created by the rejection

    # End the event; a new report succeeds and seeds a NEW WO even though
    # the prior WO is still open (FS-Q2).
    assert (
        client.post(f"/downtime-events/{event_id}/end", headers=user_auth).status_code
        == 200
    )
    third = client.post(f"/assets/{asset_id}/downtime-events", headers=user_auth)
    assert third.status_code == 201
    assert third.json()["work_order"]["id"] != wo_id
    assert _counts() == (2, 2)
    with db.get_session_factory()() as session:
        statuses = session.scalars(sa.select(models.WorkOrder.status)).all()
        assert list(statuses) == [models.WorkOrderStatus.OPEN] * 2


def test_record_downtime_uns_reuse_path(
    client: TestClient, user_auth: dict[str, str]
) -> None:
    """Direct service call, no HTTP — the UNS ingestion reuse path."""
    asset_id = _register_asset(client, user_auth, path="plant/uns/oven-1")
    with db.get_session_factory()() as session:
        asset = session.get(models.Asset, asset_id)
        assert asset is not None
        event, work_order = record_downtime(
            session, asset, models.DowntimeProducer.UNS, reported_by=None
        )
        assert event.producer is models.DowntimeProducer.UNS
        assert event.reported_by is None
        assert work_order.origin is models.WorkOrderOrigin.UNS_DOWNTIME
        assert work_order.created_by is None
        assert work_order.downtime_event_id == event.id

        # FS-Q1 applies to the direct path too.
        with pytest.raises(OngoingDowntimeError) as exc_info:
            record_downtime(
                session, asset, models.DowntimeProducer.UNS, reported_by=None
            )
        assert exc_info.value.ongoing_event_id == event.id
        assert exc_info.value.work_order_id == work_order.id


def test_end_sets_fields_and_leaves_wo_untouched(
    client: TestClient, user_auth: dict[str, str]
) -> None:
    asset_id = _register_asset(client, user_auth)
    reported = client.post(f"/assets/{asset_id}/downtime-events", headers=user_auth)
    event_id = reported.json()["event"]["id"]
    wo_id = reported.json()["work_order"]["id"]

    ended = client.post(f"/downtime-events/{event_id}/end", headers=user_auth)
    assert ended.status_code == 200
    body = ended.json()
    assert body["up_at"] is not None
    assert body["duration_seconds"] is not None and body["duration_seconds"] >= 0
    with db.get_session_factory()() as session:
        me = session.scalar(
            sa.select(models.User).where(models.User.username == "tech1")
        )
        stored = session.get(models.DowntimeEvent, event_id)
        assert stored is not None and me is not None
        assert stored.ended_by == me.id
        # Explicit independence: the linked WO's status is untouched.
        wo = session.get(models.WorkOrder, wo_id)
        assert wo is not None
        assert wo.status is models.WorkOrderStatus.OPEN

    assert (
        client.get(f"/assets/{asset_id}", headers=user_auth).json()["status"] == "up"
    )


def test_end_uns_event_409(client: TestClient, user_auth: dict[str, str]) -> None:
    asset_id = _register_asset(client, user_auth)
    with db.get_session_factory()() as session:
        asset = session.get(models.Asset, asset_id)
        assert asset is not None
        event, _ = record_downtime(
            session, asset, models.DowntimeProducer.UNS, reported_by=None
        )
        event_id = event.id

    response = client.post(f"/downtime-events/{event_id}/end", headers=user_auth)
    assert response.status_code == 409
    with db.get_session_factory()() as session:
        stored = session.get(models.DowntimeEvent, event_id)
        assert stored is not None
        assert stored.up_at is None and stored.ended_by is None


def test_end_already_ended_409_preserves_attribution(
    client: TestClient, user_auth: dict[str, str], planner_auth: dict[str, str]
) -> None:
    asset_id = _register_asset(client, user_auth)
    event_id = client.post(
        f"/assets/{asset_id}/downtime-events", headers=user_auth
    ).json()["event"]["id"]
    first = client.post(f"/downtime-events/{event_id}/end", headers=user_auth)
    assert first.status_code == 200
    original_up_at = first.json()["up_at"]

    again = client.post(f"/downtime-events/{event_id}/end", headers=planner_auth)
    assert again.status_code == 409
    with db.get_session_factory()() as session:
        stored = session.get(models.DowntimeEvent, event_id)
        me = session.scalar(
            sa.select(models.User).where(models.User.username == "tech1")
        )
        assert stored is not None and me is not None
        assert stored.ended_by == me.id  # attribution not rewritten
        assert stored.up_at is not None
        assert stored.up_at.isoformat().startswith(original_up_at[:19])


def test_report_on_retired_asset_409_and_unknowns_404(
    client: TestClient, user_auth: dict[str, str]
) -> None:
    asset_id = _register_asset(client, user_auth)
    assert (
        client.post(f"/assets/{asset_id}/retire", headers=user_auth).status_code
        == 200
    )
    retired_report = client.post(
        f"/assets/{asset_id}/downtime-events", headers=user_auth
    )
    assert retired_report.status_code == 409
    assert _counts() == (0, 0)
    assert (
        client.post("/assets/9999/downtime-events", headers=user_auth).status_code
        == 404
    )
    unknown_end = client.post("/downtime-events/9999/end", headers=user_auth)
    assert unknown_end.status_code == 404


def test_integrity_race_surfaces_as_409_pointer(
    client: TestClient, user_auth: dict[str, str], monkeypatch: pytest.MonkeyPatch
) -> None:
    """Two requests pass the pre-check: the FS-Q1 index fires, and the
    rejection is the same 409 pointer body — not a 500."""
    asset_id = _register_asset(client, user_auth)
    reported = client.post(f"/assets/{asset_id}/downtime-events", headers=user_auth)
    event_id = reported.json()["event"]["id"]
    wo_id = reported.json()["work_order"]["id"]

    # Simulate the race: the pre-check misses once (as if the competing
    # insert landed between check and flush), then behaves normally so the
    # post-IntegrityError re-query finds the ongoing event.
    real_ongoing = downtime._ongoing_event
    calls = {"n": 0}

    def flaky_ongoing(
        db_session: OrmSession, asset_id_: int
    ) -> models.DowntimeEvent | None:
        calls["n"] += 1
        if calls["n"] == 1:
            return None
        return real_ongoing(db_session, asset_id_)

    monkeypatch.setattr(downtime, "_ongoing_event", flaky_ongoing)

    raced = client.post(f"/assets/{asset_id}/downtime-events", headers=user_auth)
    assert raced.status_code == 409
    assert raced.json()["detail"] == {
        "message": "asset already has an ongoing downtime event",
        "ongoing_event_id": event_id,
        "work_order_id": wo_id,
    }
    assert calls["n"] >= 2  # the pre-check missed and the re-query ran
    assert _counts() == (1, 1)  # no orphaned half-pair
