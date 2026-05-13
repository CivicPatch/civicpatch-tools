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
    sso.py          ← GitHub OAuth login/logout
    webhooks/       ← inbound webhook handlers
  lib/              ← infrastructure wrappers (external APIs, storage, cache, etc.)
    github/         ← GitHub API calls, PR helpers, data sync, JWT auth
    temporal/       ← Temporal client, workflows, activities
    auth.py         ← request auth middleware + permission enforcement
    auth_session.py ← session cookie management
    redis.py, pubsub.py, storage.py, files.py, hash.py, cache.py, lock.py, csv.py, sheets.py
  core/             ← domain orchestration (coordinates lib/ + database/ calls)
    pr_sync.py               ← PR state sync
    merge.py                 ← PR merge background task
    export.py                ← requests/people export
    people_collector.py      ← artifact processing pipeline
    candidate.py             ← scrape candidate selection
    pipeline_issue_resolution.py ← resolve pipeline issues via GitHub PRs
  database/         ← pure SQL queries (one file per domain)
  schemas/          ← Pydantic request/response models
    common.py       ← shared enums + models (Identity, Role, PullRequest, …)
    jobs.py         ← job-related request/response models
    requests.py     ← cross-layer request models (HandleSubmitJobArtifactsRequest, …)
  frontend/
    vite.py         ← Jinja template helpers for Vite asset paths
  worker.py         ← Temporal worker entrypoint
  main.py           ← FastAPI app + lifespan
tests/
  unit/
  integration/
```

## Before writing code

1. Read the file(s) you are about to change — understand existing patterns before adding new ones
2. Read existing tests in the relevant `tests/unit/` or `tests/integration/` directory before writing tests
3. All queries go in `database/` — one file per domain, check there before adding a new function
4. **Before touching the database, read `DATABASE.md`** — it is the authoritative reference for table structure; do not read migration files to infer schema

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

- All queries live in `database/` — one file per domain; routers and `core/` never write SQL directly
- Use the async connection pool (`get_pool()`) — never open a raw connection outside of it
- DB functions are named after what they do: `get_jurisdiction_people`, `create_update_user`, etc.
- **UUID columns**: psycopg returns UUID columns as Python `uuid.UUID` objects. Always cast UUID columns to text in the SQL query (`id::text`, `request_id::text`) so callers receive plain strings — never scatter `str()` calls in routers or services. The DB function is the boundary; it owns the type contract.

## Environment

- Env vars accessed via `environment.get_env_vars()` — never read `os.environ` directly in business logic

## Layers

- **`lib/`** — infrastructure wrappers: one file (or subpackage) per external concern. Thin — call external APIs or storage and return typed results. No domain decisions.
- **`core/`** — domain orchestration: coordinates multiple `lib/` and `database/` calls to fulfill a domain operation. No HTTP concerns.
- Side effects (network calls, DB writes) live in `lib/` and `database/`, not in routers or `core/`.

## Database (dev)

The dev database runs in the `civicpatch-org-db` Docker container (exposed on `127.0.0.1:8003`). Connect with:

```sh
mise run psql
```

This execs `psql` inside the container, so no host postgres client is required — the container just needs to be running (`mise run dev` or `docker compose up -d civicpatch-org-db`).

## Migrations

- Migration files live in `database_operations/migrations/` and are named `NNN_description.up.sql` / `NNN_description.down.sql`
- Every migration must be wrapped in `BEGIN` / `COMMIT`
- Down migrations must exactly reverse the up migration — test that the round-trip is clean
- Create a new migration file whenever you add, rename, or drop a column, table, or index — never edit an existing migration
- **A migration is not complete until the Mermaid schema diagram in `DATABASE.md` is updated** — the diagram must always reflect the current state of the database, including index annotations (`"idx"` or `"idx: expression"`) on any affected fields

## Background tasks

- Use `BackgroundTasks` (FastAPI) for work that should not block the HTTP response — including long-running operations where the caller polls for status via a separate endpoint
- Background task functions must be defined at **module level**, not nested inside route handlers — this makes them independently importable and unit-testable
- Pass all needed context as explicit parameters; do not rely on closures over request state
- Background tasks must not silently swallow exceptions; wrap in try/except, log failures, and write error state to the appropriate store (Redis, DB)
- `asyncio.sleep` is acceptable inside background tasks — the response has already been sent, so no connection is held open

## API consumers

This API has a single consumer: the civicpatch frontend. Backward compatibility is not required — endpoints can be renamed, removed, or changed freely as long as the frontend is updated in the same changeset.

## Frontend components

- New frontend components must be written in TypeScript (`.ts`) — do not create new `.js` component files
- When importing a `.ts` component from a `.js` file, use the `.ts` extension explicitly (e.g. `import "../foo/foo.ts"`). Rollup does not resolve `.js` → `.ts` for plain JS importers; the `.js` → `.ts` remapping only works within TypeScript files.
- After any change to a frontend component, run `mise run typecheck-fe` and fix all errors before considering the task done

## Testing

- Framework: pytest
- **Unit test business logic functions directly** — import and call them, mock only external boundaries (GitHub API, Redis, DB). Do not test logic through the HTTP layer.
- **Route handler tests are thin** — verify the HTTP contract only (status code, response shape). Mock the background task function itself; don't re-test its logic in route tests.
- Mock external services (GitHub, Redis, DB) at the service-call boundary — patch the module-level function, not internal implementation details.
- Tests are part of the feature — do not ship a new function or endpoint without corresponding tests unless explicitly told to skip them.
- Before writing tests, read `tests/factories/` and existing tests in the relevant `tests/unit/` directory to understand available builders and patterns.
- After writing tests, run them and fix any failures before considering the task done.
- Run tests: `mise run tcp`
- **Integration tests must not be modified unless the behavior they test has genuinely changed.** If an integration test fails during a refactor, stop and flag it before proceeding — do not edit the test to make it pass. Integration tests describe observable behavior; a failing integration test means the refactor changed behavior, which requires explicit sign-off.
- **When tests must change alongside a refactor:** enumerate each test to be changed, the behavior it previously described, and the behavior it now describes. A test is not fixed by removing assertions — that is a regression. Every test change requires a one-sentence justification: "This test verified [old claim]. It now verifies [new claim] because [reason]." If that sentence cannot be completed, the test does not change.
