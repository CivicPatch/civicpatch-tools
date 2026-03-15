# civicpatch-tools — Coding Standards

## Philosophy

- **Small functions.** A function should do one thing. If you need to describe it with "and", split it.
- **Small files.** Files group closely related functions. If a file is growing, split it by concern.
- **Functional style.** Prefer pure functions — given the same inputs, return the same outputs. Avoid mutating arguments.
- **Minimize side effects.** Side effects (I/O, DB, network, env reads) belong at the edges. Pure logic lives in the middle.
- **Readability first.** Code is read far more than it is written. Optimize for the reader, not the writer.

## Functions

- One level of abstraction per function
- Avoid boolean flag arguments — split into two functions instead
- Return early rather than nesting deeply

## Side Effects

- Functions that read env vars, call the network, or write to disk should be clearly named and isolated
- Pure logic functions must not call `get_env_vars()`, make HTTP calls, or touch the filesystem
- Pass dependencies (loggers, config, clients) as arguments rather than importing globals mid-function

## Pydantic Models

- Use Pydantic models for all structured data crossing function or module boundaries
- No raw `dict` passing between layers — define a model
- Validation belongs in the model, not the caller

## Package Structure

- This is a uv workspace: `civicpatch`, `api.civicpatch.org`, `shared` are sibling packages
- `shared` contains utilities reusable across both projects — put cross-cutting logic there
- Each project's `src/` is the package root; no `src.` prefix needed in imports

## Testing

- Tests live in `tests/unit/` and `tests/integration/`
- Use `tests/factories/` for test data builders — never construct raw objects in test bodies
- Do not mock what you can test directly
