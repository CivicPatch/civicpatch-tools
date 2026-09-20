BEGIN;

-- Restores the jsonb copy from the column that replaced it. A row whose copy was an empty
-- array does not come back, because an empty array and an absent key are indistinguishable
-- in the column.
UPDATE jurisdictions
   SET data = jsonb_set(data, '{parent_ocdids}', to_jsonb(meta_parent_ocdids))
 WHERE cardinality(meta_parent_ocdids) > 0;

COMMIT;
