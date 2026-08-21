BEGIN;

-- Roles a person's label named that did not define their post.
--
-- Replaces `memberships.role_id`, which was singular and truncated real data: the corpus has
-- labels naming up to five roles ("Chair - Chair Pro Tem - Vice Mayor - Council President -
-- Council Member"), and three is routine ("Chair - Vice Chair - Council Member", 10 people).
-- A single column kept the first and silently dropped the rest.
--
-- A join table rather than `text[]` because an array cannot carry a foreign key, and
-- `ON UPDATE CASCADE` is load-bearing here: renaming role ids is planned work (#2476). Open
-- memberships would self-heal on the next scrape either way, since `record` rewrites them —
-- but closed ones never rewrite, so an array would leave permanently stale ids in exactly the
-- history the roster timeline reads.
CREATE TABLE membership_roles (
    membership_id uuid NOT NULL REFERENCES memberships(id) ON DELETE CASCADE,
    role_id       text NOT NULL REFERENCES roles(id) ON UPDATE CASCADE,
    PRIMARY KEY (membership_id, role_id)
);

-- "Who currently holds this title anywhere" — mayor, council president. The reason these are
-- ids rather than text at all.
CREATE INDEX membership_roles_role_idx ON membership_roles (role_id);

-- No data to migrate: the writer landed today and set none.
ALTER TABLE memberships DROP COLUMN role_id;

COMMIT;
