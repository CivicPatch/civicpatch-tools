---
applyTo: "**"
---

# CivicPatch Repository

This is the CivicPatch monorepo with four projects: `shared/`, `civicpatch/`,
`api.civicpatch.org/`, and `components/`.

- **There are two FastAPI applications**: `civicpatch/` (scraping/data collection)
  and `api.civicpatch.org/` (public API server). They are separate apps with separate
  `.env` files.
- **Task runner is mise** — see `.github/instructions/mise-tasks.md` for syntax.