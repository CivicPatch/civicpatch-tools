# api.civicpatch.org — Project Context

See root `AI_CONTEXT.md` for shared coding standards.

## What this is

The backend API for civicpatch.org. Handles authentication, jurisdiction/people data, job orchestration, and GitHub sync.

## Project layout

```
src/
  routers/
    api/            ← versioned API routes (one file per resource)
    auth.py         ← auth routes
  services/         ← business logic (one concern per file)
  database/
    database.py     ← all DB queries
  schemas/          ← Pydantic request/response models
  stores/           ← Redis store
  utils/
  main.py           ← FastAPI app + lifespan
tests/
  unit/
  factories/
```

## Before writing code

1. Read the file(s) you are about to change — understand existing patterns before adding new ones
2. Read `tests/factories/` and existing tests in the relevant `tests/unit/` directory before writing tests
3. All queries go in `database/database.py` — check there before adding a new function

## FastAPI conventions

- Routers are created via `get_router() -> APIRouter` factory functions — one file per resource
- Auth is enforced via `Depends(require_route_access(RouteCategory.X))` — never skip it on protected routes
- Return `{"data": ...}` for all successful responses
- Pydantic models in `schemas/` define all request bodies and responses — no raw dicts across route boundaries

## Database conventions

- All queries live in `database/database.py` — routers and services never write SQL directly
- Use the async connection pool (`get_pool()`) — never open a raw connection outside of it
- DB functions are named after what they do: `get_jurisdiction_people`, `create_update_user`, etc.

## Environment

- Env vars accessed via `environment.get_env_vars()` — never read `os.environ` directly in business logic

## Services

- One file per external concern: `github_service.py`, `auth_service.py`, etc.
- Services are thin — they call DB or external APIs and return typed results
- Side effects (network calls, DB writes) live here, not in routers

## Database (dev)

The dev database is exposed on `127.0.0.1:6000`. Connect with:

```sh
psql postgres://civicpatch:development_password@127.0.0.1:6000/development_db
# or via mise:
mise run psql
```

## Migrations

- Migration files live in `database_operations/migrations/` and are named `NNN_description.up.sql` / `NNN_description.down.sql`
- Every migration must be wrapped in `BEGIN` / `COMMIT`
- Down migrations must exactly reverse the up migration — test that the round-trip is clean
- Create a new migration file whenever you add, rename, or drop a column, table, or index — never edit an existing migration
- **After every migration, update the Mermaid schema diagram in `README.md`** — the diagram must always reflect the current state of the database, including index annotations (`"idx"` or `"idx: expression"`) on any affected fields

## Background tasks

- Use `BackgroundTasks` (FastAPI) for fire-and-forget work that should not block the HTTP response — e.g., DB writes triggered by a webhook burst
- Do not use `BackgroundTasks` for work that the caller needs to observe the result of — await it directly instead
- Background tasks must not silently swallow exceptions; wrap in try/except and log failures

## Testing

- Framework: pytest
- `tests/factories/` for test data builders — never construct raw objects in test bodies
- Do not mock what you can test directly; mock external services (GitHub, Redis) at the service boundary, not deeper
- **Write unit tests for any new function with meaningful logic** — pure functions, data transformations, validation, business logic. Trivial pass-through wrappers do not need tests.
- **Write integration tests for new endpoints** — route handlers are thin wrappers; test them against a real DB, not mocks.
- Tests are part of the feature — do not ship a new function or endpoint without corresponding tests unless explicitly told to skip them.
- Before writing tests, read `tests/factories/` and existing tests in the relevant `tests/unit/` or `tests/integration/` directory to understand available builders and patterns.
- After writing tests, run them and fix any failures before considering the task done.
- Run tests: `mise run tapi`
