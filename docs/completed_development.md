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
