"""Auth integration tests — migrated tmp DBs + tmp users configs only.

Never touches backend/data/ or a real users config: every test overrides
CMMESS_DATABASE_URL and CMMESS_USERS_FILE onto tmp_path and clears the
cached engine/session factory around itself.
"""

import hashlib
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Annotated

import bcrypt
import pytest
import sqlalchemy as sa
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from app import config, db, models
from app.auth import require_planner
from app.main import app
from app.seeding import seed_users_from_config
from tests.test_migrations import upgrade_to_head

# rounds=4 (bcrypt minimum) keeps the suite fast; production uses gensalt().
PLANNER_PW = "planner-secret"
USER_PW = "tech-secret"
_PLANNER_HASH = bcrypt.hashpw(PLANNER_PW.encode(), bcrypt.gensalt(rounds=4)).decode()
_USER_HASH = bcrypt.hashpw(USER_PW.encode(), bcrypt.gensalt(rounds=4)).decode()


def _config_toml(accounts: list[tuple[str, str, str]]) -> str:
    blocks = [
        f'[[users]]\nusername = "{u}"\npassword_hash = "{h}"\nrole = "{r}"\n'
        for u, h, r in accounts
    ]
    return "\n".join(blocks)


DEFAULT_ACCOUNTS = [
    ("planner1", _PLANNER_HASH, "planner"),
    ("tech1", _USER_HASH, "user"),
]


@dataclass
class AuthEnv:
    database_url: str
    users_file: Path

    def write_config(self, accounts: list[tuple[str, str, str]]) -> None:
        self.users_file.write_text(_config_toml(accounts))


@pytest.fixture()
def auth_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[AuthEnv]:
    url = f"sqlite:///{tmp_path / 'auth.db'}"
    upgrade_to_head(url)
    users_file = tmp_path / "users.toml"
    env = AuthEnv(database_url=url, users_file=users_file)
    env.write_config(DEFAULT_ACCOUNTS)
    monkeypatch.setenv(config.ENV_DATABASE_URL, url)
    monkeypatch.setenv(config.ENV_USERS_FILE, str(users_file))
    db.get_engine.cache_clear()
    db.get_session_factory.cache_clear()
    yield env
    db.get_engine.cache_clear()
    db.get_session_factory.cache_clear()


@pytest.fixture()
def client(auth_env: AuthEnv) -> Iterator[TestClient]:
    # Entering the context runs the lifespan → seeds from the tmp config.
    with TestClient(app) as test_client:
        yield test_client


def _login(client: TestClient, username: str, password: str) -> str:
    response = client.post(
        "/auth/login", json={"username": username, "password": password}
    )
    assert response.status_code == 200
    token = response.json()["token"]
    assert isinstance(token, str)
    return token


def _bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def test_login_happy_path_and_token_stored_hashed_only(client: TestClient) -> None:
    response = client.post(
        "/auth/login", json={"username": "planner1", "password": PLANNER_PW}
    )
    assert response.status_code == 200
    body = response.json()
    assert body["user"]["username"] == "planner1"
    assert body["user"]["role"] == "planner"
    token = body["token"]

    me = client.get("/auth/me", headers=_bearer(token))
    assert me.status_code == 200
    assert me.json() == body["user"]

    # At rest: only the SHA-256 hex, never the raw token.
    with db.get_session_factory()() as session:
        stored = session.scalars(sa.select(models.Session.token_hash)).all()
        assert hashlib.sha256(token.encode()).hexdigest() in stored
        assert token not in stored
        assert all(len(h) == 64 for h in stored)


def test_login_failures_return_identical_401(client: TestClient) -> None:
    wrong_password = client.post(
        "/auth/login", json={"username": "planner1", "password": "not-it"}
    )
    unknown_user = client.post(
        "/auth/login", json={"username": "who-is-this", "password": "not-it"}
    )
    assert wrong_password.status_code == unknown_user.status_code == 401
    assert wrong_password.json() == unknown_user.json()
    # No secret or username leaks into the error body.
    assert "planner1" not in wrong_password.text
    assert "not-it" not in wrong_password.text


def test_missing_and_malformed_tokens_401(client: TestClient) -> None:
    assert client.get("/auth/me").status_code == 401
    assert client.get("/auth/me", headers=_bearer("nope")).status_code == 401
    assert (
        client.get("/auth/me", headers={"Authorization": "Basic abc"}).status_code
        == 401
    )


