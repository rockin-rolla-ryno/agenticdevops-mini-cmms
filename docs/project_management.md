# CMMess — Project Management

> Holds the workflow specifics and the **task index**. The task-spec *format* lives in the spec-authoring checklist; this doc holds the index of tasks and the row format for it.

## Task-spec format

Every task gets a spec at `docs/tasks/task_<ID>_<slug>.md`, six sections, before any coding-agent command. See `checklists/spec-authoring.checklist.md`.

## Coding-agent command format

The command is handed to the human to paste into Claude Code:

```
To Claude Code — "Read docs/tasks/task_<ID>_<slug>.md in full before writing any code.
[2–4 sentence summary of what to implement, which files, key constraints.]
Standing invariants: honor docs/architecture-facts.md and CLAUDE.md; keep contract
docs (Rule 12) and user-docs (Rule 18) in the same commit; migrations run on both
SQLite and Postgres; never read/write/delete data outside the app's own store."
```

## The task index

**Row format — enforce it, because a readable index is a usable index:**

- One row per task **for its whole lifecycle**. Status transitions **edit the existing row in place** — never append a duplicate.
- Leading status symbol from a fixed set: ✅ complete · 🟡 in progress · 🔴 not started · ❄️ deferred.
- Title: soft target ≤8 words, hard cap ≤12 words; single em-dash separator; no bold annotations in the title cell.
- Date in the Verified column when complete.

| Status | ID | Title | Verified |
|---|---|---|---|
| ✅ | T-001 | Backend skeleton — FastAPI /health + tooling | 2026-07-22 |
| ✅ | T-002 | Renderer scaffold — Electron/Vite/React + green CI | 2026-07-22 |
| ✅ | T-003 | Data model — SQLAlchemy/Alembic + core schema | 2026-07-22 |

## Queued / not-yet-specced items

*(none — next items get queued here as the FS's feature slices are cut)*
