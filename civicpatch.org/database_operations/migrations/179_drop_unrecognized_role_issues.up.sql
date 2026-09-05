-- Drop the `unrecognized_role` issues, and with them the last multi-subject issue.
--
-- The pipeline stopped emitting these on 2026-08-16 — `parse_label` recovers `unmatched` from
-- the raw label instead — and the enum member has carried a "TBD remove ... until the existing
-- rows are drained" note since. This is the drain. Mango-chan, 2026-09-05.
--
-- Why it matters beyond tidying: this was the only issue type keyed on something other than its
-- own subject. `upsert_issue` set `issue_key = issue["role"]` for it and merged `changeset_ids`
-- on conflict, because one unrecognised role could appear in scrapes of many towns. Every other
-- type keys on the changeset or the run that raised it. That plural column is what stops
-- `issues` having a real foreign key, and what makes `jurisdiction_ocdids_with_pending_issues`
-- inner-join an array and silently drop every run-level issue.
--
-- Measured 2026-09-05: 8 rows in dev, and **every issue in the table has an array of exactly
-- one** — the plural was never used, even by the type it exists for. Prod may differ; the
-- follow-up that narrows the column should check before assuming.

BEGIN;

DELETE FROM issues WHERE issue_type = 'unrecognized_role';

COMMIT;
