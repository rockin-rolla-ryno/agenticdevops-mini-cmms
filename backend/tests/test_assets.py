"""Assets API integration tests — tmp-path DBs + tmp configs only
(the test_auth.py fixture pattern). UNS-discovered assets, downtime events,
and work orders are inserted directly via the ORM where no API creates
them yet (T-006/T-007).
"""

from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from pathlib import Path

import bcrypt
import pytest
import sqlalchemy as sa
from fastapi.testclient import TestClient

from app import config, db, models
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
    url = f"sqlite:///{tmp_path / 'assets.db'}"
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


def _register(
    client: TestClient,
    auth: dict[str, str],
    path: str = "plant/area/line/pump-1",
    display_name: str = "Pump 1",
) -> int:
    response = client.post(
        "/assets", json={"path": path, "display_name": display_name}, headers=auth
    )
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["provenance"] == "manual"
    assert body["retired"] is False
    asset_id = body["id"]
    assert isinstance(asset_id, int)
    return asset_id


def _insert_uns_asset(path: str = "plant/area/line/uns-1") -> int:
    with db.get_session_factory()() as session:
        asset = models.Asset(
            path=path,
            display_name="UNS Asset",
            provenance=models.AssetProvenance.UNS_DISCOVERED,
        )
        session.add(asset)
        session.commit()
        return asset.id


def _insert_downtime(
    asset_id: int,
    down_at: datetime,
    up_at: datetime | None,
) -> int:
    with db.get_session_factory()() as session:
        event = models.DowntimeEvent(
            asset_id=asset_id,
            producer=models.DowntimeProducer.UNS,
            down_at=down_at,
            up_at=up_at,
        )
        session.add(event)
        session.commit()
        return event.id


def test_all_endpoints_401_without_token(client: TestClient) -> None:
    assert client.get("/assets").status_code == 401
    assert client.get("/assets/1").status_code == 401
    assert client.post("/assets", json={}).status_code == 401
    assert client.patch("/assets/1", json={}).status_code == 401
    assert client.post("/assets/1/retire").status_code == 401


def test_both_roles_can_perform_every_action(
    client: TestClient, user_auth: dict[str, str], planner_auth: dict[str, str]
) -> None:
    for i, auth in enumerate((user_auth, planner_auth)):
        asset_id = _register(client, auth, path=f"plant/role-test/asset-{i}")
        assert client.get("/assets", headers=auth).status_code == 200
        assert client.get(f"/assets/{asset_id}", headers=auth).status_code == 200
        patched = client.patch(
            f"/assets/{asset_id}", json={"display_name": "Renamed"}, headers=auth
        )
        assert patched.status_code == 200
        assert (
            client.post(f"/assets/{asset_id}/retire", headers=auth).status_code == 200
        )


def test_register_appears_in_list_and_duplicate_409(
    client: TestClient, user_auth: dict[str, str]
) -> None:
    _register(client, user_auth, path="plant/a/pump")
    listed = client.get("/assets", headers=user_auth)
    assert listed.status_code == 200
    (entry,) = listed.json()
    assert entry["path"] == "plant/a/pump"
    assert entry["provenance"] == "manual"
    assert entry["status"] == "up"

    # Same path again — 409, no row created (any provenance, retired or not).
    duplicate = client.post(
        "/assets",
        json={"path": "plant/a/pump", "display_name": "Copycat"},
        headers=user_auth,
    )
    assert duplicate.status_code == 409
    with db.get_session_factory()() as session:
        count = session.scalar(sa.select(sa.func.count()).select_from(models.Asset))
        assert count == 1


def test_malformed_paths_rejected_422(
    client: TestClient, user_auth: dict[str, str]
) -> None:
    for bad_path in ["", "/a/b", "a/b/", "a//b", "a/ /b", "x" * 256]:
        response = client.post(
            "/assets",
            json={"path": bad_path, "display_name": "Nope"},
            headers=user_auth,
        )
        assert response.status_code == 422, f"path {bad_path!r} not rejected"
    with db.get_session_factory()() as session:
        count = session.scalar(sa.select(sa.func.count()).select_from(models.Asset))
        assert count == 0


def test_status_derived_from_ongoing_downtime(
    client: TestClient, user_auth: dict[str, str]
) -> None:
    asset_id = _register(client, user_auth)
    event_id = _insert_downtime(asset_id, down_at=datetime.now(UTC), up_at=None)

    listed = client.get("/assets", headers=user_auth).json()
    assert listed[0]["status"] == "down"
    detail = client.get(f"/assets/{asset_id}", headers=user_auth).json()
    assert detail["status"] == "down"

    # Close the event — status flips to "up" with no stored state anywhere.
    with db.get_session_factory()() as session:
        event = session.get(models.DowntimeEvent, event_id)
        assert event is not None
        event.up_at = datetime.now(UTC)
        session.commit()

    assert client.get("/assets", headers=user_auth).json()[0]["status"] == "up"
    assert (
        client.get(f"/assets/{asset_id}", headers=user_auth).json()["status"] == "up"
    )


