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

Each level can do everything the levels below it can.

```
default  <  contributors  <  maintainers  <  admins
```

`users.role` stores the level. `build_permissions()` in `routers/frontend.py` gives the frontend
its flags, and `require_route_access` enforces the same on each route: change both together.
A page the visitor can't view redirects to `/`.

### Public (not signed in)

- View a jurisdiction page and all its data: people, history, roles, posts, organizations and
  memberships.

### Default (signed in)

- Review: start, move through, pass and end a review session; publish the card being reviewed.
- Edit a roster within their own review.
- Create a post in an organization.
- Assign a person to a post and set their office label.
- View Activity.
- Read jurisdictions, people, review cards and unmatched role text through the API.
- Read a jurisdiction's collected source pages through the API; the service key may too. Not
  public. (Its governing law is on the public jurisdiction GET, as `extras_governing_law`.)

### Contributors

- View the Queue; publish or dismiss its cards; reject a scrape.
- Delete directory people.
- Say a membership ended, or never held.

### Maintainers

- Delete a person.
- Edit a jurisdiction's published data (opens a PR), and edit the live roster directly.
- Edit any jurisdiction field cp.org owns, saved at once with no PR, through
  `PATCH /api/v1/jurisdictions/{ocdid}`: its government form, governing law and the
  organizations its law sets up. One rule for every one of them: maintainers and the service
  key, nobody else.
- Edit a post's headcount and tracked state; delete a post, or fold it into another.
- Create, edit and delete organizations; choose a jurisdiction's default organization.
- Store a collected governing-law source page; the service key may too.
- Add, edit and remove roles (each opens a PR on open-data's `data_source/config.yml`).
- Scrape a single jurisdiction; read pipeline run details; resume a paused run.
- Run a curated-sheet import and publish what it produced.
- Manage their own API keys.

### Admins

- Reorder roles (opens a PR, like the other role changes).
- `/pipelines`: scrape costs, batch scrapes, cadence, cost caps and in-progress runs.
- Start a governing-law collection, for one jurisdiction or a whole state (API only), and set the
  collectors' cost caps.
- Cancel a run; read a running run's Temporal state.
- Moderate the Issues page.
- Change other users' levels; roll back a user's hand-made edits.
- Open the debug copies of the pages a scrape read.
- The admin-bus endpoints (`od_sync`, `sheet_sync` and the rest).

### Username

Every account has a `username`, chosen once at sign-up: the email-OTP form (`components/email-login`) asks for one alongside the verification code, and `POST /api/v1/auth/supabase/verify-otp` passes it to `upsert_user`, which only writes it on the row's first INSERT — a later login never overwrites it. This is what the activity feed and any other surface that shows authorship renders instead of falling back to the user's email. Usernames must be unique, and can be changed later from `/settings` (`POST /api/v1/user/username`).

### Bootstrapping the first admin

The user must have signed in via Supabase OTP at least once so a `users` row exists.

```sh
mise run grant_role -- <user-email> admins         # local dev stack, from this repo
mise run prod-grant-role -- <user-email> admins    # against civicpatch.org, from cp-infrastructure
```

Runs `src/scripts/grant_role.py` inside the app container (`docker exec` locally, `kubectl exec` in prod), not through the API: the role route takes no service key, so cluster access is what bootstrapping takes. **Sets the level unconditionally** — passing `default` demotes back to the baseline. Valid role args: `default`, `contributors`, `maintainers`, `admins`. If multiple `users` rows share an email (one per sign-in provider), every match gets the role, and their sessions are dropped so it takes effect.

**After bootstrap — admin UI:**

Once your account is at `admins`, visit `/admin/users` to manage other users' roles via clickable chips. Each user shows the chip for their current level filled in; click an outlined chip to promote/demote to that level, or click the currently-filled chip to revoke back to default. Contributor changes toggle instantly with a status toast; Maintainer and Admin changes open a confirm modal. Your own row is locked at both layers — to change your own role, use `mise run grant_role` (local) or cp-infrastructure's `prod-grant-role`.

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

