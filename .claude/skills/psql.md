---
name: psql
description: Inspect the dev database schema using mise run psql
trigger: when asked about database schema, table columns, or DB structure in this project
---

To inspect the dev database schema, use:

```
mise run psql -- -c "\d <table_name>"
```

For example:
- `mise run psql -- -c "\d review_session_entries"` — show columns, types, constraints
- `mise run psql -- -c "\dt"` — list all tables
- `mise run psql -- -c "\d+ <table>"` — show extended info including indexes and FK constraints

**Always use this instead of reading migration files or README.md for schema questions.** The live DB reflects the current applied state; migrations require mentally folding N files together.