def test_deactivated_user_cannot_login_and_sessions_revoked(
    client: TestClient, auth_env: AuthEnv
) -> None:
    token = _login(client, "tech1", USER_PW)
    assert client.get("/auth/me", headers=_bearer(token)).status_code == 200

    # Remove tech1 from the config and re-seed (as an app restart would).
    auth_env.write_config([("planner1", _PLANNER_HASH, "planner")])
    seed_users_from_config()

    login_again = client.post(
        "/auth/login", json={"username": "tech1", "password": USER_PW}
    )
    assert login_again.status_code == 401
    # Existing session stops working too.
    assert client.get("/auth/me", headers=_bearer(token)).status_code == 401
    # The row is deactivated, never deleted.
    with db.get_session_factory()() as session:
        user = session.scalar(
            sa.select(models.User).where(models.User.username == "tech1")
        )
        assert user is not None and user.active is False

    # Re-adding the account reactivates it.
    auth_env.write_config(DEFAULT_ACCOUNTS)
    seed_users_from_config()
    assert (
        client.post(
            "/auth/login", json={"username": "tech1", "password": USER_PW}
        ).status_code
        == 200
    )


def test_logout_revokes_session(client: TestClient) -> None:
    token = _login(client, "tech1", USER_PW)
    assert client.post("/auth/logout", headers=_bearer(token)).status_code == 204
    assert client.get("/auth/me", headers=_bearer(token)).status_code == 401


def test_expired_session_rejected(client: TestClient) -> None:
    token = _login(client, "tech1", USER_PW)
    with db.get_session_factory()() as session:
        stored = session.scalar(
            sa.select(models.Session).where(
                models.Session.token_hash
                == hashlib.sha256(token.encode()).hexdigest()
            )
        )
        assert stored is not None
        stored.expires_at = datetime.now(UTC) - timedelta(hours=1)
        session.commit()
    assert client.get("/auth/me", headers=_bearer(token)).status_code == 401


# Minimal planner-gated route: no production domain route exists yet, so the
# enforcement pattern is exercised on a test app sharing the same env/DB.
planner_app = FastAPI()


@planner_app.get("/planner-only")
def planner_only(
    user: Annotated[models.User, Depends(require_planner)],
) -> dict[str, str]:
    return {"username": user.username}


def test_require_planner_enforces_role(client: TestClient) -> None:
    user_token = _login(client, "tech1", USER_PW)
    planner_token = _login(client, "planner1", PLANNER_PW)

    gate = TestClient(planner_app)
    # Valid session, wrong role → 403 (distinct from 401).
    assert gate.get("/planner-only", headers=_bearer(user_token)).status_code == 403
    ok = gate.get("/planner-only", headers=_bearer(planner_token))
    assert ok.status_code == 200
    assert ok.json() == {"username": "planner1"}
    assert gate.get("/planner-only").status_code == 401

    # FS-Q3: Planner ⊇ User — both roles pass require_user.
    assert client.get("/auth/me", headers=_bearer(user_token)).status_code == 200
    assert client.get("/auth/me", headers=_bearer(planner_token)).status_code == 200


def test_health_stays_unauthenticated(client: TestClient) -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_reseed_idempotent_and_applies_changes(
    client: TestClient, auth_env: AuthEnv
) -> None:
    seed_users_from_config()  # second run over the same config
    with db.get_session_factory()() as session:
        count = session.scalar(sa.select(sa.func.count()).select_from(models.User))
        assert count == 2

    # Change tech1's role and password in the config; re-seed applies both.
    new_hash = bcrypt.hashpw(b"rotated-secret", bcrypt.gensalt(rounds=4)).decode()
    auth_env.write_config(
        [("planner1", _PLANNER_HASH, "planner"), ("tech1", new_hash, "planner")]
    )
    seed_users_from_config()

    old_password = client.post(
        "/auth/login", json={"username": "tech1", "password": USER_PW}
    )
    assert old_password.status_code == 401
    token = _login(client, "tech1", "rotated-secret")
    me = client.get("/auth/me", headers=_bearer(token))
    assert me.json()["role"] == "planner"


def test_startup_fails_without_migrated_schema(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv(
        config.ENV_DATABASE_URL, f"sqlite:///{tmp_path / 'unmigrated.db'}"
    )
    monkeypatch.setenv(config.ENV_USERS_FILE, str(tmp_path / "users.toml"))
    db.get_engine.cache_clear()
    db.get_session_factory.cache_clear()
    try:
        with pytest.raises(RuntimeError, match="alembic upgrade head"):
            with TestClient(app):
                pass
    finally:
        db.get_engine.cache_clear()
        db.get_session_factory.cache_clear()
