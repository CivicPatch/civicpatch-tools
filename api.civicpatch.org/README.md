# api.civicpatch.org

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
| PostgreSQL (PostGIS) | Primary data store | `localhost:6000` |
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

Create `../api.civicpatch.org.env` with these values. Everything else in `docker-compose.yml` uses defaults.

## Local setup

See the [root README](../README.md) for `mise install` / Docker setup.

Once the env file is in place:

```sh
# Start the API + database + Redis
docker compose up

# API is available at http://localhost:8001
# Database is available at localhost:6000 (PostGIS)
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
mise tapi
```

## GitHub webhook

The API listens for `pull_request` events at `POST /webhooks/github`. It uses HMAC-SHA256 signature verification (`X-Hub-Signature-256`). On each event it updates `pull_request_status` on the corresponding `jobs` row, keeping PR state in sync without polling GitHub.

An hourly background task also reconciles DB state against GitHub's open-PR list to recover from any missed events.

To register the webhook in GitHub, set the payload URL to `https://api.civicpatch.org/webhooks/github` and set the secret to match `GITHUB_WEBHOOK_SECRET`.

## Database schema

> **Keep this diagram in sync with migrations.** Whenever a migration adds, renames, or drops a column or table, update the chart below.

```mermaid
erDiagram
    %% idx = regular index, functional idx noted inline
    users {
        text provider PK
        text provider_user_id PK
        text email
        text display_name
        text server_url
        bool is_approved
        timestamptz created_at
    }

    jurisdictions {
        text jurisdiction_ocdid PK
        text state
        text status
        jsonb data "idx: (data->>'geoid'), LOWER(data->>'name')"
        text file_path
        text git_commit
        timestamp updated_at
    }

    requests {
        uuid id PK
        text status
        text request_type
        text jurisdiction_ocdid FK
        jsonb arguments_json
        jsonb result_data
        jsonb review_json "idx: jsonb_array_length(review_json->'issues')"
        timestamptz created_at
        timestamptz updated_at
    }

    jobs {
        int id PK
        uuid request_id FK "idx"
        text requested_by_provider "idx: (requested_by_provider, requested_by_provider_user_id)"
        text requested_by_provider_user_id
        int progress
        text status "idx"
        text server_source
        text run_url
        text pull_request_review_state_to_delete "idx"
        timestamptz created_at
        timestamptz updated_at
    }

    pull_requests {
        uuid id PK
        uuid request_id FK
        int pr_number
        text url
        text status
        text review_state
        timestamptz closed_at
        timestamptz merged_at
        timestamptz created_at
        timestamptz updated_at
    }

    people {
        uuid id PK
        text jurisdiction_ocdid FK
        jsonb data
        text file_path
        text git_commit
        text status
        timestamptz updated_at
    }

    unrecognized_roles {
        uuid id PK
        uuid request_id FK "idx"
        text role
        text person_name
        text status "idx"
        text pr_url
        timestamptz created_at
    }

    notes {
        uuid id PK
        text jurisdiction_ocdid FK "idx"
        text body
        text user_id
        timestamptz created_at
    }

    jurisdictions ||--o{ requests : "jurisdiction_ocdid"
    jurisdictions ||--o{ people : "jurisdiction_ocdid"
    jurisdictions ||--o{ notes : "jurisdiction_ocdid"
    requests ||--o| jobs : "request_id"
    requests ||--o| pull_requests : "request_id"
    requests ||--o{ unrecognized_roles : "request_id"
```

**Notes:**
- `requests.result_data` — array of scraped `Official` objects returned by the civicpatch pipeline
- `requests.review_json` — pipeline review output (`issues`, `warnings`, etc.)
- `people.data` — full `Official` JSONB blob; the canonical record for a jurisdiction's current officials
- `jurisdictions.data` — jurisdiction metadata (name, geoid, etc.)
- `jobs` and `pull_requests` each have a unique constraint on `request_id` (one-to-one with `requests`)
- `people` has no FK to `requests` — it is updated independently when a PR is merged

