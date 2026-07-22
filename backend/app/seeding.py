"""Account seeding from the TOML users config (FS-Q5).

Runs at FastAPI startup (lifespan), never at import. Semantics:
upsert by username (create missing; update role/hash to match the config;
reactivate if present) and deactivate any DB user absent from the config.
Rows are never deleted — history FKs stay valid.
"""

import tomllib
from dataclasses import dataclass
from pathlib import Path

import sqlalchemy as sa

from app import models
from app.config import get_users_file
from app.db import get_engine, get_session_factory

MIGRATE_HINT = (
    "database schema is not migrated — run `alembic upgrade head` from backend/ "
    "before starting the app"
)


@dataclass(frozen=True)
class SeedAccount:
    username: str
    password_hash: str
    role: models.UserRole


def load_accounts(path: Path) -> list[SeedAccount]:
    """Parse and validate the users TOML. Raises with operator-clear messages."""
    if not path.is_file():
        raise RuntimeError(
            f"users config not found at {path} — copy "
            "backend/config/users.example.toml to that path (or set "
            "CMMESS_USERS_FILE) and fill in real accounts"
        )
    with path.open("rb") as fh:
        data = tomllib.load(fh)

    raw_users = data.get("users")
    if not isinstance(raw_users, list) or not raw_users:
        raise RuntimeError(f"users config {path} must define at least one [[users]]")

    accounts: list[SeedAccount] = []
    for i, entry in enumerate(raw_users):
        if not isinstance(entry, dict):
            raise RuntimeError(f"users config {path}: entry {i} is not a table")
        try:
            username = entry["username"]
            password_hash = entry["password_hash"]
            role = entry["role"]
        except KeyError as exc:
            raise RuntimeError(
                f"users config {path}: entry {i} is missing key {exc}"
            ) from exc
        if not isinstance(username, str) or not isinstance(password_hash, str):
            raise RuntimeError(
                f"users config {path}: entry {i}: username and password_hash "
                "must be strings"
            )
        try:
            parsed_role = models.UserRole(role)
        except ValueError as exc:
            raise RuntimeError(
                f"users config {path}: entry {i}: role must be one of "
                f"{[r.value for r in models.UserRole]}"
            ) from exc
        accounts.append(
            SeedAccount(
                username=username, password_hash=password_hash, role=parsed_role
            )
        )

    usernames = [a.username for a in accounts]
    if len(usernames) != len(set(usernames)):
        raise RuntimeError(f"users config {path}: duplicate usernames")
    return accounts


def _ensure_schema_migrated(engine: sa.Engine) -> None:
    inspector = sa.inspect(engine)
    if not inspector.has_table("users") or not inspector.has_table("sessions"):
        raise RuntimeError(MIGRATE_HINT)
    user_columns = {col["name"] for col in inspector.get_columns("users")}
    if "active" not in user_columns:
        raise RuntimeError(MIGRATE_HINT)


def seed_users_from_config() -> None:
    """Startup entry point: validate schema, then apply the config."""
    _ensure_schema_migrated(get_engine())
    accounts = load_accounts(get_users_file())
    factory = get_session_factory()
    with factory() as session:
        seeded_names = set()
        for account in accounts:
            seeded_names.add(account.username)
            user = session.scalar(
                sa.select(models.User).where(models.User.username == account.username)
            )
            if user is None:
                session.add(
                    models.User(
                        username=account.username,
                        password_hash=account.password_hash,
                        role=account.role,
                        active=True,
                    )
                )
            else:
                user.password_hash = account.password_hash
                user.role = account.role
                user.active = True

        # Deactivate (never delete) DB users absent from the config.
        for user in session.scalars(
            sa.select(models.User).where(models.User.active.is_(True))
        ):
            if user.username not in seeded_names:
                user.active = False

        session.commit()
