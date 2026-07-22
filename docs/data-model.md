# CMMess — Data Model

> **Schema authority** (per `docs/contract-sync.md`, row 3): when the persisted
> schema changes, the SQLAlchemy models (`backend/app/models.py`), the Alembic
> migration, and **this doc** move in the same commit (Rule 12). If this page and
> the models disagree, that's a bug — fix the commit, not the reader.

Behavioral source: `docs/functional-spec.md` (FS). Architectural constraints:
`docs/architecture-facts.md` § Persistence & migrations, DEC-006 (dual-engine),
DEC-008 (asset authority by provenance).

## Conventions

- **All timestamps are UTC** (`DateTime(timezone=True)`; SQLite stores naive
  values — the UTC convention is application-wide).
- **Enum-valued columns are short strings (`VARCHAR(32)`) constrained by CHECK
  constraints, typed in Python as `StrEnum`** — never native Postgres `ENUM`
  types. Why: the same DDL runs on SQLite and Postgres, and adding a value is
  an additive CHECK swap, never an `ALTER TYPE` (a deliberate dual-engine
  decision, DEC-006).
- Integer surrogate PKs everywhere; domain identity (e.g. asset `path`) is a
  separate unique column.
- Constraint naming follows the metadata naming convention in `models.py`
  (`ck_<table>_<name>`, `uq_<table>_<col>`, `fk_<table>_<col>_<reftable>`), so
  future SQLite batch migrations can target constraints by name.
- SQLite enforces foreign keys only when asked: the app engine (`app/db.py`)
  issues `PRAGMA foreign_keys=ON` per connection so both engines enforce
  referential integrity identically.

## Tables

### `users`

Accounts are **seeded from a TOML config** (FS-Q5), not self-registered.

| Column | Type | Constraints |
|---|---|---|
| `id` | int | PK |
| `username` | str(64) | unique, not null |
| `role` | str(32) | CHECK in (`user`, `planner`) — the two FS roles |
| `password_hash` | str(255) | not null — bcrypt |
| `active` | bool | not null, default true (0002) — seeded-config revocation flag |
| `created_at` | datetime (UTC) | not null |

**Seeding semantics (runs in the FastAPI lifespan at startup, never on
import):** the TOML at `CMMESS_USERS_FILE` (default `backend/config/users.toml`,
gitignored; committed example: `backend/config/users.example.toml`) is upserted
by username — missing accounts are created, existing ones get role/hash updated
and are reactivated. Any DB user **absent from the config is deactivated,
never deleted** — history FKs stay valid, but the account can no longer log in
and its existing sessions stop resolving. If the schema isn't migrated,
startup fails with an operator message to run `alembic upgrade head`.
Hash generation: `python -m app.hash_password`.

### `sessions`

Opaque bearer sessions (T-004). The raw token exists only in the login
response; **at rest only its SHA-256 hex is stored**. Expired/orphaned rows
are treated as invalid on read — no background sweeper in v1.

| Column | Type | Constraints |
|---|---|---|
| `id` | int | PK |
| `token_hash` | str(64) | unique, not null — SHA-256 hex of the raw token |
| `user_id` | int | FK→`users.id`, not null |
| `created_at` | datetime (UTC) | not null |
| `expires_at` | datetime (UTC) | not null — now + `CMMESS_SESSION_TTL_HOURS` (default 24) at creation |

### `assets`

Generic, configurable entities keyed by their UNS-style path — never a
plant-specific equipment table.

| Column | Type | Constraints |
|---|---|---|
| `id` | int | PK |
| `path` | str(255) | unique, not null — the identity. **Immutability is app-level policy**, not a DB constraint: the row id stays stable while re-discovery rebuilds cached fields (DEC-008) |
| `display_name` | str(255) | not null |
| `description` | text | nullable |
| `provenance` | str(32) | CHECK in (`uns_discovered`, `manual`) — DEC-008: UNS is authoritative for discovered assets (local row = rebuildable cache); the registry is authoritative for manual ones |
| `retired` | bool | not null, default false (FS-Q7) |
| `created_at`, `updated_at` | datetime (UTC) | not null |

### `downtime_events`

A downtime interval on an asset. `up_at IS NULL` means **ongoing**. Duration is
always derived (`up_at − down_at`), never stored.

