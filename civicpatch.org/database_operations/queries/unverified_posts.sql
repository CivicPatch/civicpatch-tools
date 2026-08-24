-- How many posts nobody has vouched for, and where they pile up.
--
-- Worth re-running: unverified posts now feed both the queue's badge and its ORDER BY, and
-- nothing reaps them. A mis-parsed label mints a post that stays unverified forever, so this
-- number only grows — the trend matters more than any single reading.
--
-- A high count in one jurisdiction is parse debris, not a busy council. `delete_if_unheld`
-- removes a post nothing has ever held or vouched for.
--
--   cd ~/cp-infrastructure
--   mise run prod-sql < ~/civicpatch-tools/civicpatch.org/database_operations/queries/unverified_posts.sql
WITH unverified AS (
    SELECT posts.jurisdiction_ocdid, posts.role_id, posts.division_ocdid
    FROM posts
    WHERE NOT (
        EXISTS (SELECT 1 FROM memberships WHERE memberships.post_id = posts.id)
        OR EXISTS (
            SELECT 1 FROM assertions
            WHERE assertions.entity_type = 'post' AND assertions.entity_id = posts.id
              AND assertions.field_path IS NULL AND assertions.kind = 'confirm'
        )
    )
)
SELECT
    (SELECT count(*) FROM posts)                                   AS posts_total,
    (SELECT count(*) FROM unverified)                              AS unverified_total,
    (SELECT count(DISTINCT jurisdiction_ocdid) FROM unverified)    AS jurisdictions_affected,
    (SELECT count(*) FROM unverified WHERE role_id = 'unmatched')  AS unverified_unmatched,
    (SELECT max(n) FROM (
        SELECT count(*) AS n FROM unverified GROUP BY jurisdiction_ocdid
     ) per_jurisdiction)                                           AS worst_jurisdiction;
