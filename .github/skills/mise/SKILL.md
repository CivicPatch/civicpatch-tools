---
applyTo: "**/mise.toml"
---

# Mise Task Instructions

This repository uses [mise](https://mise.jdx.dev) as its task runner. Tasks are defined
in `mise.toml` files using TOML syntax. For CivicPatch-specific conventions and project
structure, see `.github/instructions/civicpatch.md`.

## Core Syntax

The only required field for a task is `run`:

```toml
# Minimal task
[tasks.build]
run = "echo building"

# With description (always include this)
[tasks.build]
description = "Build the project"
run = "echo building"

# Multi-line script
[tasks.test]
description = "Run tests"
run = """
echo "Running tests..."
pytest
"""

# Array of commands (run in series; stops on failure)
[tasks.ci]
description = "Run CI checks"
run = [
  "ruff check",
  "mypy",
  "pytest",
]
```

## Key Task Properties

```toml
[tasks.example]
description = "What this task does"        # shown in `mise tasks`
run = "command"                            # required: command(s) to run
dir = "subproject/"                        # working directory (default: mise.toml location)
depends = ["other-task", "another-task"]   # tasks to run before this one
sources = ["src/**/*.py"]                  # skip if outputs are newer than these
outputs = ["dist/bundle.js"]               # files produced by this task
shell = "bash"                             # override shell (default: sh)
hide = false                               # hide from `mise tasks` output
quiet = false                              # suppress mise's own output (not the script's)
silent = false                             # suppress ALL output including the script's
confirm = "Are you sure?"                  # prompt user before running
```

## Working Directory

The default `dir` is the directory containing the `mise.toml` file. Override it per task:

```toml
[tasks.frontend:build]
dir = "civicpatch/src/frontend/"   # relative to mise.toml location
run = "npm run build"

[tasks.in-place]
dir = "{{cwd}}"                    # use the directory where `mise run` was called
run = "echo running here"
```

## Task Dependencies

```toml
[tasks.deploy]
description = "Deploy after build"
depends = ["build", "test"]
run = "./scripts/deploy.sh"

# Parallel then serial
[tasks.ci]
run = [
  { tasks = ["lint", "typecheck"] },   # these run in parallel
  "pytest",                             # then this runs after both finish
]
```

## Task Arguments

Use the `usage` field to define typed arguments:

```toml
[tasks.test]
description = "Run tests for a specific path"
usage = 'arg "<path>" help="Test path to run"'
run = "pytest $usage_path"

[tasks.deploy]
description = "Deploy to an environment"
usage = '''
arg "<environment>" help="Target environment (staging|prod)"
flag "--force" help="Skip confirmation"
'''
run = "./deploy.sh $usage_environment"
```

## Environment Variables and Vars

```toml
# Env vars are passed to all tasks
[env]
NODE_ENV = "development"
API_URL = "http://localhost:3000"

# Vars are TOML-only (not passed as env vars to scripts)
[vars]
build_flags = "--release"

[tasks.build]
run = "build {{vars.build_flags}}"
```

## File-Based Tasks (Alternative to TOML)

For complex scripts, create executable files in a `mise-tasks/` directory:

```
mise-tasks/
  build          # executable script, runs as `mise run build`
  test
  deploy
```

Add a shebang and optional metadata at the top:

```bash
#!/usr/bin/env bash
# MISE description="Build the project"
set -euo pipefail

echo "building..."
```

## Monorepo Setup

```toml
# Root mise.toml
experimental_monorepo_root = true

[env]
MISE_EXPERIMENTAL = "1"
```

Run tasks across projects using path syntax:

```bash
mise run //civicpatch:test
mise run //api.civicpatch.org:dev

# From inside a subdirectory
cd civicpatch
mise :test       # runs this project's test task
```

## Running Tasks

```bash
mise run <task>              # run a task
mise run <task> -- --arg     # pass arguments to the task
mise tasks                   # list all available tasks
mise watch <task>            # re-run on file changes (requires watchexec)
```