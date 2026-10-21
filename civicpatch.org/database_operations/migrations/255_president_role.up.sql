-- One `president` and one `vice-president` role (2026-10-20-plan-president-role.md):
-- council-president, village-president and commission-president are one office under local names,
-- as are council-vice-president and commissioner-vice-president, as 253 made the member roles one.
-- How a president is filled is read per town by the organizations collector, so the role no
-- longer has to carry it. The organization's own label goes in extras_role_labels, as 253's did.
--
-- 253's rekey for each merged id: a post's id is the hash of (organization, role, division), so
-- every such post gets its new key, memberships, membership ids and claims following; two old
-- posts meeting at one key merge into the oldest. Each new role takes the place of the old role
-- holding nearly all its posts (council-president, council-vice-president), so both still rank
-- below member.

BEGIN;

CREATE TEMP TABLE role_merges (old_id text, new_id text, label text, keeps_place boolean) ON COMMIT DROP;
INSERT INTO role_merges VALUES
    ('council-president', 'president', 'President', true),
    ('village-president', 'president', 'President', false),
    ('commission-president', 'president', 'President', false),
    ('council-vice-president', 'vice-president', 'Vice President', true),
    ('commissioner-vice-president', 'vice-president', 'Vice President', false);

INSERT INTO roles (id, label, status, is_unique, priority, selection_method, config_path)
SELECT DISTINCT ON (m.new_id) m.new_id, m.label, 'active', true, r.priority, 'elected_by_members', r.config_path
FROM role_merges m JOIN roles r ON r.id = m.old_id
ORDER BY m.new_id, NOT m.keeps_place, r.priority
ON CONFLICT (id) DO NOTHING;

CREATE TEMP TABLE merged_posts ON COMMIT DROP AS
SELECT p.id AS old_id,
       post_id_of_key(p.organization_id, m.new_id, p.division_ocdid) AS new_id,
       m.new_id AS new_role_id,
       p.organization_id, p.division_ocdid, p.jurisdiction_ocdid, r.label AS old_label,
       p.created_at
FROM posts p JOIN role_merges m ON m.old_id = p.role_id JOIN roles r ON r.id = p.role_id;

-- The organization's label for each new role: the role its oldest such post had. One row per
-- organization: UPDATE ... FROM applies only one of several matching rows, which lost the second key.
-- A label the organization already has wins.
UPDATE organizations o
SET extras_role_labels = k.labels || o.extras_role_labels
FROM (
    SELECT organization_id, jsonb_object_agg(new_role_id, old_label) AS labels
    FROM (
        SELECT DISTINCT ON (organization_id, new_role_id) organization_id, new_role_id, old_label
        FROM merged_posts ORDER BY organization_id, new_role_id, created_at, old_id
    ) oldest
    GROUP BY organization_id
) k
WHERE o.id = k.organization_id;

-- Per new key, the oldest old post keeps it; the rest are duplicates that fold into it.
CREATE TEMP TABLE merged_post_rekeys ON COMMIT DROP AS
SELECT DISTINCT ON (new_id) old_id, new_id, new_role_id, jurisdiction_ocdid FROM merged_posts ORDER BY new_id, created_at, old_id;

CREATE TEMP TABLE merged_post_duplicates ON COMMIT DROP AS
SELECT m.old_id AS duplicate_id, k.old_id AS keeper_old_id, k.new_id, m.jurisdiction_ocdid
FROM merged_posts m JOIN merged_post_rekeys k ON k.new_id = m.new_id AND k.old_id <> m.old_id;

-- A membership's id is uuid5 of (person, post): every person in the jurisdiction, since a claim
-- may name a membership that has no row. Duplicates' memberships take the keeper's new key.
CREATE TEMP TABLE merged_membership_rekeys ON COMMIT DROP AS
SELECT uuid_generate_v5('5364ee76-7dec-41fd-a3b0-7218a73ea92f'::uuid, pe.id::text || '|' || x.old_id::text) AS old_id,
       uuid_generate_v5('5364ee76-7dec-41fd-a3b0-7218a73ea92f'::uuid, pe.id::text || '|' || x.new_id::text) AS new_id
FROM (SELECT old_id, new_id, jurisdiction_ocdid FROM merged_post_rekeys
      UNION ALL SELECT duplicate_id, new_id, jurisdiction_ocdid FROM merged_post_duplicates) x
JOIN people pe ON pe.jurisdiction_ocdid = x.jurisdiction_ocdid;

-- Duplicates' memberships move to the keeper (still under its old id; the cascade below re-keys
-- them again), then the duplicate posts go.
UPDATE memberships SET post_id = d.keeper_old_id FROM merged_post_duplicates d WHERE memberships.post_id = d.duplicate_id;
UPDATE claims SET value = to_jsonb(d.keeper_old_id::text)
FROM merged_post_duplicates d
WHERE claims.entity_type = 'person' AND claims.field_path = 'posts' AND claims.value #>> '{}' = d.duplicate_id::text;
UPDATE claims SET entity_id = d.keeper_old_id FROM merged_post_duplicates d WHERE claims.entity_type = 'post' AND claims.entity_id = d.duplicate_id;
UPDATE claims SET value = to_jsonb(d.keeper_old_id::text)
FROM merged_post_duplicates d
WHERE claims.entity_type = 'post' AND claims.field_path = 'same_as' AND claims.value #>> '{}' = d.duplicate_id::text;
DELETE FROM posts WHERE id IN (SELECT duplicate_id FROM merged_post_duplicates);

-- memberships.post_id follows through its ON UPDATE CASCADE foreign keys.
UPDATE posts SET id = k.new_id, role_id = k.new_role_id FROM merged_post_rekeys k WHERE posts.id = k.old_id;

UPDATE memberships SET id = r.new_id FROM merged_membership_rekeys r WHERE memberships.id = r.old_id;

UPDATE claims SET value = to_jsonb(k.new_id::text)
FROM merged_post_rekeys k
WHERE claims.entity_type = 'person' AND claims.field_path = 'posts' AND claims.value #>> '{}' = k.old_id::text;

UPDATE claims SET entity_id = k.new_id FROM merged_post_rekeys k WHERE claims.entity_type = 'post' AND claims.entity_id = k.old_id;

UPDATE claims SET value = to_jsonb(k.new_id::text)
FROM merged_post_rekeys k
WHERE claims.entity_type = 'post' AND claims.field_path = 'same_as' AND claims.value #>> '{}' = k.old_id::text;

UPDATE claims SET entity_id = r.new_id FROM merged_membership_rekeys r WHERE claims.entity_type = 'membership' AND claims.entity_id = r.old_id;

COMMIT;
