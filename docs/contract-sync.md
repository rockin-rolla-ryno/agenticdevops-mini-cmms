# Contract-Sync — CMMess

> The project-specific form of **Rule 12**: when a module-boundary contract changes,
> its typed surfaces **and** its human-readable doc move **in the same commit**.
> Stale contract docs mean broken code at a boundary — the failure surfaces at
> runtime, in a different module than the one edited. The only defense that holds is:
> the contract, its schema, its typed surface, and its doc all change together.

## What counts as a "contract" here

Anything two independently-editable parts of CMMess agree on:

- the **renderer↔backend REST API** (endpoint paths, request/response shapes);
- **Pydantic** request/response models and their matching **TypeScript** types;
- **SQLAlchemy** models / the persisted schema and its **Alembic** migrations;
- the **UNS topic structure** the backend subscribes to for asset discovery;
- any other format one part writes and another reads.

## The mapping — when a spec changes X, it also updates Y (same commit)

| Change | Must also update, same commit |
|---|---|
| A REST endpoint, or its request/response shape | the Pydantic model **+** the matching TypeScript type **+** `docs/api-contract.md` |
| A Pydantic model used at the boundary | its TypeScript type counterpart **+** `docs/api-contract.md` |
| A SQLAlchemy model / persisted schema | the Alembic migration (runnable on **both** SQLite and Postgres) **+** `docs/data-model.md` |
| The UNS topic structure the backend subscribes to | the MQTT-client subscription code **+** `docs/uns-contract.md` |
| Any other serialized on-the-wire / on-disk format | that format's spec doc |

## How the PM enforces it

- The **spec** lists the required doc + typed-surface edits explicitly, so the coding
  agent makes them alongside the code (spec-authoring checklist has the contract-sync
  line).
- The **review agent** flags any diff that changes a contract with no matching doc
  change.
- `<<ADOPT-IF: contract drift recurs despite the above — add a CI check that fails a
  contract change shipped with no matching doc change. Implement it as a ratchet: the
  check fails on the forbidden pattern everywhere except an allowlist of known offenders
  that may only ever shrink, never grow.>>`
