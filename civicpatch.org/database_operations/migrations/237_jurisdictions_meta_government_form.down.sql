BEGIN;

ALTER TABLE jurisdictions DROP CONSTRAINT IF EXISTS jurisdictions_meta_government_form_check;
ALTER TABLE jurisdictions DROP COLUMN IF EXISTS meta_government_form;

COMMIT;
