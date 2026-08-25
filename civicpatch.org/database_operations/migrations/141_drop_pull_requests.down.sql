BEGIN;

-- Structure only. The rows are not recoverable and nothing writes them any more; this
-- exists so the migration round-trips, not so the data comes back.
CREATE TABLE IF NOT EXISTS pull_requests (
    id                  uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    request_id          uuid NOT NULL UNIQUE REFERENCES requests(id) ON DELETE CASCADE,
    pr_number           integer NOT NULL,
    url                 text,
    status              text NOT NULL DEFAULT 'DEFAULT',
    merged_at           timestamptz,
    created_at          timestamptz NOT NULL DEFAULT now(),
    updated_at          timestamptz NOT NULL DEFAULT now(),
    resolved_by_user_id uuid REFERENCES users(id) ON DELETE SET NULL,
    merge_enqueued_at   timestamptz
);

CREATE INDEX IF NOT EXISTS idx_pull_requests_status ON pull_requests (status);

COMMIT;
