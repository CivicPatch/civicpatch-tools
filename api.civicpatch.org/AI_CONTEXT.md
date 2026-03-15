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

## Testing

- Framework: pytest
- `tests/factories/` for test data builders
- Mock external services (GitHub, Redis) at the service boundary, not deeper
- Run tests: `uv run pytest api.civicpatch.org/tests`
