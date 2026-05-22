BEGIN;

-- Reverse 087: restore the user_roles join table from the single users.role column.
-- This is lossy in principle — if multi-row history ever existed, that history is
-- gone after the up. In practice the up was applied before any such history was
-- captured, so the round-trip is clean for the actual data we have.

CREATE TABLE user_roles (
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    role VARCHAR(50) NOT NULL,
    PRIMARY KEY (user_id, role)
);

-- Restore one row per user that holds an elevation. Users at 'default' have no row
-- (matches the pre-087 convention: default was the absence of an explicit role).
INSERT INTO user_roles (user_id, role)
SELECT id, role FROM users WHERE role IS NOT NULL AND role <> 'default';

ALTER TABLE users DROP CONSTRAINT users_role_valid;
ALTER TABLE users DROP COLUMN role;

COMMIT;
