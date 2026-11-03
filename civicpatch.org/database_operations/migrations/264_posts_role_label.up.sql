-- A post's name, written by the fold: what its organization calls the role, else the role's label.
-- Replaces post_role_label, which read the roles table being retired.

BEGIN;

ALTER TABLE posts ADD COLUMN IF NOT EXISTS role_label text;

UPDATE posts SET role_label = COALESCE(
    (SELECT organizations.extras_role_labels ->> posts.role_id FROM organizations WHERE organizations.id = posts.organization_id),
    (SELECT roles.label FROM roles WHERE roles.id = posts.role_id)
) WHERE role_label IS NULL;

DROP FUNCTION IF EXISTS post_role_label(uuid, text);

COMMIT;
