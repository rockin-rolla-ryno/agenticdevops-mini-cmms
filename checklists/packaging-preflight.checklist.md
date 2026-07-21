# Checklist — Packaging Pre-Flight

**When:** before tagging a release / running the packaging pipeline. This is the **Class-B** companion to the local pre-flight command (a `npm run` script defined when the build is scaffolded): the local pre-flight catches logic/lint/test/doc failures (the things a developer machine *can* reproduce), but packaging failures live on the CI runners and in cross-platform native builds, which a local machine **cannot** reproduce. Those don't get "pre-flighted" by running them — they get caught by *reading this list before the tag*.

**Why it exists:** the source project's beta launch cost five human round-trips because each packaging failure only surfaced on the runner and revealed the next. All five are now known. The unknown sixth will be new — but the known five must never recur, and that's what a read-before-tag checklist buys.

## Read before you tag

- [ ] **Runtime version matches the developer's known-working local toolchain — not another pipeline's choice.** The packaging build compiles native code; it must use the version that compiles cleanly on the maintainer's actual machines. If the human says "we use version X," that is ground truth (Rule 19) — use X. **Node 22** is the maintainer's known-working runtime and the current test-CI runtime; no deliberate difference yet. If a native addon later fails to compile on a newer Node, pin the version that compiles cleanly and record the reason here.
- [ ] **Lock-file / package-manager version pinned to match the lock file.** A runner whose default package-manager version differs from the one that *wrote* the lock file will reject the install. Pin the writer's version. **TBD — set when the build is scaffolded (T-001)**, once a `package-lock.json` and its package-manager version exist.
- [ ] **Publish/upload side-effects are disabled unless intended.** A packaging tool that sees a version tag may try to publish a release and fail on a missing token — or worse, succeed. **TBD — set when the electron-forge release pipeline is built**: ensure the make/dist step does not auto-publish a release on a version tag (an explicit no-publish flag).
- [ ] **Runner OS image pinned where a toolchain version matters.** A `*-latest` image can silently roll to a compiler/SDK the build's toolchain can't detect yet. Pin the known-good image for the platform that's sensitive to it. **TBD — set when per-OS installers are built**: pin the runner OS image (not `*-latest`) for any platform whose toolchain version matters.
- [ ] **Per-target arch is controlled in exactly one place.** If both the build config *and* the CLI invocation set architecture, the config can silently override the flag — producing a package with the wrong native binary inside (builds green, crashes on load). Set arch in one layer only; split per-arch into separate jobs if needed. **TBD — set when per-arch packaging is built**: control target architecture in exactly one layer (build config *or* CLI flag, not both).
- [ ] **Every platform's installer built from one commit, and the maintainer launched the primary one.** Green build ≠ launches. The human runtime-tests the real installer on the real target before it's called done (Rule 14 for packaging).

## The general shape

Local pre-flight handles what a dev machine can reproduce. This list handles what only the runner and cross-platform native builds reveal. When a *new* packaging gotcha surfaces, add a line here and a comment at its point-of-use in the CI config — so it's read before the next tag, not rediscovered on the next runner.
