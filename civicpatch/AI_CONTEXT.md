# civicpatch — Project Context

See root `AI_CONTEXT.md` for shared coding standards.

## What this is

A pipeline that scrapes and processes municipal government officials data, then submits results to `api.civicpatch.org`.

## Project layout

```
src/
  jobs/people_collector/
    steps/          ← pipeline steps step_00 through step_11
    main.py         ← orchestrator
  services/         ← external integrations (LLMs, civicpatch API, search)
  domain/           ← core models
  utils/
  interfaces/
    api/            ← FastAPI app + routes
    cli/            ← CLI entrypoint
tests/
  unit/
  integration/
  prompts/          ← LLM contracts + evals
  factories/        ← test data builders
```

## Pipeline conventions

- Each step is a directory (`step_NN_name/`) containing one primary function that takes a `PeopleCollectorContext` and returns a step result schema
- Steps are pure where possible — side effects (LLM calls, HTTP) are isolated to service functions
- `WorkflowLogger` is passed through the call stack; never instantiate a new one mid-pipeline
- `shared` is importable directly: `from shared.utils import ...`

## Environment

- Env vars accessed via `civicpatch_environment.get_env_vars()` — never read `os.environ` directly in business logic
- Docker compose sets all required vars with defaults for development

## Testing

- Framework: pytest
- Markers: `unit`, `integration`, `evals`, `evals_relevant`, `contracts`
- `tests/factories/` contains builders — use them, don't build raw objects in tests
- Run unit tests: `docker compose run --rm civicpatch_test pytest -m unit tests/unit`

## Frontend

Vanilla JS web components served by FastAPI.

- **Framework:** Haunted (React-like hooks) + `lit-html`
- **Bundler:** Rollup — `npm run build` (or `npm start` to watch)
- **Entry:** `src/frontend/` — components in `components/`, Jinja2 templates in `templates/`
