# civicpatch.org

The backend API for civicpatch.org. Receives scrape results from `civicpatch`, creates PRs to the [open-data](https://github.com/CivicPatch/open-data/) repository, and exposes data to the web UI.

## What it does

- Accepts ZIP payloads from `civicpatch` pipeline jobs and opens GitHub PRs to `open-data`
- Manages jurisdiction and people data in a PostGIS/PostgreSQL database
- Authenticates users via GitHub OAuth (GitHub App)
- Exposes REST endpoints consumed by the `civicpatch` web UI
- Receives GitHub webhook events to keep PR state in sync without polling

## Project layout

```
src/
  routers/
    api/            ← versioned API routes (one file per resource)
    auth.py         ← GitHub OAuth routes
  webhooks/
    github.py       ← GitHub webhook receiver (pull_request events)
  services/         ← business logic (github_service, auth_service, etc.)
  database/
    database.py     ← all SQL queries
  schemas/          ← Pydantic request/response models
  stores/           ← Redis helpers
  utils/
  main.py           ← FastAPI app + lifespan + background tasks
database_operations/
  migrations/       ← numbered SQL migrations (NNN_description.up/down.sql)
  migrate.py        ← migration runner
tests/
  unit/
  factories/        ← test data builders
```

## Services and dependencies

| Service | Purpose | Default (dev) |
|---------|---------|---------------|
| PostgreSQL (PostGIS) | Primary data store | `localhost:8003` |
| Redis | Session/cache store | `localhost:6379` |
| GitHub App | OAuth + API access + webhooks | Contact maintainer for keys |

## Environment variables

Most values have safe development defaults in `docker-compose.yml`. The only ones that require real credentials:

| Variable | Required | Notes |
|----------|----------|-------|
| `GITHUB_APP_ID` | Yes | Contact maintainer |
| `GITHUB_APP_CLIENT_ID` | Yes | Contact maintainer |
| `GITHUB_APP_CLIENT_SECRET` | Yes | Contact maintainer |
| `GITHUB_APP_PRIVATE_KEY_BASE64` | Yes | Contact maintainer |
| `GITHUB_APP_INSTALLATION_ID` | Yes | Contact maintainer |
| `GITHUB_WEBHOOK_SECRET` | Optional | Required to receive webhook events |
| `STORAGE_ENDPOINT` / `STORAGE_ACCESS_KEY_ID` / `STORAGE_SECRET_ACCESS_KEY` | Optional | Cloudflare R2, only for zip storage |

Create `../civicpatch.org.env` with these values. Everything else in `docker-compose.yml` uses defaults.

## Permissions

Roles are assigned via GitHub team membership. The `build_permissions()` function in `routers/frontend.py` maps roles to frontend capabilities; backend routes enforce the same boundaries via `require_route_access`. Keep both in sync when changing permissions — see the CLAUDE.md note.

| Feature | default | contributors | maintainers | admins |
|---|:---:|:---:|:---:|:---:|
| Jurisdictions — read | ✓ | ✓ | ✓ | ✓ |
| People — read | ✓ | ✓ | ✓ | ✓ |
| People — create / update | | ✓ | | |
| People — delete | | ✓ | | |
| Pull requests — read / merge | ✓ | ✓ | ✓ | ✓ |
| Review sessions | ✓ | ✓ | ✓ | ✓ |
| Notes — read | ✓ | ✓ | ✓ | ✓ |
| Notes — create | | ✓ | ✓ | ✓ |
| Pipeline runs — read errors / events | | | ✓ | ✓ |
| Pipeline runs — trigger (remote) | | | ✓ | |
| Pipeline runs — trigger (local, dev only) | | | ✓ | |
| Pipeline runs — resume (paused) | | | ✓ | |
| Pipeline runs — resolve / cancel | | | | ✓ |
| Issues page (unrecognized roles, dead URLs) | | | ✓ | |

## Local setup

See the [root README](../README.md) for `mise install` / Docker setup.

Once the env file is in place:

```sh
# Start the API + database + Redis
docker compose up

# API is available at http://localhost:8000
# Database is available at localhost:8003 (PostGIS)
```

## Migrations

Migrations are numbered SQL files in `database_operations/migrations/`.

```sh
# Apply all pending migrations
mise migrate_up

# Roll back the most recent migration
mise migrate_down
```

When adding a feature that changes the schema, create a new migration file:
`NNN_description.up.sql` / `NNN_description.down.sql` — do not edit existing ones.

## Testing

```sh
# Unit tests (from workspace root)
mise tcp
```

## GitHub webhook

The API listens for `pull_request` events at `POST /webhooks/github`. It uses HMAC-SHA256 signature verification (`X-Hub-Signature-256`). On each event it updates `pull_request_status` on the corresponding `jobs` row, keeping PR state in sync without polling GitHub.

An hourly background task also reconciles DB state against GitHub's open-PR list to recover from any missed events.

To register the webhook in GitHub, set the payload URL to `https://civicpatch.org/webhooks/github` and set the secret to match `GITHUB_WEBHOOK_SECRET`.

## Database schema

See [DATABASE.md](DATABASE.md) for the full Mermaid ER diagram and column notes.

