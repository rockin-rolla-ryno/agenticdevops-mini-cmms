# CMMess — Completed Development

> The full history of completed work. **Read the recent entries before assuming something isn't built.** Log an entry **only after reading the actual output files** — it records what was *built*, not what was planned.

## How to use this log

- **Entries are immutable once written**, except to add/update the "verified by human" line. A future reader who finds an older entry restating a mechanism should **not** "clean it up" — that's drift in the wrong direction.
- Newest entries at the top of `## Log`.
- When this file gets large, archive by release into `docs/archive/completed_development_<release>.md` and keep only recent entries live.

## Per-entry convention

The entry shape — header block, the required body sections in order, the length caps, and the anti-patterns — is owned by **`checklists/close-out.checklist.md`**. Follow it there.

The one line worth repeating because it's mandatory and cheap: every entry carries a **`User-facing impact:`** line, never omitted. `None.` is a valid, considered answer.

## Log

### T-007 — Work-order API: FS §5 state machine, planning, single-choke-point audit trail

**Date:** 2026-07-22
**Spec:** `docs/tasks/task_T-007_work-order-api.md`
**Verified by human:** ✅ 2026-07-22 — Cursor QA pass ("QA Passed -- ship it"); runtime delegated to PM — 12-check CL suite passed, full audited lifecycle verified live.

**What was built.** The backend domain surface completed (commit `93dfaa1`): `backend/app/work_orders.py` — list (five exact-match ANDed filters; planner queue = `status=open`), detail (reused `DowntimeEventOut` + chronological transitions), direct manual creation (origin `manual`, FS-Q6 priority), creator-or-planner PATCH (open/planned only; priority deliberately lives in `plan`), and five intent-named transitions implementing FS §5 verbatim: `plan` (planner; re-plan updates fields with no audit row), `start` (self-serve claim from open sets `assigned_to`; assignee-only from planned, planners included), `complete` (executor-only, non-empty notes), `abandon` (executor-or-planner, returns to the `from_status` of the latest entry into `in_progress`, clears assignment only to open), `cancel` (planner-only, any non-terminal). `_apply_transition` is the single write path — status + audit row in one transaction, documented as the FS-Q8 UNS-publish hook. Wrong person → 403; wrong state → 409 naming the current status. Completing/cancelling never ends the downtime event (FS §4, tested API+ORM).

**Files touched.**
- `backend/app/work_orders.py` — NEW: router, models, transition helper.
- `backend/tests/test_work_orders.py` — NEW: 13 tests, 3 seeded accounts (executor gates need a non-assignee).
- `backend/app/main.py` — modified: include router (2 lines).
- `docs/api-contract.md` — modified: `## Work orders` section, same commit (Rule 12).

**Deviations from spec.** None.

**Architectural impact.** Executor rule codified (start claims via `assigned_to`; no executor column) — recorded in `api-contract.md`. Known soft spot logged, not fixed: transition endpoints are check-then-act without row locking — fine under SQLite's writer serialization; revisit with `SELECT … FOR UPDATE` when Postgres becomes primary.

**User-facing impact.** None yet — surface arrives with T-008; API documented in `docs/api-contract.md` (same commit).

### T-006 — Downtime events API + atomic work-order seeding (the event→WO core)

**Date:** 2026-07-22
**Spec:** `docs/tasks/task_T-006_downtime-wo-seeding.md`
**Verified by human:** ✅ 2026-07-22 — Cursor QA pass confirmed by the Architect ("QA Passed"); runtime delegated to PM — 10-check CL suite against a scratch-DB uvicorn passed in full.

**What was built.** The product's core primitive, live (commit `25fa63a`): `backend/app/downtime.py` with `record_downtime(db, asset, producer, reported_by)` — an HTTP-free service creating a downtime event + its seeded WO in one transaction (flush → seed → single commit; rollback removes both), written for direct reuse by the future UNS ingestion (`producer="uns"` → origin `uns_downtime`, `created_by` null — proven by a direct-call test and a live direct call in the PM's runtime suite). FS-Q1 raises a domain `OngoingDowntimeError` carrying `ongoing_event_id` + `work_order_id`; the `IntegrityError` race on the partial unique index rolls back, re-queries, and rejects identically — never a 500 (proven by a stateful-monkeypatch race test). Two `require_user` endpoints: `POST /assets/{id}/downtime-events` (201 `{event, work_order}`; 404/409-retired/409-FS-Q1-pointer) and `POST /downtime-events/{id}/end` (200 with derived duration; 409 for `uns` producer, 409 already-ended — attribution never rewritten). Ending never touches WO status (FS §4 independence, tested). Shapes reused from `app.assets` — no duplicates.

