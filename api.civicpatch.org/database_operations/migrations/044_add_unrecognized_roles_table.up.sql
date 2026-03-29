BEGIN;

CREATE TABLE unrecognized_roles (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    request_id  UUID NOT NULL REFERENCES requests(id) ON DELETE CASCADE,
    role        TEXT NOT NULL,
    person_name TEXT NOT NULL,
    status      TEXT NOT NULL DEFAULT 'pending',
    pr_url      TEXT,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_unrecognized_roles_request_id ON unrecognized_roles(request_id);
CREATE INDEX idx_unrecognized_roles_status ON unrecognized_roles(status);

COMMIT;
