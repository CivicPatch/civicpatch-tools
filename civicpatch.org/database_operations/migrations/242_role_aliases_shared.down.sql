-- Fails while two roles share an alias: remove the duplicates first.

BEGIN;

DROP INDEX IF EXISTS role_aliases_role_id_label_lower_uq;
CREATE UNIQUE INDEX IF NOT EXISTS role_aliases_label_lower_uq ON role_aliases (lower(label));

COMMIT;
