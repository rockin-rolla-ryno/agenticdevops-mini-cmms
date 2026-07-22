# Authority Docs by Area — CMMess

> The index that answers "**before I touch X, which one doc governs it?**" This is
> the operational half of Rule 3: read the one authority doc for the area you're
> about to touch, **before** you spec it, and cite it in the spec. One area → one
> authority doc; if two docs claim an area, that's drift — reconcile and name the
> winner.

| Area | Authority doc | Read when |
|---|---|---|
| Architecture constraints (all areas) | `docs/architecture-facts.md` | every spec — the hard constraints to enforce |
| Product behavior (features, roles, lifecycles, v1 scope) | `docs/functional-spec.md` | any feature work — what the product does, per role |
| Persistence / data model | `docs/data-model.md` *(live — authored by T-003)* | any schema, migration, or storage work |
| Renderer↔backend REST boundary | `docs/api-contract.md` *(live — seeded by T-001)* | any endpoint, request/response shape, or cross-boundary work |
| UNS / MQTT asset discovery | `docs/uns-contract.md` *(to author)* | any UNS topic-structure or MQTT-client work |
| What moves together at a boundary | `docs/contract-sync.md` | before changing **any** boundary contract (Rule 12) |
| Auth / roles (authorization) | `docs/architecture-facts.md` § Security baseline | any login, token/session, or role-gating work |
| Work-order / downtime domain | behavior: `docs/functional-spec.md` §§ 4–6 · schema: `docs/data-model.md` · constraints: `docs/architecture-facts.md` § Canonical data formats | any work-order seeding, planning/scheduling, or downtime-status logic |
| UI visual design | `docs/design-guide.md` | any UI work (tokens, type scale, component patterns) |
| Packaging / release | `docs/packaging.md` *(to author)* | any build, installer, or native-module-rebuild work |

**Notes**

- Docs marked *(to author)* don't exist yet; the area is still governed — the fact
  is captured in `docs/architecture-facts.md` until the dedicated doc is written.
  When a to-author doc lands, this index is where it's announced.
- Authorization and the work-order/downtime domain currently point at sections of
  `architecture-facts.md` rather than standalone docs. If either grows past what a
  section can hold, promote it to its own doc and move the index entry with it —
  that reconciliation is the index doing its job.
- No scar-tissue "read §X first" notes yet; this is a new project. They get added
  the first time copying a sibling's shape past where it held costs us a fix round.