def test_detail_history_durations_and_work_orders(
    client: TestClient, user_auth: dict[str, str]
) -> None:
    asset_id = _register(client, user_auth)
    base = datetime.now(UTC) - timedelta(days=1)
    _insert_downtime(asset_id, down_at=base, up_at=base + timedelta(minutes=30))
    _insert_downtime(asset_id, down_at=base + timedelta(hours=2), up_at=None)
    with db.get_session_factory()() as session:
        session.add(
            models.WorkOrder(
                asset_id=asset_id,
                origin=models.WorkOrderOrigin.MANUAL,
                title="Check bearings",
            )
        )
        session.commit()

    detail = client.get(f"/assets/{asset_id}", headers=user_auth).json()

    history = detail["downtime_history"]
    assert len(history) == 2
    # Newest first: the ongoing event leads.
    assert history[0]["up_at"] is None
    assert history[0]["duration_seconds"] is None
    assert history[1]["duration_seconds"] == pytest.approx(1800.0)

    (wo,) = detail["work_orders"]
    assert wo["title"] == "Check bearings"
    assert wo["origin"] == "manual"
    assert wo["priority"] == "medium"
    assert wo["status"] == "open"


def test_retired_hidden_by_default_but_not_gone(
    client: TestClient, user_auth: dict[str, str]
) -> None:
    asset_id = _register(client, user_auth)
    _insert_downtime(
        asset_id,
        down_at=datetime.now(UTC) - timedelta(hours=1),
        up_at=datetime.now(UTC),
    )
    retired = client.post(f"/assets/{asset_id}/retire", headers=user_auth)
    assert retired.status_code == 200

    assert client.get("/assets", headers=user_auth).json() == []
    with_retired = client.get(
        "/assets", params={"include_retired": "true"}, headers=user_auth
    ).json()
    assert [a["id"] for a in with_retired] == [asset_id]
    assert with_retired[0]["retired"] is True

    # Detail (including history) still 200 — hidden, not gone (FS-Q7).
    detail = client.get(f"/assets/{asset_id}", headers=user_auth)
    assert detail.status_code == 200
    assert len(detail.json()["downtime_history"]) == 1

    # A retired manual asset can still be edited.
    patched = client.patch(
        f"/assets/{asset_id}", json={"display_name": "Still here"}, headers=user_auth
    )
    assert patched.status_code == 200
    assert patched.json()["display_name"] == "Still here"


def test_uns_discovered_edit_and_retire_409(
    client: TestClient, user_auth: dict[str, str]
) -> None:
    asset_id = _insert_uns_asset()

    patched = client.patch(
        f"/assets/{asset_id}", json={"display_name": "Hijack"}, headers=user_auth
    )
    retired = client.post(f"/assets/{asset_id}/retire", headers=user_auth)
    assert patched.status_code == 409
    assert retired.status_code == 409
    with db.get_session_factory()() as session:
        asset = session.get(models.Asset, asset_id)
        assert asset is not None
        assert asset.display_name == "UNS Asset"
        assert asset.retired is False


def test_patch_cannot_change_path_any_shape(
    client: TestClient, user_auth: dict[str, str]
) -> None:
    asset_id = _register(client, user_auth, path="plant/a/fixed")
    for payload in (
        {"path": "plant/a/moved"},
        {"path": "plant/a/moved", "display_name": "X"},
        {"unknown_field": 1},
    ):
        response = client.patch(
            f"/assets/{asset_id}", json=payload, headers=user_auth
        )
        assert response.status_code == 422, f"payload {payload!r} not rejected"
    detail = client.get(f"/assets/{asset_id}", headers=user_auth).json()
    assert detail["path"] == "plant/a/fixed"


def test_patch_field_semantics(client: TestClient, user_auth: dict[str, str]) -> None:
    asset_id = _register(client, user_auth)
    client.patch(
        f"/assets/{asset_id}", json={"description": "greasy"}, headers=user_auth
    )

    # Omitted fields unchanged.
    patched = client.patch(
        f"/assets/{asset_id}", json={"display_name": "New name"}, headers=user_auth
    ).json()
    assert patched["display_name"] == "New name"
    assert patched["description"] == "greasy"

    # Explicit null clears description.
    cleared = client.patch(
        f"/assets/{asset_id}", json={"description": None}, headers=user_auth
    ).json()
    assert cleared["description"] is None
    assert cleared["display_name"] == "New name"


def test_retire_idempotent(client: TestClient, user_auth: dict[str, str]) -> None:
    asset_id = _register(client, user_auth)
    first = client.post(f"/assets/{asset_id}/retire", headers=user_auth)
    second = client.post(f"/assets/{asset_id}/retire", headers=user_auth)
    assert first.status_code == second.status_code == 200
    assert second.json()["retired"] is True


def test_unknown_asset_404(client: TestClient, user_auth: dict[str, str]) -> None:
    assert client.get("/assets/9999", headers=user_auth).status_code == 404
    assert (
        client.patch("/assets/9999", json={}, headers=user_auth).status_code == 404
    )
    assert client.post("/assets/9999/retire", headers=user_auth).status_code == 404
