# CMMess — Decision Log

> Numbered architectural decisions with rationale and date. When a spec touches an area a decision governs, read the decision **first** — it exists so the reasoning isn't relitigated from memory.

**Entry format:**
```
### DEC-NNN — <short decision title>

**Date:** YYYY-MM-DD
**Decision:** <what was decided, stated as a rule>
**Rationale:** <why — the trade-offs weighed>
**Supersedes:** <DEC-MMM, if this reverses an earlier decision — else "none">
```

**Conventions:**
- Numbered, append-only, ordered by number ascending. A reversal is a **new** DEC that names the one it supersedes; the old entry stays (history isn't rewritten).
- The decision is stated as a **rule** the specs can enforce, not a narrative.

## Log

### DEC-001 — Mechanical QA lives in the review agent; behavioral testing stays with the human

**Date:** 2026-07-21
**Decision:** The review agent (Cursor) owns mechanical QA — typecheck, lint, tests, and diffing the change against the spec's Acceptance Criteria. It is not given the human's behavioral/runtime-testing job; the human drives behavioral testing (feel and behavior).
**Rationale:** Separating "does it compile, pass, and match what was asked" from "does it feel and behave right" lets each participant catch what the other structurally can't, and keeps the human's pass from being spent re-verifying that the build works. Referenced as "Decision D1" in project instructions §3.
**Supersedes:** none *(inherited from the workflow template at project instantiation)*

### DEC-002 — No agent adopts the skills mechanism

**Date:** 2026-07-21
**Decision:** Value ships through the mechanism that fits each role — coding-agent config (`CLAUDE.md`), review-agent rules (`.cursor/rules/`), and PM checklists — not through a formal "skills" mechanism.
**Rationale:** No case was found where a skills mechanism beat the plain per-role mechanism; adopting it preemptively adds ceremony without a matching failure it prevents. The adopt-if trigger is recorded in `agent-config/skills.md`.
**Supersedes:** none *(inherited from the workflow template at project instantiation)*

### DEC-003 — Ground-truth deference is a numbered rule

**Date:** 2026-07-21
**Decision:** When the human states something about their own working environment or their own runtime observation, that is authoritative about a system the PM cannot see — act on it first, reason second (Rule 19). This is not blanket deference on code correctness, where reading the actual files remains the PM's check.
**Rationale:** Codified from a saga where the PM kept CI on the wrong runtime version for three round-trips after the human repeatedly named the right one. The observable world the human can see and the PM can't is the human's to call.
**Supersedes:** none *(inherited from the workflow template at project instantiation)*

### DEC-004 — Separate-service backend topology

**Date:** 2026-07-21
**Decision:** The FastAPI backend runs as a separate local service (`uvicorn`); the React/TypeScript renderer calls it directly over HTTP on localhost. The Electron main process is lifecycle-only (windows/app lifecycle) and never proxies data or domain calls between renderer and backend.
**Rationale:** Path of least resistance — one plain REST boundary, typed and testable end to end, instead of a two-hop IPC-then-HTTP chain; keeps main thin. Trade-off: two processes to launch in dev and orchestrate at package time, accepted for the simpler contract.
**Supersedes:** none

### DEC-005 — Server-side authorization; the renderer's role is display-only

**Date:** 2026-07-21
**Decision:** User vs. Planner authorization is enforced in the FastAPI backend, per action. Login issues a backend token/session; every protected endpoint independently re-checks the authenticated identity's role. The renderer may hide or show UI by role for UX, but that is never treated as access control.
**Rationale:** Single shared multi-user instance — client-side checks are trivially bypassed, and a hidden button is not security. Trade-off: an explicit role check on every protected endpoint, accepted as the only real boundary.
**Supersedes:** none

### DEC-006 — SQLAlchemy + Alembic, dual-engine (SQLite default, Postgres supported)

**Date:** 2026-07-21
**Decision:** All persistence goes through SQLAlchemy; migrations are authored with Alembic to run on both SQLite and Postgres, additive-first. SQLite is the default for v1/dev; Postgres is supported. No SQLite-only or Postgres-only SQL.
**Rationale:** The SQLite→Postgres path is a stated product requirement; a dialect shortcut now is an expensive refactor later. An ORM plus a migration tool gives portability and a versioned schema. Trade-off: ORM overhead and the discipline of engine-portable migrations, accepted for the portability guarantee.
**Supersedes:** none

### DEC-007 — UNS asset discovery over a live MQTT broker; the backend is the sole client

**Date:** 2026-07-21
**Decision:** Asset discovery is driven by a live MQTT broker (with simulated data in dev). The backend is the only MQTT client — nothing else subscribes or publishes. The UNS topic structure is an authoritative, documented contract (`docs/uns-contract.md`). The local asset registry is a cache of UNS discovery, never the source of truth.
**Rationale:** Matches how it will run, keeps a single ingestion point, and keeps the UNS authoritative for what assets exist so onboarding stays process-agnostic. Trade-off: dev needs a broker running with simulated messages, accepted since that mirrors production.
**Supersedes:** none
