"""Auth surface + the standing server-side enforcement pattern (DEC-005).

Every future protected endpoint uses ``require_user`` or ``require_planner``
as a dependency — a hidden renderer control is never access control.
Planner ⊇ User (FS-Q3): a planner session passes both dependencies.

Opaque bearer tokens: the raw token exists only in the login response;
at rest it is a SHA-256 hex in ``sessions.token_hash``. Passwords, hashes,
and tokens are never logged and never appear in error bodies.
"""

import hashlib
import secrets
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Annotated

import bcrypt
import sqlalchemy as sa
from fastapi import APIRouter, Depends, Header, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session as OrmSession

from app import models
from app.config import get_session_ttl_hours
from app.db import get_session_factory

router = APIRouter(prefix="/auth", tags=["auth"])

# Verified when the username is unknown so login latency does not reveal
# whether an account exists. Hash of a fixed dummy string — not a secret.
_TIMING_PARITY_HASH = b"$2b$12$Z7kRiBKkU6RnR4.0VZ7bS.JIvh0/5rpM3E25d1W1sOnKFOxLLEm06"


class LoginRequest(BaseModel):
    username: str
    password: str


class UserOut(BaseModel):
    id: int
    username: str
    role: models.UserRole


class LoginResponse(BaseModel):
    token: str
    user: UserOut


def get_db() -> Iterator[OrmSession]:
    """Per-request ORM session (FastAPI caches it within a request)."""
    with get_session_factory()() as session:
        yield session


DbSession = Annotated[OrmSession, Depends(get_db)]


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _as_utc(value: datetime) -> datetime:
    """Normalize DB datetimes: SQLite returns naive, Postgres aware; all UTC."""
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value


def _login_failed() -> HTTPException:
    # Identical status + body for every failure mode: no username enumeration.
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="invalid username or password",
    )


def _unauthorized() -> HTTPException:
    # Identical for missing/malformed/unknown/expired token and inactive user.
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="invalid or expired session",
        headers={"WWW-Authenticate": "Bearer"},
    )


def _bearer_token(
    authorization: Annotated[str | None, Header()] = None,
) -> str:
    if authorization is None or not authorization.startswith("Bearer "):
        raise _unauthorized()
    token = authorization.removeprefix("Bearer ").strip()
    if not token:
        raise _unauthorized()
    return token


@dataclass
class AuthContext:
    user: models.User
    session: models.Session


def get_auth_context(
    db: DbSession, token: Annotated[str, Depends(_bearer_token)]
) -> AuthContext:
    """Resolve a bearer token to an active user + live session, else 401."""
    session = db.scalar(
        sa.select(models.Session).where(models.Session.token_hash == hash_token(token))
    )
    if session is None:
        raise _unauthorized()
    if _as_utc(session.expires_at) <= datetime.now(UTC):
        raise _unauthorized()
    user = db.get(models.User, session.user_id)
    if user is None or not user.active:
        raise _unauthorized()
    return AuthContext(user=user, session=session)


def require_user(
    ctx: Annotated[AuthContext, Depends(get_auth_context)],
) -> models.User:
    """Any valid session of an active user — both roles pass."""
    return ctx.user


def require_planner(
    ctx: Annotated[AuthContext, Depends(get_auth_context)],
) -> models.User:
    """Planner only. FS-Q3: Planner ⊇ User, so planners also pass require_user."""
    if ctx.user.role is not models.UserRole.PLANNER:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="planner role required"
        )
    return ctx.user


@router.post("/login", response_model=LoginResponse)
def login(payload: LoginRequest, db: DbSession) -> LoginResponse:
    user = db.scalar(
        sa.select(models.User).where(models.User.username == payload.username)
    )
    if user is None:
        bcrypt.checkpw(payload.password.encode("utf-8"), _TIMING_PARITY_HASH)
        raise _login_failed()
    if not bcrypt.checkpw(
        payload.password.encode("utf-8"), user.password_hash.encode("utf-8")
    ):
        raise _login_failed()
    if not user.active:
        raise _login_failed()

    token = secrets.token_urlsafe(32)
    now = datetime.now(UTC)
    db.add(
        models.Session(
            token_hash=hash_token(token),
            user_id=user.id,
            created_at=now,
            expires_at=now + timedelta(hours=get_session_ttl_hours()),
        )
    )
    db.commit()
    return LoginResponse(
        token=token,
        user=UserOut(id=user.id, username=user.username, role=user.role),
    )


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(
    ctx: Annotated[AuthContext, Depends(get_auth_context)], db: DbSession
) -> None:
    db.delete(ctx.session)
    db.commit()


@router.get("/me", response_model=UserOut)
def me(user: Annotated[models.User, Depends(require_user)]) -> UserOut:
    """The protected-endpoint exemplar."""
    return UserOut(id=user.id, username=user.username, role=user.role)
