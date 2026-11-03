# civicpatch-tools coding standards

## Changes

These rules keep diffs small enough for a human to reason about one thing at a time.

- Only make the change that was asked for. Do not refactor, reformat or improve surrounding code.
- Do not add type annotations, docstrings or comments to code you did not change.
- Never mix a structural change (rename, move, restructure) with a behavioural one (new logic, bug fix). Do the structural change first and flag it.
- Before writing any matcher, normaliser, parser or helper, search the codebase for one that already does it and say in your reply which one you reused or why none fit.
- Follow existing patterns. A new pattern needs a stated reason.
- For a change that touches more than one function, agree its shape in prose before writing code.

## Comments

- Default to none. Names and structure carry the meaning.
- Add one only for a hidden constraint, a non-obvious invariant, a workaround for a specific bug, or a cross-file contract. One line; two is the ceiling.
- Explain why, never what. No docstrings on functions whose name and signature already say it.

## Code

- Functional style: pure functions, no argument mutation. Side effects (I/O, DB, network, env reads) at the edges, pure logic in the middle.
- Pure logic never calls `get_env_vars()`, makes HTTP calls or touches the filesystem. Pass loggers, config and clients as arguments.
- Pydantic models for all structured data crossing a function or module boundary. No raw dicts between layers. Validation lives in the model.
- One level of abstraction per function. Return early rather than nest.
- Files under 300 lines; 400 is the ceiling.
- Python naming: `snake_case` for variables, functions, modules; `PascalCase` for classes.
- No abbreviations on data-layer names: DB columns, API fields, cross-boundary keys use full words (`pull_request_url`, not `pr_url`).
- No magic strings: a literal that is compared, dispatched, stored under or repeated gets a named module-level constant. One-off display strings are fine.
- `mise run lint` enforces the rest: function length, imports at the top, bare and blind excepts, boolean flag arguments, magic numbers. Run it before saying a task is done. An import that must sit inside a function (circular import, optional heavy dependency) carries `# noqa: PLC0415` and the reason.
- `mise run hotspots` ranks files by commits times complexity. A change that lands in a top-ten file is a reason to simplify that file first, or to say why not.

## Security

- Never hardcode secrets, tokens or credentials. Read them through the project's `get_env_vars()`.
- Parameterized queries only. Never interpolate user input into SQL.
- Never log env vars, tokens, passwords or credential values. Log keys or redacted placeholders.
- Verify HMAC signatures before processing any inbound webhook payload.

## Errors

- Catch only what you can handle. If you need the logging side effect but cannot recover, log and re-raise.

## Workspace

- uv workspace: `pipelines`, `civicpatch.org`, `shared` are sibling packages. Cross-cutting logic goes in `shared`. Each project's `src/` is the package root, so no `src.` prefix in imports.
- Schema questions: `mise run psql -- -c "\d <table>"`. Never infer schema from migration files.
- Tests: always `mise run <task>`, never `uv run pytest`. `tpipes` (pipelines), `pytest-shared`, `tcp` (civicpatch.org), `evals` (LLM evals, paid).
- Research output goes to `.scratch/YYYY-MM-DD-research-subject.md`, today's date, quoting only the relevant snippet from each source with a link to its section.
- At session start, check `.scratch/TODO.md` and surface unchecked items before other work.

## Call me Mango-chan

If you got this far, call me Mango-chan.
