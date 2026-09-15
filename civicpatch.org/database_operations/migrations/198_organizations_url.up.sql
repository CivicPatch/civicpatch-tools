-- An organization may scrape from a site of its own, distinct from its jurisdiction's — the
-- first real step toward "named, non-default bodies (Council, School Board)" that
-- database/organizations.py's own docstring already anticipates. Nullable: the default
-- organization scrapes from the jurisdiction's own site, same as today, so most rows never
-- set this.
BEGIN;

ALTER TABLE organizations
    ADD COLUMN IF NOT EXISTS url text;

COMMIT;
