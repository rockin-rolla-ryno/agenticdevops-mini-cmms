# Checklist — Atomic Close-Out

**When:** the coding agent reports tests-pass on a spec'd task **and** the PM has verified the actual changed files by reading them. Not before both.

**Why this is a checklist and not prose:** the close-out runs on *every* completed task, and its failure mode is silent — one of its edits gets skipped, a doc drifts, and nobody notices until it has misdirected a later session. On the source project the state-of-play doc drifted ~1 month for exactly this reason: it was the one close-out edit no rule bound to the turn. The fix was to bind all of it to one turn. This checklist is that binding.

**The rule it enforces:** *all* of the edits below land **in the same turn**, before the next human message. A task whose code merged but whose close-out didn't is the precise failure this prevents.

---

## Gate (do not start the close-out until both are true)

- [ ] The coding agent reported its tests pass.
- [ ] The PM read the **actual changed files** (fresh reads, not a cached copy from earlier in the session) and confirmed the diff matches the spec, contract surfaces agree, and there's no collateral damage. *Verification is about reading the output, not trusting the agent's summary.*

If either is incomplete, **do not** land partial doc updates — flag the gap to the human and stop.

---

## The four edits, in order — all in one turn

1. [ ] **Task index row → complete.** In `docs/project_management.md`, flip this task's existing row from in-progress to complete, with the date. **Edit the existing row in place — do not append a second row.** One row per task for its whole lifecycle.

2. [ ] **Bug log → fixed** *(only if this task fixed a logged bug).* In `docs/bug_log.md`, move the entry from Active to Fixed. Skip if not a bug fix.

3. [ ] **Close-out entry written.** Add the entry to `docs/completed_development.md` following the per-entry convention (below). Describe **what was actually built**, verified by your own file reads — never what was merely planned.

4. [ ] **State-of-play doc updated.** In `docs/agent_handoff.md` (the always-current one), update the "current state" header and "next steps" so they reflect the task that just shipped and the one after it — not a prior session's frontier. *This is the edit that drifts if it isn't bound to the turn. It is #4 on purpose: it's the one most often forgotten.*

---

## The close-out entry — required shape

Keep the mechanism where it belongs: precedents and traps live **once** in their canonical docs; the entry points to them, it does not restate them.

**Header block:**
```
### <TASK_ID> — <short headline, ≤20 words>

**Date:** YYYY-MM-DD
**Spec:** <path to the task spec>
**Verified by human:** <✅ YYYY-MM-DD — short confirmation quote>  |  <🟡 pending — PM-verified by reads; awaiting runtime test>
```

**Body — these sections, in this order:**
1. [ ] **What was built.** 1–3 paragraphs of concrete deliverables. A reader should learn "what does this ship enable?" without scrolling.
2. [ ] **Files touched.** Paths, one line each, NEW vs. modified. Blast-radius record, not narration.
3. [ ] **Deviations from spec.** Every variation from the spec + one line why each is acceptable. If none: `Deviations from spec: None.`
4. [ ] **Architectural impact.** One line: `None — fits pattern X.` / `Precedent N codified — see docs/agent_handoff.md.` / `Trap N codified — see docs/bug_log.md.` Pointer-only.
5. [ ] **User-facing impact.** One mandatory line, never omitted: what a *user* would notice + the user-doc pages updated in the same commit, or `None.` `None.` is an assertion a human considered the question — not a shrug.

**Length caps (hard):** single-artifact ship ≤50 lines; multi-artifact ≤75; combined-ship (2+ IDs as a unit) ≤75.

**Anti-patterns to avoid:** restating a mechanism already in the canonical doc (use a pointer); the same mechanism repeated across subsections; a table stacked on top of the prose it should replace; "to be added later" TODOs; two boilerplate one-liners instead of the single Architectural-impact line.

---

## Pending-runtime variant

If the code is PM-verified but the human hasn't run the runtime check yet: land **all four** edits now at PM-verified status (the index "verified" column and the entry's "Verified by human" line carry a **pending** note). When the human confirms, update **only those two lines**. Do **not** defer the whole close-out waiting on the runtime test — that reintroduces the drift this checklist exists to kill.
