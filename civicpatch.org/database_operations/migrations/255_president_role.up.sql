-- One `president` role (2026-10-20-plan-president-role.md): council-president, village-president
-- and commission-president are one office under local names, as 253 made the member roles one.
-- How a president is filled is read per town by the organizations collector, so the role no
-- longer has to carry it. The organization's own label goes in extras_role_labels, as 253's did.
--
-- 253's rekey for these three ids: a post's id is the hash of (organization, role, division), so
-- every such post gets its `president` key, memberships, membership ids and claims following;
-- two old posts meeting at one key merge into the oldest. Priority is council-president's, which
-- holds nearly all of them, so a president still ranks below member.

BEGIN;

INSERT INTO roles (id, label, status, is_unique, priority, selection_method, config_path)
SELECT 'president', 'President', 'active', true, priority, 'elected_by_members', config_path
FROM roles WHERE id IN ('council-president', 'village-president', 'commission-president')
ORDER BY id <> 'council-president', priority
LIMIT 1
ON CONFLICT (id) DO NOTHING;

CREATE TEMP TABLE president_posts ON COMMIT DROP AS
SELECT p.id AS old_id,
       post_id_of_key(p.organization_id, 'president', p.division_ocdid) AS new_id,
       p.organization_id, p.division_ocdid, p.jurisdiction_ocdid, p.role_id AS old_role_id, r.label AS old_label,
       p.created_at
FROM posts p JOIN roles r ON r.id = p.role_id
WHERE p.role_id IN ('council-president', 'village-president', 'commission-president');

-- The organization's label for `president`: the role its oldest president post had.
UPDATE organizations o
SET extras_role_labels = o.extras_role_labels || jsonb_build_object('president', k.old_label)
FROM (SELECT DISTINCT ON (organization_id) organization_id, old_label FROM president_posts ORDER BY organization_id, created_at, old_id) k
WHERE o.id = k.organization_id AND NOT (o.extras_role_labels ? 'president');

-- Per new key, the oldest old post keeps it; the rest are duplicates that fold into it.
CREATE TEMP TABLE president_post_rekeys ON COMMIT DROP AS
SELECT DISTINCT ON (new_id) old_id, new_id, jurisdiction_ocdid FROM president_posts ORDER BY new_id, created_at, old_id;

CREATE TEMP TABLE president_post_duplicates ON COMMIT DROP AS
SELECT m.old_id AS duplicate_id, k.old_id AS keeper_old_id, k.new_id, m.jurisdiction_ocdid
FROM president_posts m JOIN president_post_rekeys k ON k.new_id = m.new_id AND k.old_id <> m.old_id;

-- A membership's id is uuid5 of (person, post): every person in the jurisdiction, since a claim
-- may name a membership that has no row. Duplicates' memberships take the keeper's new key.
CREATE TEMP TABLE president_membership_rekeys ON COMMIT DROP AS
SELECT uuid_generate_v5('5364ee76-7dec-41fd-a3b0-7218a73ea92f'::uuid, pe.id::text || '|' || x.old_id::text) AS old_id,
       uuid_generate_v5('5364ee76-7dec-41fd-a3b0-7218a73ea92f'::uuid, pe.id::text || '|' || x.new_id::text) AS new_id
FROM (SELECT old_id, new_id, jurisdiction_ocdid FROM president_post_rekeys
      UNION ALL SELECT duplicate_id, new_id, jurisdiction_ocdid FROM president_post_duplicates) x
JOIN people pe ON pe.jurisdiction_ocdid = x.jurisdiction_ocdid;

-- Duplicates' memberships move to the keeper (still under its old id; the cascade below re-keys
-- them again), then the duplicate posts go.
UPDATE memberships SET post_id = d.keeper_old_id FROM president_post_duplicates d WHERE memberships.post_id = d.duplicate_id;
UPDATE claims SET value = to_jsonb(d.keeper_old_id::text)
FROM president_post_duplicates d
WHERE claims.entity_type = 'person' AND claims.field_path = 'posts' AND claims.value #>> '{}' = d.duplicate_id::text;
UPDATE claims SET entity_id = d.keeper_old_id FROM president_post_duplicates d WHERE claims.entity_type = 'post' AND claims.entity_id = d.duplicate_id;
UPDATE claims SET value = to_jsonb(d.keeper_old_id::text)
FROM president_post_duplicates d
WHERE claims.entity_type = 'post' AND claims.field_path = 'same_as' AND claims.value #>> '{}' = d.duplicate_id::text;
DELETE FROM posts WHERE id IN (SELECT duplicate_id FROM president_post_duplicates);

-- memberships.post_id follows through its ON UPDATE CASCADE foreign keys.
UPDATE posts SET id = k.new_id, role_id = 'president' FROM president_post_rekeys k WHERE posts.id = k.old_id;

UPDATE memberships SET id = r.new_id FROM president_membership_rekeys r WHERE memberships.id = r.old_id;

UPDATE claims SET value = to_jsonb(k.new_id::text)
FROM president_post_rekeys k
WHERE claims.entity_type = 'person' AND claims.field_path = 'posts' AND claims.value #>> '{}' = k.old_id::text;

UPDATE claims SET entity_id = k.new_id FROM president_post_rekeys k WHERE claims.entity_type = 'post' AND claims.entity_id = k.old_id;

UPDATE claims SET value = to_jsonb(k.new_id::text)
FROM president_post_rekeys k
WHERE claims.entity_type = 'post' AND claims.field_path = 'same_as' AND claims.value #>> '{}' = k.old_id::text;

UPDATE claims SET entity_id = r.new_id FROM president_membership_rekeys r WHERE claims.entity_type = 'membership' AND claims.entity_id = r.old_id;

COMMIT;
