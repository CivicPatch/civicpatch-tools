-- Reverses 226's structure. The rows are derived, so the next rebuild would have refilled them;
-- nothing writes them any more, so they stay empty.

BEGIN;

CREATE TABLE IF NOT EXISTS membership_roles (
    membership_id uuid NOT NULL REFERENCES memberships (id) ON DELETE CASCADE,
    role_id       text NOT NULL REFERENCES roles (id) ON UPDATE CASCADE,
    PRIMARY KEY (membership_id, role_id)
);
CREATE INDEX IF NOT EXISTS membership_roles_role_idx ON membership_roles (role_id);

COMMIT;
