-- Reverse of 119. Aliases go; roles are set `inactive` rather than deleted.
--
-- A DELETE stops working the moment the derivation runs: `posts.role_id` is NO ACTION, so
-- the first scraped township with a Trustee pins that role permanently and rolling back
-- would fail on a FK. `inactive` is what removal means for a role anyway — per 109's
-- vocabulary it is the one status the matcher never sees — so this is the reversal, not a
-- softer version of it.
--
-- Roles this migration did not create are untouched: the WHERE clause names only its own,
-- and one of them existing beforehand under a different id simply means the UPDATE finds
-- nothing to do.
BEGIN;

DELETE FROM role_aliases WHERE lower(label) IN (
    'alderman', 'alderwoman', 'aldermen',
    'trustees', 'township trustee', 'village trustee',
    'township supervisor', 'town supervisor',
    'city clerk', 'town clerk', 'township clerk', 'village clerk', 'borough clerk',
    'municipal clerk',
    'city treasurer', 'town treasurer', 'township treasurer', 'village treasurer',
    'deputy city clerk', 'deputy town clerk', 'deputy township clerk',
    'deputy city treasurer', 'deputy township treasurer',
    'town moderator', 'city secretary', 'town secretary',
    'township assessor', 'city assessor',
    'city manager', 'town manager', 'township manager', 'village manager',
    'committeeperson', 'committeewomen', 'committee woman',
    'chairperson', 'vice chairperson', 'vice-chairperson',
    'select person', 'selectperson'
);

UPDATE roles SET status = 'inactive' WHERE id IN (
    'alderperson', 'trustee', 'supervisor', 'deputy-supervisor',
    'clerk', 'deputy-clerk', 'treasurer', 'deputy-treasurer',
    'moderator', 'secretary', 'assessor'
);

COMMIT;
