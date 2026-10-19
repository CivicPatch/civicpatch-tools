-- One `member` role for every governing body's ordinary posts (plan 2's 2.6d, 2026-10-19). The
-- six member roles (council-member, select-board-member, trustee, commissioner, alderperson,
-- committee-member) are one office under local names, and what a reader sees is the
-- organization's own label for the role: organizations.extras_role_labels, role id -> label, filled
-- here from each organization's posts so nothing shown changes today, later by the government
-- form's config and the charter run.
--
-- A post's id is the hash of (organization, role, division) (232), so every post on the six
-- roles is re-keyed to its `member` key, memberships, membership ids and claims following as 232
-- did. Two old posts that meet at one member key (a default "Government" organization holding
-- Council Member and Select Board Member at large) merge into the oldest.

BEGIN;

ALTER TABLE organizations ADD COLUMN IF NOT EXISTS extras_role_labels jsonb NOT NULL DEFAULT '{}'::jsonb;

-- What a post's role is called in its organization: the organization's own label, else the role's.
CREATE OR REPLACE FUNCTION post_role_label(organization_id uuid, role_id text)
RETURNS text LANGUAGE sql STABLE AS $$
    SELECT COALESCE(
        (SELECT o.extras_role_labels ->> role_id FROM organizations o WHERE o.id = organization_id),
        (SELECT r.label FROM roles r WHERE r.id = role_id)
    )
$$;

INSERT INTO roles (id, label, status, is_unique, priority, selection_method, config_path)
SELECT 'member', 'Member', 'active', false, MIN(priority), 'elected_by_voters', MIN(config_path)
FROM roles WHERE id IN ('council-member', 'select-board-member', 'trustee', 'commissioner', 'alderperson', 'committee-member')
ON CONFLICT (id) DO NOTHING;

CREATE TEMP TABLE member_posts ON COMMIT DROP AS
SELECT p.id AS old_id,
       post_id_of_key(p.organization_id, 'member', p.division_ocdid) AS new_id,
       p.organization_id, p.division_ocdid, p.jurisdiction_ocdid, p.role_id AS old_role_id, r.label AS old_label,
       p.created_at
FROM posts p JOIN roles r ON r.id = p.role_id
WHERE p.role_id IN ('council-member', 'select-board-member', 'trustee', 'commissioner', 'alderperson', 'committee-member');

-- The organization's label for `member`: the role its oldest member post had.
UPDATE organizations o
SET extras_role_labels = o.extras_role_labels || jsonb_build_object('member', k.old_label)
FROM (SELECT DISTINCT ON (organization_id) organization_id, old_label FROM member_posts ORDER BY organization_id, created_at, old_id) k
WHERE o.id = k.organization_id AND NOT (o.extras_role_labels ? 'member');

-- Per new key, the oldest old post keeps it; the rest are duplicates that fold into it.
CREATE TEMP TABLE member_post_rekeys ON COMMIT DROP AS
SELECT DISTINCT ON (new_id) old_id, new_id, jurisdiction_ocdid FROM member_posts ORDER BY new_id, created_at, old_id;

CREATE TEMP TABLE member_post_duplicates ON COMMIT DROP AS
SELECT m.old_id AS duplicate_id, k.old_id AS keeper_old_id, k.new_id, m.jurisdiction_ocdid
FROM member_posts m JOIN member_post_rekeys k ON k.new_id = m.new_id AND k.old_id <> m.old_id;

-- A membership's id is uuid5 of (person, post): every person in the jurisdiction, since a claim
-- may name a membership that has no row. Duplicates' memberships take the keeper's new key.
CREATE TEMP TABLE member_membership_rekeys ON COMMIT DROP AS
SELECT uuid_generate_v5('5364ee76-7dec-41fd-a3b0-7218a73ea92f'::uuid, pe.id::text || '|' || x.old_id::text) AS old_id,
       uuid_generate_v5('5364ee76-7dec-41fd-a3b0-7218a73ea92f'::uuid, pe.id::text || '|' || x.new_id::text) AS new_id
FROM (SELECT old_id, new_id, jurisdiction_ocdid FROM member_post_rekeys
      UNION ALL SELECT duplicate_id, new_id, jurisdiction_ocdid FROM member_post_duplicates) x
JOIN people pe ON pe.jurisdiction_ocdid = x.jurisdiction_ocdid;

-- Duplicates' memberships move to the keeper (still under its old id; the cascade below re-keys
-- them again), then the duplicate posts go.
UPDATE memberships SET post_id = d.keeper_old_id FROM member_post_duplicates d WHERE memberships.post_id = d.duplicate_id;
UPDATE claims SET value = to_jsonb(d.keeper_old_id::text)
FROM member_post_duplicates d
WHERE claims.entity_type = 'person' AND claims.field_path = 'posts' AND claims.value #>> '{}' = d.duplicate_id::text;
UPDATE claims SET entity_id = d.keeper_old_id FROM member_post_duplicates d WHERE claims.entity_type = 'post' AND claims.entity_id = d.duplicate_id;
-- A deleted post's `same_as` names the post it folded into.
UPDATE claims SET value = to_jsonb(d.keeper_old_id::text)
FROM member_post_duplicates d
WHERE claims.entity_type = 'post' AND claims.field_path = 'same_as' AND claims.value #>> '{}' = d.duplicate_id::text;
DELETE FROM posts WHERE id IN (SELECT duplicate_id FROM member_post_duplicates);

-- memberships.post_id follows through its ON UPDATE CASCADE foreign keys.
UPDATE posts SET id = k.new_id, role_id = 'member' FROM member_post_rekeys k WHERE posts.id = k.old_id;

UPDATE memberships SET id = r.new_id FROM member_membership_rekeys r WHERE memberships.id = r.old_id;

UPDATE claims SET value = to_jsonb(k.new_id::text)
FROM member_post_rekeys k
WHERE claims.entity_type = 'person' AND claims.field_path = 'posts' AND claims.value #>> '{}' = k.old_id::text;

UPDATE claims SET entity_id = k.new_id FROM member_post_rekeys k WHERE claims.entity_type = 'post' AND claims.entity_id = k.old_id;

UPDATE claims SET value = to_jsonb(k.new_id::text)
FROM member_post_rekeys k
WHERE claims.entity_type = 'post' AND claims.field_path = 'same_as' AND claims.value #>> '{}' = k.old_id::text;

UPDATE claims SET entity_id = r.new_id FROM member_membership_rekeys r WHERE claims.entity_type = 'membership' AND claims.entity_id = r.old_id;

COMMIT;
