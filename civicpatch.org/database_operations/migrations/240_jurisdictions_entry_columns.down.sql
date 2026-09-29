-- Restores `meta_government_form` empty: the values it held were all derivable from the config files.

BEGIN;

ALTER TABLE jurisdictions DROP CONSTRAINT IF EXISTS jurisdictions_extras_government_form_check;
ALTER TABLE jurisdictions
    DROP COLUMN IF EXISTS name,
    DROP COLUMN IF EXISTS url,
    DROP COLUMN IF EXISTS population,
    DROP COLUMN IF EXISTS geoid,
    DROP COLUMN IF EXISTS wiki_url,
    DROP COLUMN IF EXISTS extras_government_form;

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
