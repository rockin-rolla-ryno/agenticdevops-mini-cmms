# CMMess — Agent Handoff

> **Format: always-current. Updated every turn, not end-of-session.** This is the first thing every agent reads. It answers "where are we right now?" — keep it true.

## Read me first in any new session

Mandatory before responding to the human:

1. This file — state of play.
2. `docs/completed_development.md` *most-recent entries only* — what just shipped.
3. `docs/project_management.md` task table — live task status.
4. `docs/bug_log.md` — active bugs.
5. `docs/backlog.md` — prioritized "what's next" *(created when the first backlog item is queued; until then see `project_management.md` § Queued)*.

Then read what's relevant per the Tier-1/Tier-2 list in the project instructions, and the one authority doc for the area you're touching (`docs/authority-docs-by-area.md`).

## Current state

**Project bootstrap in progress — no product code yet.** The repo currently holds the workflow scaffolding (Layer A templates, Layer B2 scaffolds, checklists, agent-config templates) plus the CMMess instructions and user story. We are standing the workflow up, not building features.

**Landed this bootstrap:** all Layer B2 docs (`architecture-facts.md`, `authority-docs-by-area.md`, `contract-sync.md`) and all seven Layer A living docs; `CLAUDE.md` (root) and `.cursor/rules/qa-role.mdc`; the three checklists filled (spec-authoring, close-out, and packaging-preflight resolved as defer-TBD); a fresh CMMess `README.md`. The instructions mirror received three edits — add `api-contract.md` to Tier 2, repoint Rule 12 at `docs/contract-sync.md`, and repoint §3's review-agent config at `.cursor/rules/qa-role.mdc`. All kept docs were de-referenced from the soon-to-be-deleted scaffolds so nothing dangles.

**Scaffolding deleted; slot gate clean.** The template `layer-a/`, `layer-b2/`, `layer-b1-example/`, `agent-config/*.template.md`, `teaching/`, `diagrams/`, `INSTANTIATE.md`, and `SETUP.md` are removed. The slot gate returns only the three intentional ADOPT-IF markers (in `contract-sync.md`, `sub-agents.md`, `skills.md`) — the written-down "revisit when X" triggers, which stay.

**T-001 shipped and closed out (2026-07-22) — first full loop trip complete.** The backend skeleton is live: FastAPI `GET /health` through a typed Pydantic model, one passing pytest, ruff+mypy strict clean, `docs/api-contract.md` seeded in the same commit (Rule 12), root `.gitignore`. Commit `0a3e2a2` on `main` (direct commit — tolerated once; branch→PR resumes at T-002 when CI exists). Dev → Cursor QA → PM read-verify → human runtime test all exercised for real. Full record: `docs/completed_development.md` § T-001. Backend venv lives at `backend/.venv` (`source .venv/bin/activate` before `uvicorn app.main:app`). Note: the PM is temporarily running as a Claude Code instance (Desktop MCP bug anthropics/claude-code#79971).

**Functional spec drafted + DEC-008 landed (2026-07-22).** `docs/functional-spec.md` is live as the product-behavior authority (announced in `authority-docs-by-area.md`): three WO origins (`uns_downtime`/`manual_downtime`/`manual` — Architect decision), manual asset registration with provenance + path-merge rule (DEC-008, narrows DEC-007 — the product is fully usable with zero UNS), standard WO state machine (Open→Planned→In Progress→Completed, +Cancelled), User self-serve execution on Open WOs. `architecture-facts.md` and `CLAUDE.md` were synced to DEC-008 in the same pass. **Awaiting the Architect's pass on the FS's [default] markers and § 9 open questions (FS-Q1–Q8)** — defaults are workable, so this doesn't block T-002. The three earlier constitution edits are synced into the Project instructions field (done 2026-07-22). Temp file `docs/architecture-diagram-temp.md` exists for the human to pull out — not a living doc; delete on request (its "UNS authoritative" label predates DEC-008).

**T-002 built, verified, closed out (2026-07-22) — commit/PR/merge pending.** Renderer shell + CI live on branch `T-002-renderer-scaffold-ci` (uncommitted; Claude Code is holding the commit). Full loop ran: Dev → Cursor QA (mechanical all-PASS; two FAILs arbitrated by PM — doc-allowlist hits were PM branch bookkeeping, CI-green is post-PR by design) → PM read-verify of every shipped file → human runtime test (Electron window + placeholder ✅). Close-out landed: completed-dev § T-002, index ✅, devops_pipeline § First-green-build rewritten to current-state. **The one open criterion: CI green on the actual PR** — first real PR→CI→squash-merge trip. Spec-authoring lesson for future ACs: write the blast-radius criterion as "the *coding agent* changes no files outside this list" so PM branch bookkeeping stops tripping QA.

## Immediate next steps

1. Human: have Claude Code commit on `T-002-renderer-scaffold-ci` (close-out doc edits ride the same branch), push, open the PR (body template in `development_workflow.md` §4).
2. Human + PM: confirm CI green on the PR → squash-merge, delete branch. That closes T-002's last criterion. *(First run failed on `npm ci` — npm-major skew, see TRAP-001; fix in flight: CI pin moved Node 22→26 in `devops_pipeline.md`, coding agent bumps `ci.yml` + regenerates the lock on the branch.)*
3. Human: pass over `docs/functional-spec.md` — rule on the **[default]** markers and FS-Q1–Q8. This is now the frontier: next specs are feature slices cut from the FS (likely: data model + persistence base, then auth/roles).

## Architecture authorities by area (read the one you're touching)

The full index is in `docs/authority-docs-by-area.md`. Short version: architecture constraints → `architecture-facts.md` (every spec) · persistence → `data-model.md` *(to author)* · REST boundary → `api-contract.md` *(to author)* · UNS/MQTT → `uns-contract.md` *(to author)* · boundary-change sync → `contract-sync.md` · auth/roles → `architecture-facts.md` § Security · UI → `design-guide.md` · packaging → `packaging.md` *(to author)*.

## Standing notes

- **Keep the instructions mirror in sync.** Canonical project instructions live in the Claude Project field; the git-tracked mirror is `docs/claude_project_instructions.md`. When the instructions change, rewrite the mirror in the same turn. If the two diverge, the Project copy wins. *(As of this bootstrap, two edits — the `api-contract.md` Tier-2 addition and the Rule 12 repoint — were made to the mirror and need mirroring into the Project field.)*
- **No repo doc is attached to the Claude Project.** Every living doc is read on demand from the repo so it can't go stale.
- **The four foundational architecture choices** (separate-service topology, server-side role enforcement, SQLAlchemy+Alembic dual-engine persistence, live-broker UNS) are recorded in `decision-log.md` as DEC-004–007 and enforced via `architecture-facts.md`. Don't relitigate from memory.
