# Agent Instructions

## Repository Overview
This monorepo contains tools for collecting and managing municipal official data for CivicPatch.

## Projects

| Directory | Purpose |
|-----------|---------|
| `civicpatch/` | Core Python package for municipal data collection |
| `api.civicpatch.org/` | FastAPI backend service |

## Global Conventions
- OCD-IDs (Open Civic Data Identifiers) are used for jurisdiction identification
- YAML for data files or files meant to be modified by humans
- JSON for generated files
- Functional style preferred

See individual project `AGENTS.md` files for project-specific guidance.