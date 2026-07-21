# User Story — CMMess (Reactive CMMS)

## Combined User Story — Reactive CMMS (Process-Agnostic, Cross-Platform)

As a member of a facility's maintenance team — either a User (e.g., maintenance engineer/technician) or a Planner (e.g., maintenance manager), each with role-based access in a single shared CMMS tool — I want to track downtime on our process equipment and have that downtime drive the creation of work orders, which Planners can plan/schedule and Users can execute, against assets discoverable in a UNS structure, so that the team can respond quickly to equipment failures, plan the resulting maintenance work against the right assets, and execute it without losing time to manual tracking or asset lookup — regardless of industry, process, or plant, and regardless of what device or OS the team is running the tool on.

## Scope implied by the combined story

- **Reactive CMMS (v1)** — downtime events are the trigger: a downtime event seeds/creates a work order rather than tracking and planning being independent, disconnected capabilities. This is a reactive-maintenance model, not preventive.
- **Scales to PM later** — the data model and architecture should not preclude adding preventive maintenance (scheduled/recurring work orders independent of a downtime trigger) in a later phase. Don't build in a way that locks the product to reactive-only.
- **Role-based access, two roles** — Users and Planners are the two defined roles for v1. Multi-user, single shared tool/instance of data — not a single-operator tool.
- **Process-agnostic asset model** — the tool is not built around a specific plant, industry, or fixed equipment list (the original stamping machine / outfeed conveyor / paint workcenter example was one plant's illustration, not the product's scope). Assets are generic, configurable entities discoverable via a UNS structure, applicable to any manufacturing process or facility type.
- **Downtime tracking** — capture up/down state and downtime duration for any asset registered in the UNS, not a hardcoded set.
- **Asset discovery via UNS** — assets are addressable/discoverable through a Unified Namespace structure rather than a manually maintained static asset list, so new plants/processes/asset types can be onboarded without redesigning the data model.
- **Work order planning & execution** — downtime creates the work order; Planners plan/schedule it, Users execute it, tied to any UNS-discoverable asset.
- **Cross-platform delivery** — the tool must run across platforms (not locked to a single OS). This is a hard constraint on the technology/language choice for technical decisions — favor a stack with genuine cross-platform reach (e.g., web-based, or a cross-platform framework) over anything single-OS-native.
