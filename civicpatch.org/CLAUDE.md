# civicpatch.org — Project Context

See root `CLAUDE.md` for shared coding standards.

## What this is

The backend API for civicpatch.org. Handles authentication, jurisdiction/people data, job orchestration, and GitHub sync.

## Project layout

```
src/
  routers/
    api/            ← versioned API routes (one file per resource)
    frontend.py     ← page routes + permissions
    auth.py         ← auth routes
  services/         ← business logic (one concern per file)
  database/
    database.py     ← all DB queries
  schemas/          ← Pydantic request/response models
  stores/           ← Redis store
  utils/
  main.py           ← FastAPI app + lifespan
  frontend/         ← JS/CSS/templates (served at /frontend)
tests/
  unit/
  factories/
```

## Before writing code

1. Read the file(s) you are about to change — understand existing patterns before adding new ones
2. Read `tests/factories/` and existing tests in the relevant `tests/unit/` directory before writing tests
3. All queries go in `database/database.py` — check there before adding a new function
4. **Before touching the database, read the schema diagram in `README.md`** — it is the authoritative reference for table structure; do not read migration files to infer schema

## Permissions

The role → capability mapping is documented in `README.md` under the **Permissions** section. Before adding or changing any `require_route_access` call or modifying `build_permissions()` in `routers/frontend.py`:

1. Read the Permissions table in `README.md` to understand the intended policy
2. Update `README.md` to reflect any changes you make to `build_permissions()` or route-level enforcement
3. Keep frontend permissions (`build_permissions`) and backend enforcement (`require_route_access`) in sync — a permission granted on the frontend must be enforceable by the corresponding API route

## FastAPI conventions

- Routers are created via `get_router() -> APIRouter` factory functions — one file per resource
- Auth is enforced via `Depends(require_route_access(RouteCategory.X))` — never skip it on protected routes
- Return `{"data": ...}` for all successful responses
- Pydantic models in `schemas/` define all request bodies and responses — no raw dicts across route boundaries

## Database conventions

- All queries live in `database/database.py` — routers and services never write SQL directly
- Use the async connection pool (`get_pool()`) — never open a raw connection outside of it
- DB functions are named after what they do: `get_jurisdiction_people`, `create_update_user`, etc.
- **UUID columns**: psycopg returns UUID columns as Python `uuid.UUID` objects. Always cast UUID columns to text in the SQL query (`id::text`, `request_id::text`) so callers receive plain strings — never scatter `str()` calls in routers or services. The DB function is the boundary; it owns the type contract.

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

- Use `BackgroundTasks` (FastAPI) for work that should not block the HTTP response — including long-running operations where the caller polls for status via a separate endpoint
- Background task functions must be defined at **module level**, not nested inside route handlers — this makes them independently importable and unit-testable
- Pass all needed context as explicit parameters; do not rely on closures over request state
- Background tasks must not silently swallow exceptions; wrap in try/except, log failures, and write error state to the appropriate store (Redis, DB)
- `asyncio.sleep` is acceptable inside background tasks — the response has already been sent, so no connection is held open

## API consumers

This API has a single consumer: the civicpatch frontend. Backward compatibility is not required — endpoints can be renamed, removed, or changed freely as long as the frontend is updated in the same changeset.

## Testing

- Framework: pytest
- `tests/factories/` for test data builders — never construct raw objects in test bodies
- **Unit test business logic functions directly** — import and call them, mock only external boundaries (GitHub API, Redis, DB). Do not test logic through the HTTP layer.
- **Route handler tests are thin** — verify the HTTP contract only (status code, response shape). Mock the background task function itself; don't re-test its logic in route tests.
- Mock external services (GitHub, Redis, DB) at the service-call boundary — patch the module-level function, not internal implementation details.
- Tests are part of the feature — do not ship a new function or endpoint without corresponding tests unless explicitly told to skip them.
- Before writing tests, read `tests/factories/` and existing tests in the relevant `tests/unit/` directory to understand available builders and patterns.
- After writing tests, run them and fix any failures before considering the task done.
- Run tests: `mise run tapi`
