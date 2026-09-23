BEGIN;

-- Every claim says where it came from (§5). Rows filed before the rule get an audit note; the
-- withdraw rows 214 synthesised have no source of their own either.
UPDATE assertions
   SET sources = jsonb_build_array(jsonb_build_object('note', 'pre-source claim'))
 WHERE sources IS NULL OR sources = '[]'::jsonb;

ALTER TABLE assertions ALTER COLUMN sources SET NOT NULL;
-- `ADD CONSTRAINT` has no `IF NOT EXISTS`, and a migration the entrypoint retries must not
-- abort on the second pass.
ALTER TABLE assertions DROP CONSTRAINT IF EXISTS assertions_sources_nonempty;
ALTER TABLE assertions
    ADD CONSTRAINT assertions_sources_nonempty CHECK (jsonb_array_length(sources) > 0);

COMMIT;
