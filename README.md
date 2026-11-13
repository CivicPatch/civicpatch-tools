# civicpatch-tools

Tools that collect, process and publish data on elected municipal officials in the US.
The data lives in [open-data](https://github.com/CivicPatch/open-data/).

## Projects

- [pipelines](./pipelines/README.md): scrapes municipal websites for elected officials.
- [civicpatch.org](./civicpatch.org/README.md): the API and review site; syncs results with open-data.
- [shared](./shared/): Python code both use.

## Architecture

```
  ┌─────────────────────────────────────────────────────────────────────┐
  │  Temporal (workflow engine)                        UI :8002 (local) │
  │                                                                     │
  │  Schedules:  one scrape per state with a cadence (state_settings)   │
  │              open-data-sync (hourly)                                │
  │              sinks: activity feed (1m), recent changes (5m),        │
  │                     everything (daily)                              │
  │              two cleanups (10m / 15m)                               │
  └───────────┬──────────────────────────────┬──────────────────────────┘
              │ orchestrates                 │ orchestrates
              ▼                              ▼
  ┌───────────────────────┐      ┌───────────────────────────────────┐
  │  scrape worker        │      │  four background workers          │
  │  (civicpatch-         │      │                                   │
  │   pipeline-runs)      │      │  source   open-data → DB          │
  │                       │      │  sinks    DB → sheet, open-data,  │
  │  - trigger pipelines  │      │           R2, live activity feed  │
  │    or GitHub Actions  │      │  cleanup  retire stale work       │
  │  - poll job status    │      │  maps     map tiles → R2 (CDN)    │
  └──────────┬────────────┘      └───────────┬───────────────────────┘
             │ calls                         │ reads/writes
             ▼                               ▼
  ┌──────────────────────┐       ┌───────────────────────┐
  │  pipelines           │       │  civicpatch.org API   │◄── GitHub webhooks
  │  :8001 (local)       │       │  :8000 (local)        │◄── browser / frontend
  │                      │       │                       │◄── agents (MCP, API keys)
  │  - scrapes municipal │       │  - job registration   │
  │    websites          │       │  - PR review UI       │
  │  - formats output    │       │  - data API           │
  │  - submits ZIP       │       │  - MCP server, OAuth  │
  │                      │       │  - roster comparisons │
  └──────────┬───────────┘       └──────────┬────────────┘
             │                              │ reads/writes
             │                              ├─────────────────────────┐
             │                              ▼                         ▼
             │ submits ZIP       ┌───────────────────────┐   ┌──────────────────────┐
             └──────────────────►│  PostgreSQL DB        │   │  Redis :6379         │
                                 │  :8003 (local)        │   │  cache, locks,       │
                                 └───────────────────────┘   │  activity pub/sub    │
                                              │              └──────────────────────┘
  ┌───────────────────────────────────────────┘
  │ sinks worker commits YAML
  ▼
  open-data repo (GitHub)  ──►  data consumers
```

## Contributing

Join [Unified - Civic Data Tech](https://unified.me/chat/!NcnsrToWrvzzzoLHWn) for the weekly sync and
the biweekly hackathons. Work is tracked in [Issues](https://github.com/orgs/CivicPatch/projects/3).

Support us on [ko-fi](https://ko-fi.com/civicpatch).

## Development

### Requirements

- [mise](https://mise.jdx.dev/getting-started.html), Docker, and a GitHub account
- `gh auth login`

### Setup

```sh
mise run setup
```

Safe to rerun: it only fills in what's missing. It:

1. Installs tools, dependencies and git hooks.
2. Asks for LLM keys (OpenRouter, Gemini) and saves them to `../pipelines.env`. Only evals need them.
3. Optionally sets up your own GitHub, so the app can update repos: an org `dev-cp-<login>`, forks of
   open-data and jurisdictions, and two GitHub Apps. Keys go to `civicpatch.org.env` in the folder
   that holds this repo (not inside it), and setup prints the full path when it finishes.

Keys off disk instead: set `INFISICAL_DOMAIN` and `INFISICAL_PROJECT_ID` in your own mise config,
`infisical login`, then `mise run setup-github -- --store infisical`.

### Run

```sh
mise run dev            # Supabase + docker compose; Ctrl+C stops both
mise run seed-dev-data  # sample data from the public open-data dataset
```

Migrations run on startup.

### Log in

1. Open http://localhost:8000 and sign in with any email.
2. `mise run otp` prints the code (or open Mailpit: http://localhost:54324).

Give yourself a role: `mise run grant_role you@example.com admins`
(lowest to highest: `default`, `contributors`, `maintainers`, `admins`).

### Ports

| Port  | Service                        |
| ----- | ------------------------------ |
| 6379  | Redis                          |
| 7233  | Temporal (gRPC)                |
| 8000  | civicpatch.org API             |
| 8001  | pipelines                      |
| 8002  | Temporal UI                    |
| 8003  | PostgreSQL (civicpatch.org DB) |
| 8004  | Frontend (Vite dev)            |
| 9000  | Object storage (s2, R2 stand-in) |
| 9001  | s2 web console                 |
| 54321 | Supabase                       |
| 54324 | Mailpit (local OTP emails)     |

Photos and Debug copies load from `*.s2.localhost:9000`, so on a remote machine forward 9000 along with 8000.

## Testing

```sh
mise run tpipes   # pipelines
mise run tcp      # civicpatch.org
mise run evalsm   # LLM evals: paid, needs the LLM keys
```

## License

[MIT](LICENSE.txt)
