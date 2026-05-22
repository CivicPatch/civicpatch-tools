BEGIN;

-- Track when each user last completed a successful sign-in. Sourced from our
-- own upsert_user write (called from verify_otp). Decoupled from Supabase's
-- last_sign_in_at so the admin page can render this without an admin-API call
-- on every load.

ALTER TABLE users ADD COLUMN last_login_at TIMESTAMPTZ;

COMMIT;
