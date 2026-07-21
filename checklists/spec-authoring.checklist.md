# Checklist — Spec Authoring

**When:** before handing any task to the coding agent. Every task gets a spec file **first** — no ad-hoc coding-agent commands, ever.

**Why a checklist:** the spec is the contract the coding agent implements against and the PM verifies against. The recurring failure isn't writing a bad spec — it's writing an *incomplete* one: a silencer left to the agent's discretion, a contract doc that didn't move with the code, a layout change that broke the far side of a divider nobody looked at. Each line below is a place a real defect entered on the source project.

---

## Before writing (ground yourself — read, don't assume)

- [ ] **Read the actual source files** you're about to spec against. Never spec from memory or a conversation summary. If a file changed earlier this session, re-read the fresh version.
- [ ] **Check it isn't already built.** Read the completed-work log before speccing anything that looks missing — it may already exist.
- [ ] **Check the bug log** for the area you're touching. Patterns that caused a bug once tend to recur; the log records the root cause.
- [ ] **Read the area's authority doc** (see the authority-docs-by-area index). For UI, the design/UX guides; for the data/contract layer, the schema and contract docs.

---

## The spec file — six sections, in this order

Write to `docs/tasks/task_<ID>_<slug>.md`. Sections:

1. [ ] **Background** — what and why, briefly.
2. [ ] **What Already Exists (Do Not Rewrite)** — name the existing code the agent must build *on*, not replace. Prevents re-implementation.
3. [ ] **What to Build** — the actual change.
4. [ ] **Acceptance Criteria** — *assert a property, not a shape.* State verifiable behavior ("guest emails carry the correct timezone"), never a prescribed implementation form ("use function X"). A criterion that dictates the shape has caused a real defect; a criterion that dictates the behavior catches one. A same-context test cannot prove a context-dependent bug is fixed — say what must be observably true.
5. [ ] **Files to Modify** — the expected blast radius.
6. [ ] **Coding-Agent Instructions** — see below; mandatory.

---

## Hard constraints the spec itself must decide (not the agent)

- [ ] **Kept-but-unused symbol → the spec names the silencer.** If a call site is removed but the export/import/function is retained, the spec states *exactly* how the unused-symbol warning is silenced (the project's chosen mechanism — e.g. a module-scope `void X;` or an explicit lint-disable). Leaving it to the agent means the import gets deleted to make the build pass, and the retention intent is lost.
- [ ] **Contract-doc sync in the same commit (the contract-sync rule).** If the spec changes any module-boundary contract (IPC/RPC channels, schemas, DB migrations, serialized formats), it must include the matching updates to the contract docs and typed surfaces **in the same commit**. List them explicitly. Stale contract docs = broken code at the boundary.
- [ ] **User-visible change → user-docs in the same commit.** If the task changes what a user sees or does (a menu item, shortcut, gesture, setting, workflow), the matching user-doc page changes in the same commit, and the close-out records a User-facing-impact line. Generated pages are never hand-edited — change their source data and regenerate.
- [ ] **Layout / structural change → pre-flight both checks.** Before speccing any panel/split/layout change: (a) look for elements mixing structural utilities with content utilities — candidates for splitting; (b) enumerate every resizable boundary and verify the padding/margin on **both** sides, not just the side that was complained about. Asymmetric divider padding is a recurring cross-project failure.
- [ ] **Canvas-anchored insertion → reuse the existing insertion-point mechanism.** If new content lands at a canvas position, consume the project's established insertion-point source; do not introduce parallel cursor-tracking state.

---

## The Coding-Agent Instructions section (ends every spec)

- [ ] Tells the agent to **read the spec file first by name/path**, in full, before writing any code.
- [ ] Restates the implementation as 2–4 direct sentences: what to do, which files, the key constraints.
- [ ] Calls out **every** hard constraint from the list above that applies.
- [ ] Ends with the standing invariants line: `Standing invariants: honor docs/architecture-facts.md and CLAUDE.md; the renderer holds no business logic, DB, or MQTT/UNS access; authorization is enforced server-side; keep contract docs (Rule 12) and user-docs (Rule 18) in the same commit; migrations run on both SQLite and Postgres; never read/write/delete data outside the app's own store; build with npm run build when done.`

**The command handed to the human** mirrors this: `To Claude Code — "Read docs/tasks/task_<ID>_<slug>.md in full before writing any code. [2–4 sentence summary + constraints.] [the standing-invariants line above]"`

---

## After the spec, before the agent runs

- [ ] **Add the task-index row** in the task-index doc following its row format (edit-don't-append: one row per task).
- [ ] **Add the bug-log entry** (if a bug fix) before the task runs; mark it Fixed only after verification.
