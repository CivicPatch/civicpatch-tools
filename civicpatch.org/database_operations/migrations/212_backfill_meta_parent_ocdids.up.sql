BEGIN;

-- Ancestry has had two homes: this column, written only by GenerateMapsWorkflow, and
-- `data->'parent_ocdids'`, synced from open-data's YAML mirror. The mirror is being retired,
-- so every already-synced state has to reach the column without waiting for a map run.
UPDATE jurisdictions
   SET meta_parent_ocdids = ARRAY(SELECT jsonb_array_elements_text(data -> 'parent_ocdids'))
 WHERE data ? 'parent_ocdids'
   AND cardinality(meta_parent_ocdids) = 0;

COMMIT;
