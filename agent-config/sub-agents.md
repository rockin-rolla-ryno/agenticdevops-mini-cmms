# Sub-agents — decision (not config to install)

> This is a **recorded decision**, not a file you install. It exists so a future you doesn't rebuild the reasoning.

## Decision: keep sub-agents as the coding agent's on-demand call. Do not formalize.

The coding agent will occasionally spin up a sub-agent on its own initiative; that's fine and needs nothing from you. The two places a formalized sub-agent looks attractive both fail the concrete-benefit test:

- **Parallel verification reads** — the PM reads changed files fine sequentially; per-task blast radius is small. Fan-out adds coordination ceremony for no real speedup.
- **A dedicated QA sub-agent** — that is QA's job, and QA belongs in the **review agent** (`.cursor/rules/qa-role.mdc`), which can actually *run* the app. A coding-agent sub-agent runs in the coding agent's own sandbox and would just re-do the PM's static read. Put QA where it can execute rather than spawn an agent that can only re-read.

## Adopt-if trigger

`<<ADOPT-IF: you observe a genuine, repeated need — e.g. a task type that reliably requires exploring a large unfamiliar area before implementing, where a scoped research sub-agent would save real time. Then formalize that one narrow use, not sub-agents in general.>>`
