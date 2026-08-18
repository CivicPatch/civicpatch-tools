-- Posts, memberships, and the two registries they point at.
-- Design and rationale: .scratch/2026-08-17-posts-schema.md
BEGIN;

CREATE TABLE IF NOT EXISTS organizations (
    id                 uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    jurisdiction_ocdid text NOT NULL REFERENCES jurisdictions (jurisdiction_ocdid),
    name               text NOT NULL,
    sort_order         integer NOT NULL DEFAULT 0,
    created_at         timestamptz NOT NULL DEFAULT now(),

    UNIQUE (jurisdiction_ocdid, name),
    -- Parent for posts' composite FK.
    UNIQUE (jurisdiction_ocdid, id)
);

CREATE TABLE IF NOT EXISTS divisions (
    ocdid              text PRIMARY KEY,
    jurisdiction_ocdid text NOT NULL REFERENCES jurisdictions (jurisdiction_ocdid),
    created_at         timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS posts (
    id                 uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    jurisdiction_ocdid text NOT NULL REFERENCES jurisdictions (jurisdiction_ocdid),
    organization_id    uuid NOT NULL REFERENCES organizations (id),
    role_id            text NOT NULL REFERENCES roles (id) ON UPDATE CASCADE,
    division_ocdid     text NOT NULL REFERENCES divisions (ocdid) ON UPDATE CASCADE,
    -- Display only. NULL renders from the role.
    label              text,
    -- How many people this post holds. Set on mint, then only by a human.
    headcount          integer NOT NULL DEFAULT 1,
    status             text NOT NULL DEFAULT 'candidate',
    created_at         timestamptz NOT NULL DEFAULT now(),

    CHECK (headcount > 0),
    CHECK (status IN ('candidate', 'active', 'inactive')),
    -- Identity: the parsed triple, no free text.
    CONSTRAINT posts_identity_uq UNIQUE (organization_id, role_id, division_ocdid),
    -- Parent for memberships' composite FK.
    UNIQUE (id, organization_id),
    -- Keeps the denormalised jurisdiction honest against the organization's.
    FOREIGN KEY (jurisdiction_ocdid, organization_id)
        REFERENCES organizations (jurisdiction_ocdid, id)
);

CREATE TABLE IF NOT EXISTS memberships (
    id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    post_id         uuid NOT NULL REFERENCES posts (id),
    -- Redundant against posts.organization_id, and only here so the partial unique
    -- index below can exist — Postgres cannot enforce uniqueness across a join.
    organization_id uuid NOT NULL,
    person_id       uuid NOT NULL REFERENCES people (id),
    -- Whatever office.name left over once role and division were taken, verbatim.
    label           text,
    -- The source's claim about the term.
    start_date      date,
    end_date        date,
    -- Our observation window, from the Record's updated_at.
    first_seen_at   timestamptz NOT NULL,
    last_seen_at    timestamptz NOT NULL,
    -- Ours, not the source's: set when a scrape stops finding them, or they turn up
    -- on a different post. Unrelated to end_date above.
    closed_at       timestamptz,
    created_at      timestamptz NOT NULL DEFAULT now(),

    FOREIGN KEY (post_id, organization_id)
        REFERENCES posts (id, organization_id) ON UPDATE CASCADE
);

CREATE INDEX IF NOT EXISTS organizations_jurisdiction_idx ON organizations (jurisdiction_ocdid);
CREATE INDEX IF NOT EXISTS divisions_jurisdiction_idx ON divisions (jurisdiction_ocdid);
CREATE INDEX IF NOT EXISTS posts_jurisdiction_idx ON posts (jurisdiction_ocdid);
CREATE INDEX IF NOT EXISTS posts_organization_idx ON posts (organization_id);
CREATE INDEX IF NOT EXISTS posts_role_idx ON posts (role_id);
CREATE INDEX IF NOT EXISTS posts_division_idx ON posts (division_ocdid);
CREATE INDEX IF NOT EXISTS memberships_post_idx ON memberships (post_id);
CREATE INDEX IF NOT EXISTS memberships_person_idx ON memberships (person_id, first_seen_at DESC);

-- One OPEN membership per person per body. Closed ones pile up freely.
CREATE UNIQUE INDEX IF NOT EXISTS memberships_one_open_per_organization
    ON memberships (person_id, organization_id) WHERE closed_at IS NULL;

-- Never matched; assigned by fallback when nothing else matched. 'inactive' keeps it
-- out of the matcher's alias table.
INSERT INTO roles (id, label, status, is_unique)
VALUES ('unmatched', 'Unmatched', 'inactive', false)
ON CONFLICT (id) DO NOTHING;

COMMIT;
