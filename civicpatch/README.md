# civicpatch

Scrapes municipal government websites to collect contact information for elected officials, then submits the results to [api.civicpatch.org](../api.civicpatch.org/README.md) for publication in the [open-data](https://github.com/CivicPatch/open-data/) repository.

## Data collected

- Name, role (Mayor, Council Member, etc.), division (Ward 1, At-Large, etc.)
- Email, phone, website
- Profile image

## How it works

Each scrape job runs a pipeline against a single jurisdiction (identified by an [OCD-ID](https://github.com/opencivicdata/ocd-division-ids)):

| Step | What it does |
|------|-------------|
| 0. Prepare | Clears cache and log files for the jurisdiction |
| 1. Research municipality | Uses an LLM (Google Gemini) with web search to identify elected officials and their roles |
| 2. Search links | Finds URLs likely to contain official contact pages |
| 3. Scrape pages | Fetches and renders pages (via Patchright/Playwright) |
| 4. Preprocess content | Cleans and chunks raw page content |
| 5. Process content | Uses an LLM to extract structured people data from page content |
| 6. Merge within LLM | Deduplicates results from a single LLM pass |
| 7. Merge across LLMs | Reconciles results across multiple LLM passes |
| 8. Format output | Resolves people IDs against existing records in the API |
| 9. Cleanup | Removes temporary files |
| 10. Save output | Writes YAML data files and reports results to api.civicpatch.org |
| 11. Maybe send to GitHub | Optionally opens a PR to the open-data repo |

Pipeline steps live in `src/jobs/people_collector/steps/`, one directory per step.

## Project layout

```
src/
  jobs/people_collector/
    steps/          ← pipeline steps (step_00 through step_11)
    main.py         ← orchestrator
    schemas.py      ← workflow context and step result schemas
  services/         ← external integrations (LLMs, search, civicpatch API)
  domain/           ← core models
  utils/
  interfaces/
    api/            ← FastAPI app (job management UI + API)
    cli/            ← CLI entrypoint
tests/
  unit/
  integration/
  prompts/          ← LLM contracts + evals
  factories/        ← test data builders
```

## Development setup

See the [root README](../README.md) for Docker and environment setup.

Environment variables are documented in [docker-compose.yml](./docker-compose.yml). The minimum required to run the pipeline:

| Variable | Purpose |
|----------|---------|
| `GOOGLE_GEMINI_TOKEN` | LLM calls and web search |
| `TOGETHER_AI_TOKEN` | Secondary LLM |
| `GOOGLE_SEARCH_TOKEN` + `GOOGLE_SEARCH_ENGINE_ID` | Link search |
| `API_CIVICPATCH_ORG_URL` | Where to submit results |
| `SERVICE_API_KEY` | Auth for api.civicpatch.org |

## Running a scrape locally

Trigger a job via the web UI (`http://localhost:8000`) or the CLI:

```sh
docker compose run --rm civicpatch uv run python -m interfaces.cli.main --jurisdiction-ocdid ocd-division/country:us/state:ca/place:oakland
```

## Testing

```sh
mise test-cp
```

## Contributing

### Adding or fixing a pipeline step

Each step in `src/jobs/people_collector/steps/` is a directory with a single primary function that takes a `PeopleCollectorContext` and returns a typed result. To add a step:

1. Create a new `step_NN_name/` directory with a `name.py` file
2. Define the step result schema in `schemas.py`
3. Wire it into `main.py`

### Adding shared utilities

Logic reusable across `civicpatch` and `api.civicpatch.org` belongs in the [`shared`](../shared/) workspace package.

### Code standards

See [AI_CONTEXT.md](./AI_CONTEXT.md).
