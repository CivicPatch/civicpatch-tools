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
  frontend/
    css/styles.css          ← global styles (tokens, base, layout, buttons, utilities)
    css/components/         ← per-component stylesheets, @imported by styles.css
    pages/          ← page-level web components
    components/     ← shared web components
    api.js          ← API calls
tests/
  unit/
  integration/
  prompts/          ← LLM contracts + evals
  factories/        ← test data builders
```

## Before writing code

1. Read the file(s) you are about to change — understand existing patterns before adding new ones
2. Read `tests/factories/` and existing tests in the relevant `tests/unit/` directory before writing tests
3. Check `shared/` before implementing a utility — it may already exist

## Pipeline conventions

- `PeopleCollectorContext` is the shared state object threaded through every step; it carries the job config, logger, env vars, and accumulated step results — read it, never mutate it
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
- Do not mock what you can test directly
- **Write unit tests for any new function with meaningful logic** — pure functions, pipeline step logic, data transformations, validation. Trivial pass-through wrappers do not need tests.
- Tests are part of the feature — do not ship a new function without corresponding tests unless explicitly told to skip them.
- Before writing tests, read `tests/factories/` and existing tests in the relevant `tests/unit/` or `tests/integration/` directory to understand available builders and patterns.
- After writing tests, run them and fix any failures before considering the task done.
- Run unit tests: `docker compose run --rm civicpatch_test pytest -m unit tests/unit`

## LLM prompts

- Prompt templates live in `tests/prompts/` — contracts pin the expected output shape, evals verify quality
- When writing or modifying a prompt, update the corresponding contract test in `tests/prompts/`
- Prompt strings are single-responsibility: one task per prompt, no multi-step instructions collapsed into one string
- Variable substitution uses clearly named placeholders — document each placeholder above the prompt string with a comment

## Frontend

See [src/frontend/AI_CONTEXT.md](./src/frontend/AI_CONTEXT.md) for frontend-specific conventions.
