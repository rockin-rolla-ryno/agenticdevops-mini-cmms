# CLAUDE.md — coding-agent invariants (CMMess)

> Minimal by design — **invariants only.** Task-specific detail belongs in the per-task spec, not here. This file exists so specs stop re-teaching the constitution every time.

## Non-negotiable

- **Never read, modify, delete, or reset a real or dev database, and never run a destructive migration against one.** The application database (SQLite file in dev, Postgres in deployment) holds real multi-user data — work orders, assets, downtime events, accounts. The only data you may touch are the committed test fixtures (e.g. under `tests/fixtures/`; the scaffold task T-001 establishes the exact path).
- **Read the task spec named in the command, in full, before writing any code.**
- **Build when done:** `npm run build` (renderer + main); for the backend, ensure `pip install -r requirements.txt` succeeds and the FastAPI app imports and starts.

## Architecture invariants (enforce in every change)

The hard constraints live in `docs/architecture-facts.md` — read them and treat them as binding. The ones you will break most easily if you forget:

- **No business logic, no direct database access, and no MQTT/UNS access in the renderer.** The React/TS renderer only calls typed backend REST endpoints. *(Hardest rule — no exceptions.)*
- **Authorization is enforced server-side, per endpoint.** Never rely on the renderer hiding or disabling a control as access control.
- **The renderer↔backend boundary is typed end to end** — Pydantic models and TypeScript types must agree; never hand-roll a shape that bypasses the shared typed surface. A boundary change moves its Pydantic model + TS type + `docs/api-contract.md` in the same commit (Rule 12).
- **Persistence goes through SQLAlchemy; Alembic migrations must run on both SQLite and Postgres** — no dialect-specific SQL.
- **The backend is the only MQTT client; the UNS is authoritative for assets.** Any local asset table is a cache rebuilt from UNS, never the source of truth.
- **Work-order origin is a typed, extensible field** (e.g. `uns_downtime`, `manual`) — never hardcode that a work order requires a downtime event.

## Traps that bite the coding agent specifically

- **A grep that finds nothing is not evidence of absence until the grep itself is validated.** Watch for identifiers assembled at runtime (e.g. a UNS topic path built from parts) that a literal grep can't match, case-sensitivity misses, and files not on the search path. Prove the grep by matching a string you *know* is present before trusting its silence.
- **Two green typechecks are not proof the two sides of the REST contract agree.** The renderer and backend each typecheck independently; they can still disagree at runtime. The tell: exercise the boundary against a *running* backend (an integration test), never mock it into triviality. Likewise, a new **required** field on a persisted schema makes pre-existing rows fail validation and silently vanish — new persisted fields are optional or ship with a migration/default.

## What stays out of this file

Per-task constraints, file lists, and acceptance criteria — those are in the spec. Standing rules the PM enforces (close-out, contract-sync) — the PM's job, not yours. Your job: implement the spec, honor the invariants above, build clean.
