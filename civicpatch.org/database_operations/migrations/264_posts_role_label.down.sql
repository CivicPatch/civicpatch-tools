BEGIN;

CREATE OR REPLACE FUNCTION post_role_label(organization_id uuid, role_id text)
RETURNS text LANGUAGE sql STABLE AS $$
    SELECT COALESCE(
        (SELECT o.extras_role_labels ->> role_id FROM organizations o WHERE o.id = organization_id),
        (SELECT r.label FROM roles r WHERE r.id = role_id)
    )
$$;

ALTER TABLE posts DROP COLUMN IF EXISTS role_label;

COMMIT;
