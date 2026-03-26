BEGIN;

-- 1. Create Requests (The Master Intent)
CREATE TABLE IF NOT EXISTS requests (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    status TEXT NOT NULL DEFAULT 'DEFAULT',
    request_type TEXT NOT NULL DEFAULT 'scrape', 
    jurisdiction_ocdid TEXT,
    
    arguments_json JSONB NOT NULL DEFAULT '{}',
    result_data JSONB, 
    review_json JSONB,

    requested_by_user_id UUID REFERENCES users(id) ON DELETE SET NULL,
    
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 2. Create Pull Requests (The GitHub Record)
CREATE TABLE IF NOT EXISTS pull_requests (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    request_id UUID UNIQUE NOT NULL REFERENCES requests(id) ON DELETE CASCADE,
    
    pr_number INTEGER NOT NULL,
    url TEXT,
    status TEXT NOT NULL DEFAULT 'DEFAULT',

    closed_at TIMESTAMPTZ,
    merged_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 3. Update Jobs (The Worker Record)
-- Split into two statements to avoid Postgres RENAME syntax error
-- 3. Update Jobs (The Worker Record)
ALTER TABLE jobs ADD COLUMN IF NOT EXISTS request_id UUID UNIQUE REFERENCES requests(id) ON DELETE SET NULL;

-- Idempotent Rename: Only rename if the old column still exists
DO $$ 
BEGIN 
    IF EXISTS (SELECT 1 FROM information_schema.columns 
               WHERE table_name='jobs' AND column_name='job_run_url') THEN
        ALTER TABLE jobs RENAME COLUMN job_run_url TO run_url;
    END IF;
END $$;

-- 4. Final Back-references (Nullable by default)
-- job_id is INTEGER to match your existing jobs.id
ALTER TABLE requests ADD COLUMN IF NOT EXISTS job_id INTEGER UNIQUE REFERENCES jobs(id) ON DELETE SET NULL;
ALTER TABLE requests ADD COLUMN IF NOT EXISTS pr_id UUID UNIQUE REFERENCES pull_requests(id) ON DELETE SET NULL;

COMMIT;