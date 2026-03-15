# civicpatch AI Context

A pipeline tool for scraping and processing municipal government officials data, then submitting results to api.civicpatch.org.

## Project layout

```
src/          ← package root (installed as editable, no src. prefix needed)
tests/
  unit/
  integration/
  prompts/    ← contracts + evals
  factories/  ← test data builders
```

Pipeline steps live in `src/jobs/people_collector/steps/`, numbered `step_00` through `step_11`.

## Testing

- Framework: pytest
- Imports use the package root directly: `from services.civicpatch_api import ...` (no `src.` prefix)
- Markers: `unit`, `integration`, `evals`, `evals_relevant`, `contracts`
- `tests/factories/` contains builders for common test objects

## Frontend

Vanilla JS web components served by FastAPI (Jinja2 templates + static files).

- **Framework:** [Haunted](https://github.com/matthewp/haunted) (React-like hooks for web components) + `lit-html` for rendering
- **Bundler:** Rollup — `npm run build` (or `npm start` to watch)
- **Entry:** `src/frontend/` — components in `components/`, pages in `templates/pages/`, Jinja2 templates in `templates/`
- Hot reload is enabled in non-production via `arel`

## Key conventions

- Pipeline steps live in numbered directories (`step_00` → `step_11`) and are orchestrated by `jobs/people_collector/main.py`
- `WorkflowLogger` writes to per-jurisdiction log files; pass it through the call stack rather than creating new instances
- `shared` is a sibling workspace package (uv workspace), importable as `from shared.utils import ...`
