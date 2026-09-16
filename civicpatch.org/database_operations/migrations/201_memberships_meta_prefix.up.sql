BEGIN;

-- `unmatched_text` predates the `meta_` convention 199 adopted for posts' internal-only
-- columns. It is the same kind of field — parser residue for our own triage, not a fact
-- about the membership — so it joins that convention here too.
ALTER TABLE memberships RENAME COLUMN unmatched_text TO meta_unmatched_text;
ALTER INDEX memberships_unmatched_text_idx RENAME TO memberships_meta_unmatched_text_idx;

COMMIT;
