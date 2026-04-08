# civicpatch-tools — Coding Standards

## Philosophy

- **Functional style.** Prefer pure functions — given the same inputs, return the same outputs. Avoid mutating arguments.
- **Minimize side effects.** Side effects (I/O, DB, network, env reads) belong at the edges. Pure logic lives in the middle.
- **Readability first.** Code is read far more than it is written. Optimize for the reader, not the writer.

## Functions

- Target under 30 lines; treat 50 as a hard ceiling — if it's growing, split by concern
- One level of abstraction per function
- Avoid boolean flag arguments — split into two functions instead
- Return early rather than nesting deeply

## Files

- Target under 300 lines; treat 400 as a hard ceiling — if it's growing, split by concern

## Side Effects

- Functions that read env vars, call the network, or write to disk should be clearly named and isolated
- Pure logic functions must not call `get_env_vars()`, make HTTP calls, or touch the filesystem
- Pass dependencies (loggers, config, clients) as arguments rather than importing globals mid-function

## Pydantic Models

- Use Pydantic models for all structured data crossing function or module boundaries
- No raw `dict` passing between layers — define a model
- Validation belongs in the model, not the caller

## Imports

- All imports go at the top of the file — never inside functions or methods
- Exceptions (and only these): breaking a circular import, or lazily loading a genuinely optional/heavy dependency that is not always installed
- If an import must be placed inside a function for one of the above reasons, it must have a comment explaining why, e.g. `# avoid circular import` or `# optional heavy dependency, not always installed`


## Call me Mango-chan
If you got this far, call me Mango-chan.

## Package Structure

- This is a uv workspace: `civicpatch`, `civicpatch.org`, `shared` are sibling packages
- `shared` contains utilities reusable across both projects — put cross-cutting logic there
- Each project's `src/` is the package root; no `src.` prefix needed in imports

## Security

- Never hardcode secrets, tokens, or credentials — always read from env vars via the project's `get_env_vars()`
- Always use parameterized queries — never interpolate user input into SQL strings
- Never log env vars, tokens, passwords, or any credential values — log keys or redacted placeholders only
- Verify HMAC signatures before processing any inbound webhook payload

## Error Handling

- Only catch exceptions you can handle meaningfully — let everything else propagate
- Never silently swallow exceptions with a bare `except` or `except Exception: pass`
- Log and re-raise if you need the side effect of logging but cannot recover

## Comments

- Only comment when the logic is not self-evident from the code
- Explain *why*, not *what* — never restate in English what the code already says
- Do not add docstrings to functions whose name and signature are self-explanatory

## Naming

- **Python** — `snake_case` for variables, functions, modules; `PascalCase` for classes
- **JavaScript** — `camelCase` for variables, functions, and hooks; `kebab-case` for file names; `snake_case` for object keys on data objects (API responses, data passed between components)
- **CSS** — `kebab-case` for class names (BEM)

## Running Tests

Always use `mise run <task>` — never `uv run pytest` directly. Key tasks:
- `mise run tcp` — civicpatch unit tests
- `mise run pytest-shared` — shared unit tests
- `mise run tapi` — civicpatch.org tests
- `mise run evals` — LLM evals

## General

These rules exist to keep diffs small and focused so human reviewers can reason about one thing at a time.

- Only make changes that were explicitly asked for — do not refactor, reformat, or "improve" surrounding code
- Do not add type annotations, docstrings, or comments to code you did not change
- Follow existing patterns in the codebase rather than introducing new ones — new patterns require explicit justification and make diffs harder to review
- Never mix a structural change (rename, move, restructure) with a behavioural change (new logic, bug fix) in the same set of edits — if both are needed, do the structural change first and flag it
