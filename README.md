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
  │  Schedules:  pr-sync (hourly)  ·  od-sync (daily)                   │
  └───────────┬──────────────────────────────┬──────────────────────────┘
              │ orchestrates                 │ orchestrates
              ▼                              ▼
  ┌───────────────────────┐      ┌───────────────────────────────────┐
  │  worker               │      │  civicpatch-org-worker            │
  │  (people-collector    │      │  (civicpatch-org-sync queue)      │
  │   queue)              │      │                                   │
  │                       │      │  · sync open-data → DB            │
  │  · trigger pipelines  │      │  · sync GitHub PR states → DB     │
  │    or GitHub Actions  │      └───────────┬───────────────────────┘
  │  · poll job status    │                  │ reads/writes
  └──────────┬────────────┘                  │
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

1. Run the following:

   ```sh
   mise install
   mise setup
   ```

2. Set up environment variables for **civicpatch** (optional — skip if you don't need to run scrapes):

   - Reference [pipelines/docker-compose.yml](./pipelines/docker-compose.yml) for available variables
   - Create `../civicpatch.env` with the variables you need

3. Set up environment variables for **civicpatch.org** (contact the maintainer for GitHub App keys):

   - Reference [civicpatch.org/docker-compose.yml](./civicpatch.org/docker-compose.yml) for available variables
   - Create `../civicpatch.org.env` with the variables you need

4. Start the dev environment:

   ```sh
   mise dev
   ```

   This starts all services and watches `worker/` and `shared/` for Python changes,
   automatically restarting the Temporal worker when code changes. Keep it running
   in a terminal while developing.

   Migrations run automatically on startup. If you need to run them manually:

   ```sh
   mise migrate_up
   ```

### Local services

| Port | Service |
|------|---------|
| 5173 | Frontend (Vite dev) |
| 6379 | Redis |
| 7233 | Temporal (gRPC) |
| 8000 | civicpatch.org API |
| 8001 | pipelines |
| 8002 | Temporal UI |
| 8003 | PostgreSQL (civicpatch.org DB) |

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