| Column | Type | Constraints |
|---|---|---|
| `id` | int | PK |
| `asset_id` | int | FK→`assets.id`, not null |
| `producer` | str(32) | CHECK in (`uns`, `manual`) |
| `down_at` | datetime (UTC) | not null |
| `up_at` | datetime (UTC) | nullable — null = ongoing |
| `reported_by` | int | FK→`users.id`, nullable (null for UNS-produced) |
| `ended_by` | int | FK→`users.id`, nullable |

**FS-Q1 — one ongoing event per asset, enforced at the database level:**
partial unique index `uq_downtime_events_ongoing_per_asset` — `UNIQUE (asset_id)
WHERE up_at IS NULL`. Partial indexes are supported natively by both SQLite and
Postgres; the `WHERE` clause is identical SQL on both (expressed via
SQLAlchemy's `sqlite_where`/`postgresql_where`, which is the portable spelling,
not dialect-specific SQL).

### `work_orders`

| Column | Type | Constraints |
|---|---|---|
| `id` | int | PK |
| `asset_id` | int | FK→`assets.id`, not null |
| `origin` | str(32) | CHECK in (`uns_downtime`, `manual_downtime`, `manual`) — typed and extensible; never assume a WO requires a downtime event or the UNS |
| `downtime_event_id` | int | FK→`downtime_events.id`, nullable — see pairing CHECK |
| `title` | str(255) | not null |
| `description` | text | nullable |
| `priority` | str(32) | CHECK in (`low`, `medium`, `high`), default `medium` (FS-Q6) |
| `status` | str(32) | CHECK in (`open`, `planned`, `in_progress`, `completed`, `cancelled`), default `open` |
| `created_by` | int | FK→`users.id`, nullable — null = system/UNS-seeded |
| `assigned_to` | int | FK→`users.id`, nullable |
| `scheduled_start` | datetime (UTC) | nullable |
| `expected_duration_minutes` | int | nullable |
| `completion_notes` | text | nullable |
| `created_at`, `updated_at` | datetime (UTC) | not null |

**FS §5 — origin↔event pairing, enforced at the database level:** CHECK
`ck_work_orders_origin_event_pairing`:

```sql
(origin = 'manual' AND downtime_event_id IS NULL) OR
(origin IN ('uns_downtime', 'manual_downtime') AND downtime_event_id IS NOT NULL)
```

`manual` origin ⇔ no downtime event; downtime origins ⇔ a downtime event. Both
illegal directions are rejected by the database on both engines (proven in
`backend/tests/test_models.py`).

### `work_order_transitions`

The FS's per-transition audit trail (including abandon notes). Transition
*logic* / state-machine enforcement is a later task — only the table exists.

| Column | Type | Constraints |
|---|---|---|
| `id` | int | PK |
| `work_order_id` | int | FK→`work_orders.id`, not null |
| `from_status`, `to_status` | str(32) | not null, CHECK in the `work_orders.status` value set |
| `at` | datetime (UTC) | not null |
| `by_user` | int | FK→`users.id`, nullable — null = system |
| `note` | text | nullable |

## Migration policy

- **Alembic**, config in `backend/alembic.ini`, environment in
  `backend/alembic/`, versions in `backend/alembic/versions/`. Run from
  `backend/`: `alembic upgrade head`. Current head: `0002`
  (`0001` initial schema → `0002` auth: `users.active` + `sessions`).
- **Dual-engine (DEC-006): every migration file runs unmodified on both SQLite
  and Postgres.** No dialect-specific SQL, no native PG ENUM types. The
  env-gated test `test_upgrade_runs_on_postgres_when_url_provided` proves it
  whenever `CMMESS_TEST_POSTGRES_URL` is set.
- **Additive-first.** New persisted fields are optional or ship with a
  migration/default — a new required field with no default silently invalidates
  pre-existing rows.
- `env.py` runs online migrations with `render_as_batch=True` so future ALTERs
  stay portable to SQLite.

## Where the database lives

- Dev default: SQLite at **`backend/data/cmmess.db`** — gitignored; the
  directory is created lazily on first use, never on import. **The dev DB is
  off-limits to tests and tooling** (CLAUDE.md): tests run exclusively against
  tmp-path databases.
- Override with **`CMMESS_DATABASE_URL`** (any SQLAlchemy URL; Postgres via
  `postgresql+psycopg://…`).
- Importing the app neither creates nor migrates a database; migration is an
  explicit operator step.
