-- A post's name, written by the fold: what its organization calls the role, else the role's label.
-- Replaces post_role_label, which read the roles table being retired.

BEGIN;

ALTER TABLE posts ADD COLUMN IF NOT EXISTS role_label text;

UPDATE posts SET role_label = post_role_label(organization_id, role_id) WHERE role_label IS NULL;

DROP FUNCTION IF EXISTS post_role_label(uuid, text);

COMMIT;