**Files touched.**
- `backend/app/downtime.py` — NEW: service + router.
- `backend/tests/test_downtime.py` — NEW: 10 tests incl. atomicity row-counts, exact 409-body equality, FS-Q2 re-seed, race.
- `backend/app/main.py` — modified: include downtime router (2 lines).
- `docs/api-contract.md` — modified: `## Downtime events` section, same commit (Rule 12).

**Deviations from spec.** None.

**Architectural impact.** None — `record_downtime` is now the single seeding path (the contract doc mandates no parallel path may be written); FS-Q8 publish hook will attach at T-007's transition helper, not here.

**User-facing impact.** None yet — surface arrives with T-008; API documented in `docs/api-contract.md` (same commit).

### T-005 — Assets API: registry list/detail with derived status, manual register/edit/retire

**Date:** 2026-07-22
**Spec:** `docs/tasks/task_T-005_assets-api.md`
**Verified by human:** ✅ 2026-07-22 — runtime testing delegated to PM this task ("All QA passed — you do the cl tests"); PM's 12-check CL suite against a scratch-DB uvicorn passed in full.

**What was built.** The first domain API slice (commit `22f7608`): `backend/app/assets.py`, five endpoints under a router-level `require_user` dependency (both roles; no route can be accidentally unauthenticated). `GET /assets` — flat path-ordered list, `include_retired=false` default, derived up/down status computed in two bounded queries (no N+1). `GET /assets/{id}` — detail with newest-first downtime history (derived `duration_seconds`, null while ongoing) and WO summaries; reachable when retired (FS-Q7). `POST /assets` — manual registration, server-side path validation (422), duplicate path 409 with pre-check + `IntegrityError` race catch. `PATCH` — `model_fields_set` omitted-vs-null semantics; `AssetUpdate` has no `path` field + `extra="forbid"` (path immutability is structural). `POST .../retire` — manual-only, idempotent 200. Edit/retire on `uns_discovered` → 409 (DEC-008: cache rows aren't locally mutable). Status/durations are derived from `downtime_events` at read time — nothing stored.

**Files touched.**
- `backend/app/assets.py` — NEW: router, Pydantic models, derivation.
- `backend/tests/test_assets.py` — NEW: 12 integration tests; row-count/change-nothing proofs behind every 409/422.
- `backend/app/main.py` — modified: include assets router (2 lines).
- `docs/api-contract.md` — modified: full `## Assets` section, same commit (Rule 12).

**Deviations from spec.** One, minor: `PATCH` with explicit `display_name: null` is silently ignored rather than 422'd — the spec left the case undefined; behavior is safe (a non-nullable column can't be nulled) and logged here for the record.

**Architectural impact.** None — first consumer of the DEC-005 gate pattern outside auth itself; router-level dependency is now the precedent for domain routers. `WorkOrderSummaryOut`/`DowntimeEventOut` are the shared shapes T-006/T-007 build on.

**User-facing impact.** None yet — no renderer surface until T-008; no user-doc pages exist to update. The API surface itself is documented in `docs/api-contract.md` (same commit).

### T-004 — Auth + roles: seeded accounts, sessions, server-side enforcement pattern

**Date:** 2026-07-22
**Spec:** `docs/tasks/task_T-004_auth-roles.md`
**Verified by human:** ✅ 2026-07-22 — live runtime test against the human's `uvicorn` + dev DB (PM-executed at the human's direction): login/me/logout happy paths, identical generic 401s for bad-password vs. unknown-user, uniform 401 without token, 204 logout with the token 401ing afterwards.

