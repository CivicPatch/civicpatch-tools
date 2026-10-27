-- Every default organization becomes, or stands beside, `{lsad} Officers`, the catch-all for
-- offices on no board. The name mirrors core/organization_derivation.py::default_organization_name.
-- A default still named 'Government' is renamed in place, keeping its id. A default renamed to a
-- board before keeps its name; Officers is created beside it and takes the flag.

BEGIN;

CREATE TEMP TABLE default_organization_names ON COMMIT DROP AS
SELECT jurisdiction_ocdid,
       default_id,
       CASE WHEN last_word IN ('city', 'town', 'township', 'county', 'village', 'borough', 'plantation')
            THEN initcap(last_word) || ' Officers'
            ELSE 'Officers'
       END AS name
FROM (
    SELECT j.jurisdiction_ocdid,
           d.id AS default_id,
           lower(substring(regexp_replace(j.data->>'name', '\s*\([^)]*\)', '', 'g') FROM '(\S+)\s*$')) AS last_word
    FROM jurisdictions j
    JOIN organizations d ON d.jurisdiction_ocdid = j.jurisdiction_ocdid AND d.meta_is_default
) defaults;

UPDATE organizations o SET name = n.name
FROM default_organization_names n
WHERE o.id = n.default_id
  AND o.name = 'Government'
  AND NOT EXISTS (
    SELECT 1 FROM organizations taken
    WHERE taken.jurisdiction_ocdid = n.jurisdiction_ocdid AND taken.name = n.name
  );

INSERT INTO organizations (jurisdiction_ocdid, name)
SELECT jurisdiction_ocdid, name FROM default_organization_names
ON CONFLICT (jurisdiction_ocdid, name) DO NOTHING;

UPDATE organizations o SET meta_is_default = false
FROM default_organization_names n
WHERE o.jurisdiction_ocdid = n.jurisdiction_ocdid AND o.meta_is_default AND o.name <> n.name;

UPDATE organizations o SET meta_is_default = true
FROM default_organization_names n
WHERE o.jurisdiction_ocdid = n.jurisdiction_ocdid AND o.name = n.name;

COMMIT;
