-- An alias may belong to several roles ("member": Council Member and Select Board Member); the
-- record's organization, then priority, picks which. Still unique within one role.

BEGIN;

DROP INDEX IF EXISTS role_aliases_label_lower_uq;
CREATE UNIQUE INDEX IF NOT EXISTS role_aliases_role_id_label_lower_uq
    ON role_aliases (role_id, lower(label));

COMMIT;
