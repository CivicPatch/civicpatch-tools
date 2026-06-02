# civicpatch.org

The backend API for civicpatch.org. Receives scrape results from `civicpatch`, creates PRs to the [open-data](https://github.com/CivicPatch/open-data/) repository, and exposes data to the web UI.

## What it does

- Accepts ZIP payloads from `civicpatch` pipeline jobs and opens GitHub PRs to `open-data`
- Manages jurisdiction and people data in a PostGIS/PostgreSQL database
- Authenticates users via Supabase email OTP
- Exposes REST endpoints consumed by the `civicpatch` web UI
- Receives GitHub webhook events to keep PR state in sync without polling

## Project layout

```
src/
  routers/
    api/            ← versioned API routes (one file per resource)
    sso.py          ← Supabase email-OTP callback + logout
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
| Supabase | Auth (email-OTP, JWT issuance, email delivery via Resend SMTP) | Cloud Supabase project |
| GitHub App | Open-data PR creation, file reads, webhooks | Contact maintainer for keys |

## Environment variables

Most values have safe development defaults in `docker-compose.yml`. The only ones that require real credentials:

| Variable | Required | Notes |
|----------|----------|-------|
| `GITHUB_APP_ID` | Yes | Contact maintainer |
| `GITHUB_APP_PRIVATE_KEY_BASE64` | Yes | Contact maintainer |
| `GITHUB_APP_INSTALLATION_ID` | Yes | Contact maintainer |
| `SUPABASE_URL` | Yes | Your Supabase project URL (`https://<ref>.supabase.co`) |
| `SUPABASE_SECRET_KEY` | Yes | Server-only. The backend is the only thing that talks to Supabase. |
| `GITHUB_WEBHOOK_SECRET` | Optional | Required to receive webhook events |
| `STORAGE_ENDPOINT` / `STORAGE_ACCESS_KEY_ID` / `STORAGE_SECRET_ACCESS_KEY` | Optional | Cloudflare R2, only for zip storage |

Create `../civicpatch.org.env` with these values. Everything else in `docker-compose.yml` uses defaults.

## Permissions

Roles are a **trust ladder** — each level inherits everything below it.

```
default  <  contributors  <  maintainers  <  admins
```

Stored as a single `users.role` column. The `build_permissions()` function in `routers/frontend.py` maps the ladder to frontend capabilities; backend routes enforce the same boundaries via `require_route_access(category, required_role)`. Keep both in sync when changing permissions — see the CLAUDE.md note.

### What each level adds

| Level | Capabilities introduced at this level (all lower-level capabilities are inherited) |
|---|---|
| **default** (any signed-in user) | Read-only API access: list jurisdictions, people, pull requests. Read review session stats and active session. View the Activity page (change log of trusted-contributor curation activity). (No editor pages — Queue / Reviews / Issues all require Contributor+.) |
| **contributors** | View the Queue page. Edit jurisdiction details via PRs. Create / update / delete directory people. Create / navigate / pass / end review sessions. Close / merge / update pull requests. |
| **maintainers** | Trigger pipeline runs (single + batch). Read & edit role configs (state and locality scope). Read pipeline run details. Resume paused runs. View the Quarantine bucket on the Activity page (changes from untrusted default-role contributors, awaiting spam/profanity review). |
| **admins** | View and moderate the Issues page (flag, dismiss, resolve). Manage other users' trust levels (via `/admin`). Cancel pipeline runs. Edit global role config. View queue page errors. All admin-bus endpoints (od_sync, pr_sync, etc.). |

### Display name onboarding

Independent of role, every signed-in user is redirected to `/settings` until they pick a `display_name`. This is enforced by middleware (`lib/middleware.py`) so the activity feed and any other surface that shows authorship can render a user-chosen handle instead of falling back to the user's email. New users see a suggested name (e.g. `wandering-meadow`) prefilled in the form; they can accept it or type their own. Display names must be unique.

### Bootstrapping the first admin

The user must have signed in via Supabase OTP at least once so a `users` row exists.

**Preferred — `mise run grant_role`:**

```sh
mise run grant_role -- <user-email> admins         # local dev
mise run grant_role_prod -- <user-email> admins    # against civicpatch.org
```

Authenticates via `SERVICE_API_KEY` (local) or `$PROD_SERVICE_API_KEY` (prod). Hits the same `PUT /api/admin/users/{id}/role` endpoint the admin UI uses. **Sets the level unconditionally** — passing `default` demotes back to the baseline. Valid role args: `default`, `contributors`, `maintainers`, `admins`. If multiple `users` rows share an email (rare; legacy pre-Supabase rows), the task sets the role on all matches.

**After bootstrap — admin UI:**

Once your account is at `admins`, visit `/admin` to manage other users' roles via clickable chips. Each user shows the chip for their current level filled in; click an outlined chip to promote/demote to that level, or click the currently-filled chip to revoke back to default. Contributor changes toggle instantly with a status toast; Maintainer and Admin changes open a confirm modal. Your own row is locked at both layers — to change your own role, use `mise run grant_role`.

**Fallback — direct SQL:**

```sql
UPDATE users SET role = 'admins'
WHERE provider='supabase' AND email='<user-email>';
```

The session picks up the new role on the next request — no logout required.

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

## Links

- [Democracy Club — Volunteer](https://candidates.democracyclub.org.uk/volunteer/) — a similar volunteer-driven project in the UK that verifies candidate data for elections

