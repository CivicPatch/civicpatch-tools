BEGIN;

ALTER TABLE memberships
    ADD COLUMN role_id text REFERENCES roles(id) ON UPDATE CASCADE;

CREATE INDEX memberships_role_id_idx ON memberships (role_id) WHERE role_id IS NOT NULL;

DROP TABLE membership_roles;

COMMIT;
