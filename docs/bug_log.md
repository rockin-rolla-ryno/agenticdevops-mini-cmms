# CMMess — Bug Log

> Active and fixed bugs, **plus the traps log.** Consult before touching any previously-buggy area — patterns that caused a bug once tend to recur.

## Bug entries

Each bug gets an entry **before** its fix task runs; flip it to Fixed only **after** verification.

**Entry format:**
```
### BUG-NNN — <one-line symptom>   [Active | Fixed <date>]

**Reported:** <how it surfaced>
**Root cause:** <the actual cause, once known — not the symptom>
**Fix:** <what changed; link the spec/task>
**Trap (if any):** <pointer to a TRAP-NNN below if this bug revealed a reusable trap>
```

## Active

*(none)*

## Fixed

*(none)*

## Traps

A **trap** is a failure mode that will fool a future agent — most often the "**green everywhere, broken where nobody looks**" kind, where the type-checker, linter, tests, and build all pass but the thing is still wrong. The traps log is where these are recorded once, canonically, so a close-out entry can *point* to a trap instead of restating it.

**How to write a trap:** give it an id (`TRAP-NNN`) and a one-line description of the deceptive failure, then two things — **why every guard misses it** (walk typecheck → lint → tests → build and name where it actually surfaces, usually only when the real artifact runs) and **the tell** (the concrete check that *does* catch it, since the automated guards won't). Keep the traps themselves here in this doc.

*(none yet — started empty. Add a trap the first time a "green everywhere" failure teaches one. The strongest early one most projects hit: a grep that returns nothing is evidence about the grep, not the code — validate the grep against a string you know is present before trusting its silence.)*