**What was built.** Backend auth (commit `04941a4`, direct on `main`): additive migration `0002` (`users.active` for seeded-config revocation; `sessions` storing only SHA-256 token hashes), TOML account seeding in the FastAPI lifespan (`CMMESS_USERS_FILE`, gitignored real config, committed example) with upsert-and-deactivate semantics — deactivation also kills live sessions, rows never deleted; `POST /auth/login` / `POST /auth/logout` / `GET /auth/me` with opaque bearer tokens (`secrets.token_urlsafe(32)`, TTL via `CMMESS_SESSION_TTL_HOURS`); and **the standing DEC-005 enforcement pattern** — `require_user`/`require_planner` dependencies (Planner ⊇ User, FS-Q3), named as *binding* for every future protected endpoint in `docs/api-contract.md`. Beyond spec, kept deliberately: timing-parity bcrypt verify on unknown usernames (latency doesn't enumerate either) and naive/aware datetime normalization for SQLite. `python -m app.hash_password` generates config hashes. 10 integration tests cover every §3d property, including token-hashed-at-rest proven by DB inspection and startup failing with an operator message on an unmigrated schema. Cursor QA: PASS (15 passed/1 expected skip); the Postgres leg was exercised once for real by the coding agent (throwaway Postgres 16 container, fresh + stepwise 0001→0002).

**Files touched.** NEW: `backend/app/auth.py` · `backend/app/seeding.py` · `backend/app/hash_password.py` · `backend/alembic/versions/0002_auth_sessions.py` · `backend/tests/test_auth.py` · `backend/config/users.example.toml`. Modified: `backend/app/main.py` (router + lifespan) · `backend/app/config.py` · `backend/app/models.py` (`active`, `Session`) · `backend/requirements.txt` (+bcrypt) · `.gitignore` (+`backend/config/users.toml`) · `docs/api-contract.md` (Auth section, same commit) · `docs/data-model.md` (0002 surface, same commit).

**Deviations from spec.** None. Known non-blocking (QA smell, accepted): a hand-corrupted `password_hash` in config/DB would 500 on `bcrypt.checkpw` rather than 401 — not spec-required; the hash-helper + example-file flow makes it unlikely.

**Architectural impact.** DEC-005 now has its canonical implementation; `require_user`/`require_planner` is the enforcement pattern all future endpoints copy (recorded as binding in `docs/api-contract.md` § Auth).

**User-facing impact.** None yet — backend-only by Architect decision; the renderer login task delivers the user-visible surface (and the TS leg of the auth contract).

### T-003 — Data model + persistence base: SQLAlchemy 2.0, Alembic dual-engine, core schema

**Date:** 2026-07-22
**Spec:** `docs/tasks/task_T-003_data-model-persistence.md`
**Verified by human:** ✅ 2026-07-22 — runtime surface nil for this task (no endpoints or UI changed); human accepted the review agent's live-boot check (`uvicorn` → `GET /health` 200) in lieu of a separate eye-test.

**What was built.** The persistence layer (commit `4a5a651`, direct on `main` per the session decision): five SQLAlchemy 2.0 typed models (`users`, `assets`, `downtime_events`, `work_orders`, `work_order_transitions`) with enum values as strings + CHECK constraints (never native PG enums), one hand-written Alembic initial migration that runs unmodified on SQLite and Postgres, config via `CMMESS_DATABASE_URL` (default `backend/data/cmmess.db`, gitignored, lazily created, off-limits to tests), and `docs/data-model.md` authored as the schema authority in the same commit (Rule 12). Both FS-derived invariants are enforced **at the database level** and test-proven in both directions: FS-Q1's one-ongoing-downtime-event-per-asset (partial unique index) and FS §5's origin↔event pairing (CHECK). Beyond spec, kept deliberately: `PRAGMA foreign_keys=ON` per SQLite connection (dual-engine referential-integrity parity), a metadata naming convention enabling future batch migrations, `render_as_batch` in env.py, and the agent verified the migration + both constraints against a real Postgres 16 (throwaway Docker) rather than resting on the env-gated skip. Cursor QA: PASS, 5 passed/1 visible skip (the Postgres leg awaiting `CMMESS_TEST_POSTGRES_URL`).

**Files touched.** All backend/docs, NEW unless noted: `backend/app/config.py` · `backend/app/db.py` · `backend/app/models.py` · `backend/alembic.ini` · `backend/alembic/env.py` · `backend/alembic/script.py.mako` · `backend/alembic/versions/0001_initial_schema.py` · `backend/tests/test_migrations.py` · `backend/tests/test_models.py` · `docs/data-model.md` · `backend/requirements.txt` (edit: +sqlalchemy, +alembic, +psycopg) · `.gitignore` (edit: +`backend/data/`).

**Deviations from spec.** None. Known non-blocking (QA smells, agreed): the `test_models` session fixture uses a raw engine without the FK pragma — the constraint proofs it makes don't depend on FK enforcement, but a future test asserting FK violations must use the `app.db` engine path; the agent's local gate ran Python 3.14 (3.12 not installed locally) — the pinned runtime is covered by CI on push.

**Architectural impact.** DEC-006 and DEC-008 now have their first enforcement in code; `docs/data-model.md` is live as the schema authority (announced in `authority-docs-by-area.md`'s terms — the *(to author)* marker is now stale there and in the handoff's short index).

**User-facing impact.** None. No user-visible surface; no user-doc changes required.

### T-002 — Renderer scaffold: Electron+Vite+React shell; CI workflow live

**Date:** 2026-07-22
**Spec:** `docs/tasks/task_T-002_renderer-scaffold-ci.md`
**Verified by human:** ✅ 2026-07-22 — "All tests passed"; `npm run dev` launched the Electron window with the placeholder. Final criterion (CI green on the actual PR) closes at merge — tracked in the handoff.

**What was built.** The Electron + Vite + TypeScript + React renderer shell at repo root, scaffolded from electron-forge's vite-typescript template: `src/main.ts` is lifecycle-only with `contextIsolation: true` / `nodeIntegration: false` explicit (DEC-004 + security baseline; no IPC, HTTP, or domain logic — confirmed by PM read of every `src/` file), a comment-only preload, and a static placeholder `App`. Test harness established: vitest + jsdom + Testing Library, one test rendering `App` and asserting by role + text, with `vitest.config.ts` deliberately separate from the forge/vite build configs. eslint flat config (@eslint/js + typescript-eslint; template's legacy .eslintrc upgraded per spec), strict tsconfig, and scripts `dev|build|lint|test|typecheck` all wired and exiting 0. `.github/workflows/ci.yml` implements `docs/devops_pipeline.md`'s table exactly: push-to-main + PR, `permissions: contents: read`, Python 3.12 + Node 22 pinned, backend ruff/mypy soft via `continue-on-error` with "soft — advisory" step names, all other steps hard, no extras. Cursor QA: all mechanical checks PASS on both toolchains; its two FAILs were arbitrated — doc-allowlist hits were the PM's own branch bookkeeping (agent's blast radius clean), and CI-green is sequenced post-PR by design.

**Files touched.** NEW: `.github/workflows/ci.yml` · `package.json` · `package-lock.json` · `forge.config.ts` · `forge.env.d.ts` · `index.html` · `tsconfig.json` · `eslint.config.mjs` · `vite.main.config.ts` · `vite.preload.config.ts` · `vite.renderer.config.ts` · `vitest.config.ts` · `src/main.ts` · `src/preload.ts` · `src/renderer.tsx` · `src/App.tsx` · `src/App.test.tsx` · `src/index.css` · `src/test/setup.ts`. Modified: `.gitignore` (adds `.vite/` only) · `README.md` (real dev/build commands).

**Deviations from spec.** None in substance. Two recorded interpretations: `npm run build` = `tsc --noEmit && electron-forge package` (heavier than a bare bundle; satisfies the criterion, `out/` gitignored) · `@vitejs/plugin-react` pinned `^4` (v6 requires Vite 8; forge template pins Vite 5). Known non-blocking: Vite emits an "empty chunk: preload" warning for the comment-only preload — no lint impact, no silencer needed.

**Architectural impact.** None new — first implementation of the DEC-004 shell (main lifecycle-only) and the Electron security baseline; `docs/devops_pipeline.md` is now current state, not target (its § First green build was rewritten this close-out).

**User-facing impact.** None. No end users yet; `README.md` dev-commands block updated in the same commit.

### T-001 — Backend skeleton: FastAPI `GET /health`, test, tooling; API contract doc seeded

**Date:** 2026-07-22
**Spec:** `docs/tasks/task_T-001_backend-skeleton.md`
**Verified by human:** ✅ 2026-07-22 — booted `uvicorn app.main:app`; live `GET /health` returned 200 `{"status":"ok"}`

**What was built.** The Python/FastAPI backend skeleton (commit `0a3e2a2`): `backend/app/main.py` exposes `GET /health` through a typed Pydantic `HealthResponse` (`status: Literal["ok"]`) — the typed-boundary invariant honored from the very first endpoint. One pytest exercises it via `TestClient`, asserting 200 and the exact body. `backend/requirements.txt` holds exactly six deps (fastapi, uvicorn, pytest, httpx, ruff, mypy — no SQLAlchemy/Alembic/MQTT); `backend/pyproject.toml` configures ruff (E/F/I/W) and mypy strict (py311) so bare `ruff check .`, `mypy .`, and `pytest` all exit clean from `backend/`. The commit also seeds `docs/api-contract.md` with the `/health` entry (Rule 12, same commit; TypeScript leg N/A until the renderer lands) and a root `.gitignore`. Cursor QA: PASS on all checks. Known non-blocking: pytest surfaces a Starlette-internal deprecation warning — revisit at the next dependency bump.

**Files touched.** All NEW:
- `backend/app/__init__.py`
- `backend/app/main.py`
- `backend/tests/__init__.py`
- `backend/tests/test_health.py`
- `backend/requirements.txt`
- `backend/pyproject.toml`
- `docs/api-contract.md`
- `.gitignore`

**Deviations from spec.** One, procedural: committed directly to `main` rather than branch→PR — acceptable this once because no CI exists yet to gate a PR (that lands with T-002); branch→PR resumes from T-002 onward. Code content: none.

**Architectural impact.** None — first instance of the typed renderer↔backend boundary pattern per `docs/architecture-facts.md`; `docs/api-contract.md` now live (announced in `docs/authority-docs-by-area.md`'s terms as the REST-boundary authority).

**User-facing impact.** None. No user-visible surface exists yet; no user-doc changes required.
