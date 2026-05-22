BEGIN;

-- Move from a flat set-of-roles model (user_roles join table, many rows per user)
-- to a strict trust ladder (one level per user). The new `users.role` column
-- stores the highest level the user previously held; lower levels are now
-- implied by the ladder, not stored.

ALTER TABLE users ADD COLUMN role TEXT;

-- Populate users.role from the highest existing user_roles row.
-- Ranking: admins (4) > maintainers (3) > contributors (2) > default (1).
-- Any role not in this set is ignored (would surface as NULL → 'default' below).
UPDATE users u SET role = (
    SELECT ur.role
    FROM user_roles ur
    WHERE ur.user_id = u.id
    ORDER BY CASE ur.role
        WHEN 'admins' THEN 4
        WHEN 'maintainers' THEN 3
        WHEN 'contributors' THEN 2
        WHEN 'default' THEN 1
        ELSE 0
    END DESC
    LIMIT 1
);

-- Users with no user_roles rows (or only unknown role strings) collapse to default.
UPDATE users SET role = 'default' WHERE role IS NULL;

ALTER TABLE users ALTER COLUMN role SET DEFAULT 'default';
ALTER TABLE users ALTER COLUMN role SET NOT NULL;

-- Enforce the ladder vocabulary at the DB layer. Adding a new level later
-- requires a migration to update this constraint, which is the right friction.
ALTER TABLE users ADD CONSTRAINT users_role_valid
    CHECK (role IN ('default', 'contributors', 'maintainers', 'admins'));

DROP TABLE user_roles;

COMMIT;
