# CMMess

A reactive **CMMS** (computerized maintenance management system) for facility maintenance teams, where **downtime drives the work**: a downtime event on any asset seeds a work order that Planners plan and schedule and Users execute — rather than tracking and planning being separate, disconnected capabilities.

## What makes it different

- **Downtime-driven.** Work orders originate from a typed, extensible trigger — an automated downtime event detected via the UNS, or manual creation by a User or Planner. v1 is reactive-only, but the origin is a first-class field so preventive/scheduled maintenance can be added later without a redesign.
- **Process-agnostic assets.** Assets are generic, configurable entities discovered through a **Unified Namespace (UNS)** rather than a hardcoded equipment list, so any industry, plant, or facility onboards without changing the data model.
- **Two roles, one shared instance.** Users (technicians/engineers) and Planners (managers) work from a single multi-user instance with role-based access, enforced server-side.
- **Cross-platform.** Delivered as a desktop app that runs across operating systems.

## Stack

- **Renderer:** Electron + TypeScript + React
- **Backend:** Python 3.12 + FastAPI, run as a separate local service
- **Persistence:** SQLAlchemy + Alembic — SQLite by default (v1/dev), Postgres supported
- **Asset discovery:** MQTT client (paho/aiomqtt) subscribing to a UNS topic structure
- **Auth:** role-based (User / Planner), enforced in the backend

The renderer talks to the backend over HTTP (localhost) and holds no business logic, database access, or MQTT access — all domain logic lives in the backend. See `docs/architecture-facts.md` for the full set of hard constraints.

## Status

**v1, in setup.** The workflow and architecture are established; the product itself is not yet scaffolded. The first task (T-001) stands up the renderer and backend skeletons with a green CI pipeline. Build/dev/release commands below become live once T-001 lands.

## Build & run

```
# Backend
pip install -r requirements.txt
uvicorn app.main:app --reload

# Renderer (Electron + Vite)
npm install
npm run dev        # develop
npm run build      # build renderer + main
npm run make       # per-OS installers (electron-forge)
```

## How this project is developed

CMMess is built with an agentic-devops loop: a human lead (architecture and behavioral testing), a PM agent (specs, verification, living docs), a coding agent, and a review agent (mechanical QA). Every change rides a spec → branch → implement → QA → read-verify → runtime-test → close-out → PR → CI loop. The governing docs live under `docs/`:

- `docs/architecture-facts.md` — the hard technical constraints every change enforces
- `docs/decision-log.md` — numbered architectural decisions with rationale
- `docs/development_workflow.md` — the branch/PR loop
- `docs/devops_pipeline.md` — what CI runs and why
- `docs/agent_handoff.md` — current state (read first)

## License

Open-source under an open license; developed from a closed repository during v1. (License file to be added.)
