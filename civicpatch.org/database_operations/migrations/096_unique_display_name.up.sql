BEGIN;

-- display_name is now treated as the user's handle (rendered everywhere the
-- activity feed used to fall back to email). Default Postgres UNIQUE treats
-- NULLs as distinct, so users who haven't picked a handle yet (NULL) coexist
-- fine; only non-NULL values must be unique.

ALTER TABLE users ADD CONSTRAINT users_display_name_unique UNIQUE (display_name);

COMMIT;
