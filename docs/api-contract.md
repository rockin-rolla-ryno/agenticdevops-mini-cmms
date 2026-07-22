# API Contract — CMMess

> The authority for the renderer↔backend REST surface. Per `docs/contract-sync.md`,
> any endpoint/schema change moves its Pydantic model, its TypeScript type, and this
> doc **in the same commit** (Rule 12). No renderer exists yet, so the TypeScript leg
> is N/A until the renderer lands.

## Auth

**Scheme:** opaque bearer tokens. `POST /auth/login` returns a raw token;
every protected endpoint expects `Authorization: Bearer <token>`. Tokens are
stored server-side only as SHA-256; sessions expire after
`CMMESS_SESSION_TTL_HOURS` (default 24) and are treated as invalid on read.

**Enforcement pattern (DEC-005) — binding for every future protected
endpoint:** authorization is a server-side FastAPI dependency, never renderer
UI state. Use `require_user` (any valid session of an active account — both
roles) or `require_planner` (planner only) from `backend/app/auth.py`.
FS-Q3: Planner ⊇ User — a planner session passes both.

**Error semantics (uniform):**

- `401` — missing/malformed/unknown/expired token, or the session's user is
  inactive. One generic body for all of these; no distinguishing detail.
- `403` — valid session, insufficient role (e.g. `user` on a planner-only
  endpoint).
- Login failures (unknown username, wrong password, inactive account) all
  return the **same** 401 body — no username enumeration.

Accounts are seeded from a TOML config at startup (FS-Q5) — see
`docs/data-model.md`; there is no signup/registration endpoint.

TypeScript leg: N/A this task (backend-only, Architect 2026-07-22); the
renderer login task adds the TS types for these shapes.

### POST /auth/login

- **Auth:** none
- **Request model:** `LoginRequest` (`backend/app/auth.py`) — `username: str`, `password: str`
- **Response model:** `LoginResponse` — `token: str`, `user: UserOut` (`id: int`, `username: str`, `role: "user" | "planner"`)
- **Errors:** `401` generic on any failure
- **Example response (200):**

  ```json
  {"token": "…opaque…", "user": {"id": 1, "username": "planner1", "role": "planner"}}
  ```

### POST /auth/logout

- **Auth:** bearer (`require_user`-level)
- **Response:** `204 No Content`; the session is deleted — the token 401s afterwards
- **Errors:** `401` per the uniform semantics

### GET /auth/me

- **Auth:** bearer (`require_user`) — the protected-endpoint exemplar
- **Response model:** `UserOut` — `id: int`, `username: str`, `role: "user" | "planner"`
- **Errors:** `401` per the uniform semantics
- **Example response (200):**

  ```json
  {"id": 1, "username": "planner1", "role": "planner"}
  ```

## Endpoints

### GET /health

- **Path:** `/health`
- **Method:** `GET`
- **Auth:** none
- **Response model:** `HealthResponse` (`backend/app/main.py`) — `status: Literal["ok"]`
- **Example response (200):**

  ```json
  {"status": "ok"}
  ```
