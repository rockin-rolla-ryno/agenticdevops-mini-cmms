# Task T-003 — Data model + persistence base: SQLAlchemy, Alembic, core schema

## 1. Background

First domain task. The FS is settled (`docs/functional-spec.md`, Architect pass 2026-07-22); this task lands the persistence layer everything stacks on: SQLAlchemy 2.0 + Alembic wired dual-engine (DEC-006), the five core tables derived from the FS, and `docs/data-model.md` authored as the schema authority — in the same commit (Rule 12 / `docs/contract-sync.md` row 3). **No REST endpoints, no auth logic, no MQTT, no seeding** — those are later tasks; this is schema + migrations + config + tests.

Authority docs consulted: `docs/architecture-facts.md` (§ Persistence & migrations, § Canonical data formats, § Derived vs. authoritative), `docs/functional-spec.md` (§§ 2–5 — the behavioral source for every column), `docs/contract-sync.md` (schema change ⇒ migration + `data-model.md` same commit), `docs/decision-log.md` DEC-006/DEC-008.

Session note: per the Senior Architect, this session's dev happens **directly on `main`** (workflow §8 conscious skip); CI runs post-hoc on push.

## 2. What Already Exists (Do Not Rewrite)

- `backend/app/main.py` — FastAPI app with `GET /health` through `HealthResponse`. Keep it working; wire nothing into it beyond what §3 says (no startup DB calls, no new endpoints).
- `backend/requirements.txt`, `backend/pyproject.toml` — extend, don't restructure. ruff (`E,F,I,W`) and mypy `strict = true` stay green.
- `backend/tests/test_health.py` — must keep passing.
- The renderer (`src/`, root configs) and `.github/workflows/ci.yml` — untouched.
- `docs/api-contract.md` — untouched (no boundary endpoint/type changes in this task).

## 3. What to Build

### 3a. Config + engine

- `backend/app/config.py` — settings from env: `CMMESS_DATABASE_URL`, defaulting to a SQLite file at `backend/data/cmmess.db` (create the directory lazily). No secrets in code.
- `backend/app/db.py` — SQLAlchemy 2.0 engine/session factory built from config. Typed (`sessionmaker`/`Session`), no global side effects on import beyond engine construction.

### 3b. Models — `backend/app/models.py`

SQLAlchemy 2.0 **typed** declarative models (`Mapped[...]` / `mapped_column`; mypy strict must pass). All timestamps UTC. **Enum-valued columns are short strings constrained by CHECK constraints, typed in Python as `StrEnum`** — never native Postgres ENUM types (portable + additive-friendly; this is a deliberate dual-engine decision, record it in `data-model.md`).

