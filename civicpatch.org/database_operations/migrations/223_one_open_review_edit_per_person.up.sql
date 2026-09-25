-- One open review edit per person per scrape (plan 9f): saving again reuses yours, a second
-- person gets their own. Jurisdictions-page edits are born published, so never match.

BEGIN;

CREATE UNIQUE INDEX IF NOT EXISTS changesets_one_open_review_edit_per_person
    ON changesets (parent_changeset_id, created_by_user_id)
    WHERE kind = 'people_edit' AND published_at IS NULL AND dismissed_at IS NULL;

COMMIT;
