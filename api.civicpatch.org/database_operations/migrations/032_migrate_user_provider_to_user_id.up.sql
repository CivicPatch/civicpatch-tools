-- 1. Add the new UUID column (Nullable for now)
ALTER TABLE users ADD COLUMN IF NOT EXISTS id UUID DEFAULT gen_random_uuid();

-- 2. Backfill existing rows with UUIDs
-- This ensures every existing GitHub/Google user gets a unique ID
UPDATE users SET id = gen_random_uuid() WHERE id IS NULL;

-- 3. Make the new ID NOT NULL
ALTER TABLE users ALTER COLUMN id SET NOT NULL;

-- 4. Drop the old Composite Primary Key
-- Replace 'users_pkey' with the actual name of your constraint if it differs
ALTER TABLE users DROP CONSTRAINT IF EXISTS users_pkey CASCADE;

-- 5. Set the new UUID as the Primary Key
ALTER TABLE users ADD PRIMARY KEY (id);

-- 6. Keep your provider columns unique
-- You still want to ensure a user can't sign up twice with the same GitHub ID
ALTER TABLE users ADD CONSTRAINT unique_provider_user UNIQUE (provider, provider_user_id);