1. **`users`** — id PK · `username` unique, not null · `role` CHECK in (`user`, `planner`) · `password_hash` not null · `created_at`. (Seeding + auth are T-004; the table exists so domain FKs are real from day one.)
2. **`assets`** — id PK · `path` unique, not null (identity; immutability is app-level policy, note it in the doc) · `display_name` not null · `description` nullable · `provenance` CHECK in (`uns_discovered`, `manual`) (DEC-008) · `retired` bool, default false (FS-Q7) · `created_at`, `updated_at`.
3. **`downtime_events`** — id PK · `asset_id` FK→assets, not null · `producer` CHECK in (`uns`, `manual`) · `down_at` not null · `up_at` nullable (null = ongoing; duration is always derived, never stored) · `reported_by` FK→users nullable (null for UNS) · `ended_by` FK→users nullable. **Partial unique index enforcing FS-Q1: unique on `asset_id` where `up_at IS NULL`** — at most one ongoing event per asset, at the database level, on both engines.
4. **`work_orders`** — id PK · `asset_id` FK→assets, not null · `origin` CHECK in (`uns_downtime`, `manual_downtime`, `manual`) · `downtime_event_id` FK→downtime_events nullable, **with a CHECK enforcing the FS pairing: `manual` origin ⇔ null event; downtime origins ⇔ non-null event** · `title` not null · `description` nullable · `priority` CHECK in (`low`, `medium`, `high`), default `medium` (FS-Q6) · `status` CHECK in (`open`, `planned`, `in_progress`, `completed`, `cancelled`), default `open` · `created_by` FK→users nullable (null = system/UNS-seeded) · `assigned_to` FK→users nullable · `scheduled_start` nullable · `expected_duration_minutes` nullable int · `completion_notes` nullable · `created_at`, `updated_at`.
5. **`work_order_transitions`** — id PK · `work_order_id` FK→work_orders, not null · `from_status`, `to_status` not null · `at` not null · `by_user` FK→users nullable (null = system) · `note` nullable. (The FS's "timestamps per transition" audit trail — including abandon notes. Transition *logic*/state-machine enforcement is a later task; only the table lands here.)

### 3c. Alembic

- `backend/alembic.ini` + `backend/alembic/` (env.py wired to the app's metadata + config URL) + **one initial migration** creating all of the above. Additive-first; **no dialect-specific SQL** — the same migration file runs on SQLite and Postgres.
- Add to `backend/requirements.txt`: `sqlalchemy>=2.0`, `alembic>=1.13`, `psycopg[binary]>=3.1` (the Postgres driver for the dual-engine leg).

### 3d. Tests — `backend/tests/`

All tests run against **temporary** SQLite databases (tmp_path); they must never open `backend/data/` (CLAUDE.md: the dev DB is off-limits; only committed fixtures may be touched — none are needed here).

- `test_migrations.py` — `alembic upgrade head` against a fresh tmp SQLite file creates all five tables; plus one test that runs the same upgrade against Postgres **iff** `CMMESS_TEST_POSTGRES_URL` is set, and otherwise skips with a visible reason (the dual-engine invariant gets a real check the moment a Postgres URL is provided, locally or in CI later).
- `test_models.py` — on a migrated tmp DB: a basic round-trip insert of each entity; **FS-Q1 proof:** inserting a second ongoing downtime event for the same asset raises an integrity error, while a second event after the first has `up_at` set succeeds; **pairing proof:** a `manual`-origin WO with a downtime event, and a `uns_downtime`-origin WO without one, are both rejected.

### 3e. Docs + housekeeping (same commit — Rule 12)

- **`docs/data-model.md`** (new) — the schema authority: header stating its role (per `docs/contract-sync.md`), table-by-table columns/constraints (including the partial unique index and the pairing CHECK, each tied to its FS rule), the enums-as-strings+CHECK decision and why, the migration policy (Alembic, additive-first, dual-engine, no dialect-specific SQL), and where the dev DB lives (`backend/data/`, gitignored; `CMMESS_DATABASE_URL` to override).
- **`.gitignore`** (root) — add `backend/data/`.

## 4. Acceptance Criteria

From `backend/` in a fresh venv:

- [ ] `pip install -r requirements.txt` succeeds; `ruff check .`, `mypy .` (strict), `pytest` all exit clean; `test_health.py` still passes.
- [ ] `alembic upgrade head` on a fresh SQLite database produces all five tables (proven by test, not by hand).
- [ ] The identical migration runs on Postgres when `CMMESS_TEST_POSTGRES_URL` is set; the test skips visibly otherwise. No dialect-specific SQL, no native PG ENUM types, anywhere in models or migrations.
- [ ] A second **ongoing** downtime event on the same asset is rejected at the DB level; a second event after the first ended is accepted (FS-Q1).
- [ ] The WO origin↔event pairing is rejected at the DB level in both illegal directions (FS §5).
- [ ] Models are SQLAlchemy 2.0 typed (`Mapped[...]`); mypy strict passes with no per-module strictness carve-outs.
- [ ] `uvicorn app.main:app` still boots and serves `/health`; importing the app does **not** create or migrate any database.
- [ ] Tests touch only tmp databases — nothing writes `backend/data/`.
- [ ] `docs/data-model.md` lands in the same commit with the §3e content; `docs/api-contract.md` is unchanged.
- [ ] The coding agent changes no files outside the §5 list (PM doc edits in the tree are not the agent's).

## 5. Files to Modify

- `backend/app/config.py` (new) · `backend/app/db.py` (new) · `backend/app/models.py` (new)
- `backend/alembic.ini` (new) · `backend/alembic/` env + one initial version (new)
- `backend/tests/test_migrations.py` (new) · `backend/tests/test_models.py` (new)
- `backend/requirements.txt` (edit: +sqlalchemy, +alembic, +psycopg)
- `docs/data-model.md` (new, same commit)
- `.gitignore` (edit: `backend/data/`)

## 6. Coding-Agent Instructions

Read this spec file (`docs/tasks/task_T-003_data-model-persistence.md`) in full before writing any code. Per the Architect, work **directly on `main`** this session — commit there; CI runs on push.

Wire SQLAlchemy 2.0 + Alembic dual-engine per DEC-006: typed declarative models for `users`, `assets`, `downtime_events`, `work_orders`, `work_order_transitions` exactly as §3b specifies — enum values as strings + CHECK constraints (never native PG enums), the FS-Q1 partial unique index (one ongoing event per asset), and the origin↔event pairing CHECK. One initial Alembic migration runnable unmodified on both SQLite and Postgres; config via `CMMESS_DATABASE_URL` defaulting to `backend/data/cmmess.db`. Tests prove the migration, the FS-Q1 index, and the pairing CHECK against tmp SQLite databases (plus an env-gated Postgres migration test). Author `docs/data-model.md` in the same commit (Rule 12). No endpoints, no auth/seeding logic, no MQTT, no renderer changes.

Hard constraints decided by this spec:

- **Silencer decision:** no kept-but-unused symbols are expected. If one arises, stop and flag the PM — do not choose a silencer or delete it yourself.
- **Database safety (CLAUDE.md):** tests use tmp databases only; never open, write, or migrate `backend/data/` or any existing database file.
- **Rule 12:** the contract surface moving with this commit is the persisted schema → `docs/data-model.md`. The TS-type leg is N/A (no boundary shapes change); `docs/api-contract.md` must not change.
- **User-facing impact:** None — no user-visible surface changes; no user-doc edits.

Standing invariants: honor docs/architecture-facts.md and CLAUDE.md; the renderer holds no business logic, DB, or MQTT/UNS access; authorization is enforced server-side; keep contract docs (Rule 12) and user-docs (Rule 18) in the same commit; migrations run on both SQLite and Postgres; never read/write/delete data outside the app's own store; build with npm run build when done (superseded for this task by the backend gate: install, ruff, mypy, pytest, and app import all clean from `backend/`).
