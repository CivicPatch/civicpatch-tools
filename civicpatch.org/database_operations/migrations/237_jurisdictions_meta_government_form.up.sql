-- A jurisdiction's government form: its one saved copy. Set when the sync first builds
-- organizations from a config rule, or by hand. When null, shared/config/government_forms.yml
-- decides; see shared/utils/government_forms.py.

BEGIN;

ALTER TABLE jurisdictions ADD COLUMN IF NOT EXISTS meta_government_form text;

ALTER TABLE jurisdictions DROP CONSTRAINT IF EXISTS jurisdictions_meta_government_form_check;
ALTER TABLE jurisdictions ADD CONSTRAINT jurisdictions_meta_government_form_check CHECK (
    meta_government_form IS NULL OR meta_government_form IN (
        'mayor_council',
        'council_manager',
        'commission',
        'township_board',
        'open_town_meeting',
        'representative_town_meeting',
        'county_executive'
    )
);

COMMIT;
