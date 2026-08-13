BEGIN;

-- Title-case all role labels. The 106 backfill copied `role_terms.value`
-- verbatim, which was inconsistently cased (some "Mayor", some "mayor").
-- `label` is the display name — the identity — so it should be consistently
-- capitalized. PostgreSQL's initcap() handles "MAYOR PRO TEMPORE" →
-- "Mayor Pro Tempore".
--
-- Idempotent: a second run finds nothing to change (initcap of an already
-- title-cased string is a no-op).

UPDATE roles SET label = initcap(label);

COMMIT;