# civicpatch-tools

A collection of tools and projects supporting the collection, processing, and publication of data on elected municipal officials across the United States.

To view the full dataset, see the [open-data](https://github.com/CivicPatch/open-data/) repository.

## Table of Contents

- [Description](#description)
- [Projects](#projects)
- [Summary](#summary)
- [Development](#development)
- [Testing](#testing)
- [License](#license)
- [Contact](#contact)

## Description

This repository contains supporting infrastructure for the CivicPatch initiative, which aims to make information about municipal officials more accessible and transparent. It includes scrapers, APIs, and automation for data collection and publication.

## Projects

- [pipelines](./pipelines/README.md)
  The main project. Scrapes municipal websites for contact information on elected officials. Scrape jobs are run via GitHub Actions or by volunteers, and results are submitted to the open-data repo.
- [civicpatch.org](./civicpatch.org/README.md)
  Coordinates data submissions between civicpatch servers and the open-data repo. Receives GitHub webhook events to keep pull request state in sync.
- [shared](./shared/)
  Python utilities shared across both projects — import as `from shared.utils import ...`. Put cross-cutting logic here rather than duplicating it.

## Architecture

```
  ┌─────────────────────────────────────────────────────────────────────┐
  │  Temporal (workflow engine)                        UI :8002 (local) │
  │                                                                     │
  │  Schedules:  od-sync (hourly)  ·  sweep-changes (5m)                │
  │              sweep-everything (daily)  ·  two cleanups (10m / 15m)  │
  └───────────┬──────────────────────────────┬──────────────────────────┘
              │ orchestrates                 │ orchestrates
              ▼                              ▼
  ┌───────────────────────┐      ┌───────────────────────────────────┐
  │  scrape worker        │      │  three background workers         │
  │  (civicpatch-         │      │                                   │
  │   pipeline-runs)      │      │  jurisdictions  open-data → DB    │
  │                       │      │  sinks          DB → sheet,       │
  │  · trigger pipelines  │      │                 open-data, R2     │
  │    or GitHub Actions  │      │  expiry         retire stale work │
  │  · poll job status    │      └───────────┬───────────────────────┘
  └──────────┬────────────┘                  │ reads/writes
             │ calls                         ▼
             ▼                   ┌───────────────────────┐
  ┌──────────────────────┐       │  civicpatch.org API   │◄── GitHub webhooks
  │  pipelines           │       │  :8000 (local)        │◄── browser / frontend
  │  :8001 (local)       │       │                       │
  │                      │       │  · job registration   │
  │  · scrapes municipal │       │  · PR review UI       │
  │    websites          │       │  · data API           │
  │  · formats output    │       └──────────┬────────────┘
  │  · submits ZIP       │                  │ reads/writes
  └──────────┬───────────┘                  ▼
             │ submits ZIP       ┌───────────────────────┐
             └──────────────────►│  PostgreSQL DB        │
                                 │  :8003 (local)        │
                                 └───────────────────────┘
                                              │
  ┌───────────────────────────────────────────┘
  │ on merge / data sync
  ▼
  open-data repo (GitHub)  ──►  PR created  ──►  data consumers
```

## Support

[![ko-fi](https://ko-fi.com/img/githubbutton_sm.svg)](https://ko-fi.com/civicpatch)

## Contributing

Join the [Unified - Civic Data Tech](https://unified.me/chat/!NcnsrToWrvzzzoLHWn) group and
join our weekly sync and biweekly hackathon meetings.

- Weekly Sync — Introductions and Updates
- Biweekly Hackathons — Onboarding, bug bashing

[Issues](https://github.com/orgs/CivicPatch/projects/3)

## Development

### Requirements

- Docker (required for running services; tested on OSX)
- [mise](https://mise.jdx.dev/getting-started.html) (for managing environments and scripts)
  - `brew install openssl readline` (for postgres tool)

- A [github](https://github.com/) account
  - Poke a maintainer [michelle@civicpatch.org], or see [Contributing](#contributing) guide for onboarding
    for additional setup as needed. This project integrates heavily with the [open-data](https://github.com/CivicPatch/open-data)
    repo and multiple other services so you'll either want to set up your own mirror repos and corresponding
    github apps, or you can use keys provided for you during onboarding.

### Setup

1. Install workspace dependencies (mise tools, pre-commit hooks, uv packages):

   ```sh
   mise setup
   ```

2. Set up environment variables for **civicpatch** (optional — skip if you don't need to run scrapes):
   - Reference [pipelines/docker-compose.yml](./pipelines/docker-compose.yml) for available variables
   - Create `../pipelines.env` with the variables you need

3. Set up environment variables for **civicpatch.org**:
   - Create `../civicpatch.org.env` (reference [civicpatch.org/docker-compose.yml](./civicpatch.org/docker-compose.yml) for the full list)
   - The app boots without any of these, but specific features won't work until you set them:
     - GitHub PR / open-data sync — needs `GITHUB_APP_ID`, `GITHUB_APP_PRIVATE_KEY_BASE64`, `GITHUB_APP_INSTALLATION_ID`
     - Jurisdiction edits — needs `JURISDICTIONS_SYNC_APP_ID`, `JURISDICTIONS_SYNC_APP_PRIVATE_KEY_BASE64`, `JURISDICTIONS_SYNC_APP_INSTALLATION_ID`
     - File uploads / CDN — needs `STORAGE_ENDPOINT`, `STORAGE_ACCESS_KEY_ID`, `STORAGE_SECRET_ACCESS_KEY`
     - Google Sheets sync — needs `GOOGLE_SHEETS_*`
     - GitHub webhook verification — needs `GITHUB_WEBHOOK_SECRET`
   - Contact a maintainer for GitHub App keys, or set up your own mirror apps

4. Start the dev environment:

   ```sh
   mise dev
   ```

   This brings up two layers:
   - **Local Supabase stack** (via the Supabase CLI) — handles auth and captures all outbound email in Mailpit at http://localhost:54324. The CLI-generated `SUPABASE_SECRET_KEY` is auto-injected into docker compose.
   - **Docker compose stack** — civicpatch.org API, pipelines, Temporal, Redis, Postgres, FE dev server.

   The Temporal worker hot-reloads when files under `worker/` or `shared/` change. Migrations run automatically on startup; to run them manually:

   ```sh
   mise migrate_up
   ```

   Ctrl+C tears both layers down.

### Logging in (local)

civicpatch.org uses Supabase email-OTP. Locally, no real email is sent — Mailpit captures everything.

1. Open http://localhost:8000 and start the sign-in flow
2. Enter any email address (it doesn't need to exist; Mailpit catches it locally)
3. Grab the 6-digit code one of these ways:

   ```sh
   mise otp
   ```

   …or open Mailpit in a browser: http://localhost:54324

4. Enter the code on the verify screen

To grant your local user a role (e.g. for `/admin` access):

```sh
mise run grant_role you@example.com admins
```

Roles, lowest → highest: `default`, `contributors`, `maintainers`, `admins`.

### Local services

| Port  | Service                                   |
| ----- | ----------------------------------------- |
| 5173  | Frontend (Vite dev)                       |
| 6379  | Redis                                     |
| 7233  | Temporal (gRPC)                           |
| 8000  | civicpatch.org API                        |
| 8001  | pipelines                                 |
| 8002  | Temporal UI                               |
| 8003  | PostgreSQL (civicpatch.org DB)            |
| 54321 | Supabase (local, managed by Supabase CLI) |
| 54324 | Mailpit (captures local OTP emails)       |

## Testing

- Each project contains its own test suite.

### pipelines

```sh
mise tpipes
```

### civicpatch.org

```sh
mise tcp
```

## License

[MIT License](LICENSE.txt)

## Contact

For questions or contributions, open an issue or contact the maintainers via GitHub.
