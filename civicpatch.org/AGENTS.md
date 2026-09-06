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
    sso.py          ← Supabase email-OTP request/verify proxy + logout
    webhooks/       ← inbound webhook handlers
  lib/              ← infrastructure wrappers (external APIs, storage, cache, etc.)
    github/         ← GitHub API calls, PR helpers, data sync, JWT auth
    temporal/       ← Temporal client, workflows, activities
    auth.py         ← request auth middleware + permission enforcement
    auth_session.py ← session cookie management
    redis.py, pubsub.py, storage.py, files.py, hash.py, cache.py, lock.py, csv.py, sheets.py
  core/             ← PURE domain logic, no I/O (unit-testable with zero mocks)
                       Named `<subject>_<thing>`; a subject gets a suffix only when it has
                       more than one module here, so `coverage.py` is bare and `people_*` is not.
    people_derivation.py     ← a scrape's sightings grouped into people
    people_roster.py         ← those people as the document a reviewer reads
    people_roles.py          ← which office a person's labels imply
    people_edits.py          ← what a reviewer may change: field patches and accept/reject
    people_diff.py           ← a reviewer's edits as add/edit/delete change payloads
    post_derivation.py       ← the roster turned into posts and memberships
    post_grouping.py, post_issues.py
    membership_proposal.py   ← what a scrape would change about who holds what
    membership_label.py      ← what to call a post when nobody has said
    images.py                ← `local://` refs → urls (ingest); artifacts → cdn key (publish)
    jurisdiction_patch.py, jurisdiction_search.py, coverage.py
    change_logs.py, role_taxonomy.py, temporal_workflow_state.py
    output_hash.py           ← the content gate's fingerprint, shared by every sink
    open_data/               ← tree_diff.py, paths.py — the INBOUND sync, not a sink
    sinks/                   ← how each outward mirror renders its rows
      sheet/                 ← people_rows.py, membership_rows.py, post_rows.py, jurisdiction_rows.py
      parquet.py             ← the declared column schemas
  services/         ← orchestration: coordinates lib/ + database/ + core/ (does the I/O)
    sinks/                   ← the three outward mirrors; each renders, names its target, writes
      open_data.py           ← one YAML file per jurisdiction, in git
      sheet.py               ← Live[...] tabs, per state, for a curator
      parquet.py             ← partitioned files in R2, for an analyst
    open_data_sync.py        ← open-data sync (INBOUND: git → database)
    people_csv_export.py     ← requests/people export
    people_collector.py      ← artifact processing pipeline
    jurisdiction_scrape_candidate.py ← scrape candidate selection
    pipeline_issue_resolution.py ← resolve pipeline issues via GitHub PRs
  database/         ← pure SQL queries (one file per domain)
  schemas/          ← Pydantic request/response models
    common.py       ← shared enums + models (Identity, Role, PullRequest, …)
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
- **Shared SQL predicates must not require a table alias.** A constant like `AVAILABLE_FOR_REVIEW`
  is spliced into many queries; if it says `r.published_at`, every caller has to alias that table
  `r` and nothing enforces it — a mismatch is a runtime error, never a typecheck one. Write
  `changesets.published_at` and let callers use the table unaliased.
  **The deliberate pass happened 2026-09-05**: `AVAILABLE_FOR_REVIEW`, `REVIEW_STATUS`,
  `SWEEPABLE`, `HELD_BY_REVIEWER`, `WORK_IN_FLIGHT` and `RUN_IN_FLIGHT` no longer require `r`,
  and neither do their 36 call sites across 13 files. `r` was the initial of `requests`, the
  table's name before migration 152. Aliases survive only where a query joins `changesets` to
  itself (`summary.py`'s `r2`, and the `older`/`newer` CTEs in `supersede_stacked_requests`).
  Note `roles` and `pipeline_runs` are still aliased `r` in their own modules — untouched, and
  a reason to keep any future pass file-by-file rather than mechanical.
- **UUID columns**: psycopg returns UUID columns as Python `uuid.UUID` objects. Always cast UUID columns to text in the SQL query (`id::text`, `changeset_id::text`) so callers receive plain strings — never scatter `str()` calls in routers or services. The DB function is the boundary; it owns the type contract.

## Environment

- Env vars accessed via `environment.get_env_vars()` — never read `os.environ` directly in business logic

## Layers

- **`lib/`** — infrastructure wrappers: one file (or subpackage) per external concern. Thin — call external APIs or storage and return typed results. No domain decisions.
- **`core/`** — **pure domain logic** (the functional core). No I/O: a `core/` module imports no `lib.*` / `database.*` and is unit-testable with zero mocks. Diffing, classification, field-patching, etc.
- **`services/`** — orchestration (the imperative shell): coordinates multiple `lib/`, `database/`, and `core/` calls to fulfill a domain operation. No HTTP concerns. Depends inward (`services → core`), never the reverse.
- Side effects (network calls, DB writes) live in `lib/`, `database/`, and `services/` — never in `core/` (pure) or routers.

## Database (dev)

The dev database runs in the `civicpatch-org-db` Docker container (exposed on `127.0.0.1:8003`). Connect with:

```sh
mise run psql
```

This execs `psql` inside the container, so no host postgres client is required — the container just needs to be running (`mise run dev` or `docker compose up -d civicpatch-org-db`).

## Migrations

- Migration files live in `database_operations/migrations/` and are named `NNN_description.up.sql` / `NNN_description.down.sql`
- Every migration must be wrapped in `BEGIN` / `COMMIT`
- **Every DDL statement must be idempotent** — `DROP ... IF EXISTS`, `CREATE ... IF NOT EXISTS`,
  `ADD/DROP COLUMN IF [NOT] EXISTS`. Re-running a migration has to be a no-op, not an error.
  Enforced by `tests/unit/database/test_migrations.py`, which holds everything from 141 on;
  earlier files predate the rule and must not be edited
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

Every route lives under **`/api/v1/...`** (plus `/api/admin/...` for the admin console and
`/webhooks/...` for inbound hooks). There is no separate internal surface: an endpoint the
frontend uses today is an endpoint a third party may use tomorrow, and the split only ever
told us which routes we had permitted ourselves to break.

So treat every `/api/v1/` route as a contract: renames, removals and shape changes are
deprecations, not silent edits. Design a new endpoint as a domain resource — if the shape is
only meaningful to one page, that is a reason to reconsider the shape, not to hide it behind
a prefix.

## Frontend components

- New frontend components must be written in TypeScript (`.ts`) — do not create new `.js` component files
- When importing a `.ts` component from a `.js` file, use the `.ts` extension explicitly (e.g. `import "../foo/foo.ts"`). Rollup does not resolve `.js` → `.ts` for plain JS importers; the `.js` → `.ts` remapping only works within TypeScript files.
- After any change to a frontend component, run `mise run typecheck-fe` and fix all errors before considering the task done

## CSS Style

- One property per line, each on its own indented line — no inlining multiple
  properties on the same line. Readability over compactness.
- Group conceptually related rules with lightweight section comments
  (`/* Header */`, `/* Field rows */`).
- One blank line between rule blocks, no extra vertical whitespace.

## Testing

- Framework: pytest
- **Pick the test layer deliberately.** Before writing a test, ask: what behavior am I trying to lock down, and what's the cheapest layer that exercises it honestly? Mocking is for crossing process boundaries you can't cross in the test environment (external APIs, network, sometimes the DB); it is not a tool for isolating in-process code from itself. A test that mocks five things to verify one thing is a sign you picked the wrong layer — either move down (unit-test the pure function directly with no mocks) or up (integration test with real collaborators). Don't add mocks to make a test pass; if a real call from the layer under test feels wrong to make, the layering itself is probably the issue.
- **Unit test business logic functions directly** — import and call them, mock only external boundaries (GitHub API, Redis, DB). Do not test logic through the HTTP layer.
- **Route handler tests are thin** — verify the HTTP contract only (status code, response shape). Mock the background task function itself; don't re-test its logic in route tests.
- Mock external services (GitHub, Redis, DB) at the service-call boundary — patch the module-level function, not internal implementation details.
- Tests are part of the feature — do not ship a new function or endpoint without corresponding tests unless explicitly told to skip them.
- Before writing tests, read `tests/factories/` and existing tests in the relevant `tests/unit/` directory to understand available builders and patterns.
- After writing tests, run them and fix any failures before considering the task done.
- Run tests: `mise run tcp`
- **Integration tests must not be modified unless the behavior they test has genuinely changed.** If an integration test fails during a refactor, stop and flag it before proceeding — do not edit the test to make it pass. Integration tests describe observable behavior; a failing integration test means the refactor changed behavior, which requires explicit sign-off.
- **When tests must change alongside a refactor:** enumerate each test to be changed, the behavior it previously described, and the behavior it now describes. A test is not fixed by removing assertions — that is a regression. Every test change requires a one-sentence justification: "This test verified [old claim]. It now verifies [new claim] because [reason]." If that sentence cannot be completed, the test does not change.

## End-to-end tests (Playwright)

There is a full e2e suite. It lives in **`e2e/` at the repository root** — not under
`civicpatch.org/` — with specs in `e2e/tests/` and shared fixtures in `e2e/fixtures/`.

**Always run it through mise. Never invoke `npx playwright` directly and never
`npx playwright install` by hand** — the tasks set `BASE_URL`, `E2E_DB_URL`, `E2E_REDIS_HOST`
and `E2E_REDIS_PORT`, bring the isolated stack up, and install the pinned browser. Running
Playwright by hand silently downloads a *different* browser build into the shared cache.

| task | what it does |
|---|---|
| `mise run e2e-install` | once per machine: npm deps + the pinned chromium |
| `mise run e2e` | build frontend, start the stack, open the Playwright UI, tear down on exit |
| `mise run e2e-ci` | headless in a fully isolated docker stack |
| `mise run visual` | screenshot every page in both themes, diff against the committed baseline |
| `mise run visual-update` | accept the current rendering as the new baseline — only when intended |

**A frontend change needs a rebuild *and* a container restart.** The backend caches the Vite
manifest at startup, so `npm run build` alone leaves the stack serving a stale bundle and every
failure points at the wrong thing. Both `visual` tasks do this; `e2e` rebuilds but relies on the
stack being brought up fresh.

### Writing a spec

- Start from `e2e/fixtures/index.js`: `authenticatedPage` (default role) and `maintainerPage`
  (`can_write_config`) inject session cookies; `dbFixtures` seeds and tears down automatically.
- Seed through `e2e/fixtures/db.js`, which owns the fixed ids so teardown can target them.
- **Stub what the stack has no credentials for.** GitHub, Google Sheets and Temporal are not
  reachable, so route-stub those endpoints with `page.route` and assert the client wiring — that
  each control reaches the right endpoint with the right payload and drives the right state.
- Be explicit in the spec's header comment about what stubbing does *not* cover: a stub is a
  hand-written copy of the API's shape, so it cannot catch the backend changing that shape. Only
  a seeded fixture answered by the real endpoint catches contract drift.
